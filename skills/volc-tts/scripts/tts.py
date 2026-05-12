#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山引擎语音合成脚本（WebSocket V3 大模型 TTS）

用法：
  # direct 模式（单音色朗读）
  python skills/volc-tts/scripts/tts.py direct \
    --text "你好，这是一段测试语音。" \
    --speaker zh_male_baqiqingshu_uranus_bigtts \
    --output assets/tts/out.mp3

  # podcast 模式（双人播客，模型自动生成对话）
  python skills/volc-tts/scripts/tts.py podcast \
    --text "文章正文内容..." \
    --speaker-a zh_male_shenyeboke_uranus_bigtts \
    --speaker-b zh_female_vv_uranus_bigtts \
    --output assets/tts/out.mp3

  # 从文件读取文本
  python skills/volc-tts/scripts/tts.py direct \
    --file path/to/article.md \
    --speaker zh_male_baqiqingshu_uranus_bigtts \
    --output assets/tts/out.mp3

  # 列出所有已验证可用音色
  python skills/volc-tts/scripts/tts.py list-voices

认证配置（优先级：命令行参数 > 环境变量 > config.json）：
  环境变量：VOLC_TTS_APP_ID / VOLC_TTS_TOKEN
  config.json 字段：volcengine.tts_app_id / volcengine.tts_token
"""

import argparse
import asyncio
import inspect
import json
import ssl
import sys
import uuid
from pathlib import Path

import aiofiles
import certifi
import websockets
try:
    from websockets.asyncio.client import ClientConnection
except ModuleNotFoundError:
    from typing import Any as ClientConnection

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def _connect_ws(uri: str, headers: dict):
    """兼容不同 websockets 版本的连接参数"""
    params = inspect.signature(websockets.connect).parameters
    if "additional_headers" in params:
        return websockets.connect(
            uri,
            additional_headers=headers,
            ssl=_SSL_CTX,
            max_size=1_000_000_000,
        )
    return websockets.connect(
        uri,
        extra_headers=headers,
        ssl=_SSL_CTX,
        max_size=1_000_000_000,
    )

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
BASE_DIR = SKILL_DIR.parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

# ---------------------------------------------------------------------------
# WebSocket V3 协议常量
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_RESPONSE = 0b1011
FULL_SERVER_RESPONSE = 0b1001
ERROR_INFORMATION = 0b1111

MSG_FLAG_NO_SEQ = 0b0000
MSG_FLAG_WITH_EVENT = 0b0100

NO_SERIALIZATION = 0b0000
JSON_SERIALIZATION = 0b0001
COMPRESSION_NO = 0b0000

EVENT_NONE = 0
EVENT_START_CONNECTION = 1
EVENT_FINISH_CONNECTION = 2
EVENT_CONNECTION_STARTED = 50
EVENT_CONNECTION_FAILED = 51
EVENT_CONNECTION_FINISHED = 52
EVENT_START_SESSION = 100
EVENT_FINISH_SESSION = 102
EVENT_SESSION_STARTED = 150
EVENT_SESSION_FINISHED = 152
EVENT_SESSION_FAILED = 153
EVENT_TASK_REQUEST = 200
EVENT_TTS_SENTENCE_START = 350
EVENT_TTS_SENTENCE_END = 351
EVENT_TTS_RESPONSE = 352

WS_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
# 豆包语音合成模型2.0，音色后缀 _uranus_bigtts
RESOURCE_ID_DIRECT = "seed-tts-2.0"
# podcast 模式：语音播客大模型（⚠️ 需在控制台确认正确值）
RESOURCE_ID_PODCAST = "volc.podcast.default"

# ---------------------------------------------------------------------------
# 豆包语音合成模型2.0 可用音色（_uranus_bigtts 后缀）
# 文档：https://www.volcengine.com/docs/6561/1257544
# 格式：(speaker_id, 名称, 适合内容)
# ---------------------------------------------------------------------------
VERIFIED_VOICES = [
    # 有声阅读 / 朗读 / 播音
    ("zh_male_baqiqingshu_uranus_bigtts",    "霸气青叔   男声  厚重有力，适合气势型朗读/人物传记"),
    ("zh_male_xuanyijieshuo_uranus_bigtts",  "悬疑解说   男声  低沉神秘，适合悬疑叙事/案件解说"),
    ("zh_male_shenyeboke_uranus_bigtts",     "深夜播客   男声  磁性沉稳，适合播客/纪录片/长篇随笔"),
    ("zh_male_yuanboxiaoshu_uranus_bigtts",  "渊博小叔   男声  知识感强，适合财经/科普/方法论讲解"),
    ("zh_male_gaolengchenwen_uranus_bigtts", "高冷沉稳   男声  理性克制，适合课程讲解/概念拆解"),
    ("zh_male_m191_uranus_bigtts",           "云舟       男声  自然中性，适合知识朗读/说明性长文"),
    # 通用 / 女声
    ("zh_female_vv_uranus_bigtts",           "Vivi       女声  知性优雅，适合温和朗读/书摘/有声书"),
    ("zh_female_qingxinnvsheng_uranus_bigtts","清新女声  女声  清爽自然，适合轻知识/生活方式内容"),
    ("zh_female_shuangkuaisisi_uranus_bigtts","爽快思思  女声  明快活泼，适合资讯快报/短视频口播"),
]

# ---------------------------------------------------------------------------
# 协议辅助
# ---------------------------------------------------------------------------

def _make_header(msg_type: int, flags: int = MSG_FLAG_WITH_EVENT,
                 serial: int = JSON_SERIALIZATION) -> bytes:
    b0 = (PROTOCOL_VERSION << 4) | DEFAULT_HEADER_SIZE
    b1 = (msg_type << 4) | flags
    b2 = (serial << 4) | COMPRESSION_NO
    return bytes([b0, b1, b2, 0x00])


def _make_optional(event: int, session_id: str | None = None) -> bytes:
    buf = bytearray()
    if event != EVENT_NONE:
        buf.extend(event.to_bytes(4, "big", signed=True))
    if session_id is not None:
        sid = session_id.encode()
        buf.extend(len(sid).to_bytes(4, "big", signed=True))
        buf.extend(sid)
    return bytes(buf)


async def _send(ws: ClientConnection, header: bytes, optional: bytes,
                payload: bytes | None = None):
    msg = bytearray(header) + bytearray(optional)
    if payload is not None:
        msg.extend(len(payload).to_bytes(4, "big", signed=True))
        msg.extend(payload)
    await ws.send(bytes(msg))


def _parse_response(raw: bytes) -> dict:
    if len(raw) < 4:
        return {"error": "response too short"}
    msg_type = (raw[1] >> 4) & 0x0F
    flags = raw[1] & 0x0F
    offset = 4
    result: dict = {"msg_type": msg_type, "flags": flags,
                    "event": EVENT_NONE, "audio": None, "meta": None,
                    "connection_id": None, "session_id": None, "error_code": None}

    if msg_type == ERROR_INFORMATION:
        result["error_code"] = int.from_bytes(raw[offset:offset + 4], "big", signed=True)
        offset += 4
        size = int.from_bytes(raw[offset:offset + 4], "big"); offset += 4
        result["meta"] = raw[offset:offset + size].decode("utf-8", errors="replace")
        return result

    if flags & 0b100:
        result["event"] = int.from_bytes(raw[offset:offset + 4], "big", signed=True)
        offset += 4
        ev = result["event"]

        def _read_str(o):
            n = int.from_bytes(raw[o:o+4], "big"); o += 4
            return raw[o:o+n].decode("utf-8", errors="replace"), o + n

        def _read_bytes(o):
            n = int.from_bytes(raw[o:o+4], "big"); o += 4
            return raw[o:o+n], o + n

        if ev == EVENT_CONNECTION_STARTED:
            result["connection_id"], offset = _read_str(offset)
        elif ev == EVENT_CONNECTION_FAILED:
            result["meta"], offset = _read_str(offset)
        elif ev in (EVENT_SESSION_STARTED, EVENT_SESSION_FAILED, EVENT_SESSION_FINISHED):
            result["session_id"], offset = _read_str(offset)
            result["meta"], offset = _read_str(offset)
        elif ev == EVENT_TTS_RESPONSE:
            result["session_id"], offset = _read_str(offset)
            result["audio"], offset = _read_bytes(offset)
        elif ev in (EVENT_TTS_SENTENCE_START, EVENT_TTS_SENTENCE_END):
            result["session_id"], offset = _read_str(offset)
            payload, offset = _read_bytes(offset)
            result["meta"] = payload.decode("utf-8", errors="replace")

    if result["audio"] is None and msg_type == AUDIO_ONLY_RESPONSE and offset + 4 <= len(raw):
        size = int.from_bytes(raw[offset:offset + 4], "big")
        result["audio"] = raw[offset + 4:offset + 4 + size]

    return result

# ---------------------------------------------------------------------------
# 认证加载
# ---------------------------------------------------------------------------

def load_credentials(app_id: str | None, token: str | None) -> tuple[str, str]:
    import os
    if not app_id:
        app_id = os.environ.get("VOLC_TTS_APP_ID")
    if not token:
        token = os.environ.get("VOLC_TTS_TOKEN")

    if (not app_id or not token) and CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        volc = cfg.get("volcengine", {})
        app_id = app_id or volc.get("tts_app_id", "")
        token = token or volc.get("tts_token", "")

    if not app_id or not token:
        sys.exit(
            "错误：缺少凭证。\n"
            "请设置 VOLC_TTS_APP_ID / VOLC_TTS_TOKEN 环境变量，\n"
            "或在 config.json 的 volcengine.tts_app_id / volcengine.tts_token 中填写。\n"
            "控制台地址：https://console.volcengine.com/speech/app"
        )
    return app_id, token

# ---------------------------------------------------------------------------
# direct 模式：单音色 WebSocket V3
# ---------------------------------------------------------------------------

async def _run_direct(app_id: str, token: str, text: str, speaker: str,
                      output_path: Path, speed: float, format_: str,
                      model: str = ""):
    session_id = uuid.uuid4().hex
    ws_headers = {
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": RESOURCE_ID_DIRECT,
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }

    def _payload(event: int, **kw) -> bytes:
        req_params: dict = {
            "text": kw.get("text", ""),
            "speaker": speaker,
            "audio_params": {
                "format": format_,
                "sample_rate": 24000,
                "speech_rate": int((speed - 1.0) * 100),
            },
        }
        if model:
            req_params["model"] = model
        body = {
            "user": {"uid": "skill-tts"},
            "event": event,
            "namespace": "BidirectionalTTS",
            "req_params": req_params,
        }
        return json.dumps(body, ensure_ascii=False).encode()

    print(f"[direct] 连接 {WS_ENDPOINT}")
    async with _connect_ws(WS_ENDPOINT, ws_headers) as ws:
        # StartConnection
        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, NO_SERIALIZATION),
                    _make_optional(EVENT_START_CONNECTION),
                    b"{}")
        r = _parse_response(await ws.recv())
        if r["event"] != EVENT_CONNECTION_STARTED:
            sys.exit(f"连接失败：{r.get('meta')}")
        print(f"[direct] 连接成功 connection_id={r['connection_id']}")

        # StartSession
        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, JSON_SERIALIZATION),
                    _make_optional(EVENT_START_SESSION, session_id),
                    _payload(EVENT_START_SESSION))
        r = _parse_response(await ws.recv())
        if r["event"] != EVENT_SESSION_STARTED:
            sys.exit(f"会话启动失败：{r.get('meta')}")
        print(f"[direct] 会话开始 session_id={session_id}")

        # TaskRequest
        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, JSON_SERIALIZATION),
                    _make_optional(EVENT_TASK_REQUEST, session_id),
                    _payload(EVENT_TASK_REQUEST, text=text))

        # FinishSession
        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, JSON_SERIALIZATION),
                    _make_optional(EVENT_FINISH_SESSION, session_id),
                    b"{}")

        # 接收音频
        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        print(f"[direct] 接收音频 -> {output_path}")
        async with aiofiles.open(output_path, "wb") as f:
            while True:
                raw = await ws.recv()
                r = _parse_response(raw)
                if r["audio"]:
                    await f.write(r["audio"])
                    total_bytes += len(r["audio"])
                elif r["event"] == EVENT_SESSION_FINISHED:
                    print(f"[direct] 完成，共 {total_bytes} 字节")
                    break
                elif r["event"] == EVENT_SESSION_FAILED:
                    sys.exit(f"合成失败：{r.get('meta')}")
                elif r.get("error_code") is not None:
                    sys.exit(f"服务器错误 code={r['error_code']}：{r.get('meta')}")

        # FinishConnection
        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, NO_SERIALIZATION),
                    _make_optional(EVENT_FINISH_CONNECTION),
                    b"{}")
        await ws.recv()

# ---------------------------------------------------------------------------
# podcast 模式：语音播客大模型
# ---------------------------------------------------------------------------

async def _run_podcast(app_id: str, token: str, text: str,
                       speaker_a: str, speaker_b: str,
                       output_path: Path, format_: str):
    """
    语音播客大模型：直接传入原始文章文本，模型自动生成双人对话播客音频。
    ⚠️ RESOURCE_ID_PODCAST 需参考官方文档 https://www.volcengine.com/docs/6561/1668014
       在控制台开通「语音播客大模型」权限后，将正确的 Resource-Id 更新到脚本顶部。
    """
    session_id = uuid.uuid4().hex
    ws_headers = {
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": RESOURCE_ID_PODCAST,
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }

    def _payload(event: int, **kw) -> bytes:
        body = {
            "user": {"uid": "skill-tts"},
            "event": event,
            "namespace": "PodcastTTS",
            "req_params": {
                "text": kw.get("text", ""),
                "speakers": [
                    {"role": "host_a", "speaker": speaker_a},
                    {"role": "host_b", "speaker": speaker_b},
                ],
                "audio_params": {
                    "format": format_,
                    "sample_rate": 24000,
                },
            },
        }
        return json.dumps(body, ensure_ascii=False).encode()

    print(f"[podcast] 连接 {WS_ENDPOINT}")
    async with _connect_ws(WS_ENDPOINT, ws_headers) as ws:
        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, NO_SERIALIZATION),
                    _make_optional(EVENT_START_CONNECTION),
                    b"{}")
        r = _parse_response(await ws.recv())
        if r["event"] != EVENT_CONNECTION_STARTED:
            sys.exit(f"连接失败：{r.get('meta')}\n"
                     "提示：请确认已开通「语音播客大模型」权限，并更新 RESOURCE_ID_PODCAST。")
        print(f"[podcast] 连接成功 connection_id={r['connection_id']}")

        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, JSON_SERIALIZATION),
                    _make_optional(EVENT_START_SESSION, session_id),
                    _payload(EVENT_START_SESSION))
        r = _parse_response(await ws.recv())
        if r["event"] != EVENT_SESSION_STARTED:
            sys.exit(f"会话启动失败：{r.get('meta')}")
        print(f"[podcast] 会话开始 session_id={session_id}")

        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, JSON_SERIALIZATION),
                    _make_optional(EVENT_TASK_REQUEST, session_id),
                    _payload(EVENT_TASK_REQUEST, text=text))

        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, JSON_SERIALIZATION),
                    _make_optional(EVENT_FINISH_SESSION, session_id),
                    b"{}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        print(f"[podcast] 接收音频 -> {output_path}")
        async with aiofiles.open(output_path, "wb") as f:
            while True:
                raw = await ws.recv()
                r = _parse_response(raw)
                if r["audio"]:
                    await f.write(r["audio"])
                    total_bytes += len(r["audio"])
                elif r["event"] == EVENT_SESSION_FINISHED:
                    print(f"[podcast] 完成，共 {total_bytes} 字节")
                    break
                elif r["event"] == EVENT_SESSION_FAILED:
                    sys.exit(f"合成失败：{r.get('meta')}")
                elif r.get("error_code") is not None:
                    sys.exit(f"服务器错误 code={r['error_code']}：{r.get('meta')}")

        await _send(ws,
                    _make_header(FULL_CLIENT_REQUEST, MSG_FLAG_WITH_EVENT, NO_SERIALIZATION),
                    _make_optional(EVENT_FINISH_CONNECTION),
                    b"{}")
        await ws.recv()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="火山引擎大模型语音合成（WebSocket V3）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("mode", choices=["direct", "podcast", "list-voices"],
                   help="合成模式：direct=单音色  podcast=双人播客  list-voices=查看可用音色")
    p.add_argument("--text", help="要合成的文字")
    p.add_argument("--file", help="从文件读取文本（.txt / .md）")
    p.add_argument("--output", help="输出音频路径（.mp3 / .wav）")
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "ogg_opus"],
                   help="音频格式（默认 mp3）")
    p.add_argument("--app-id", help="App ID（也可设置 VOLC_TTS_APP_ID 环境变量）")
    p.add_argument("--token", help="Token（也可设置 VOLC_TTS_TOKEN 环境变量）")

    direct = p.add_argument_group("direct 模式参数")
    direct.add_argument("--speaker", default="zh_male_baqiqingshu_uranus_bigtts",
                        help="音色 speaker（默认 zh_male_baqiqingshu_uranus_bigtts 霸气青叔）")
    direct.add_argument("--speed", type=float, default=1.0,
                        help="语速 0.5~2.0（默认 1.0）")
    direct.add_argument("--model", default="",
                        help="模型版本（通常无需指定，Resource-Id 已固定为 seed-tts-2.0）")

    pod = p.add_argument_group("podcast 模式参数")
    pod.add_argument("--speaker-a", default="zh_male_shenyeboke_uranus_bigtts",
                     help="主播A 音色（默认 深夜播客）")
    pod.add_argument("--speaker-b", default="zh_female_vv_uranus_bigtts",
                     help="主播B 音色（默认 Vivi）")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "list-voices":
        print("\n已验证可用音色（WebSocket V3 大模型 TTS）：\n")
        print(f"  {'speaker':50s}  风格")
        print("  " + "-" * 80)
        for spk, desc in VERIFIED_VOICES:
            print(f"  {spk:50s}  {desc}")
        print("\n用法示例：")
        print("  python skills/volc-tts/scripts/tts.py direct \\")
        print("    --speaker zh_male_yunzhou_jupiter_bigtts --model seed-tts-2.0 \\")
        print("    --text '...' --output out.mp3")
        return

    # 读取文本
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text.strip()
    else:
        if args.mode != "list-voices":
            parser.error("必须通过 --text 或 --file 提供文本")
        return

    if not text:
        sys.exit("错误：文本内容为空")
    if not args.output:
        parser.error("--output 为必填参数")

    app_id, token = load_credentials(args.app_id, args.token)
    output = Path(args.output)

    if args.mode == "direct":
        extra = f" | 模型：{args.model}" if args.model else ""
        print(f"模式：direct | 音色：{args.speaker} | 语速：{args.speed}{extra}")
        asyncio.run(_run_direct(app_id, token, text, args.speaker,
                                output, args.speed, args.format, args.model))
    else:
        print(f"模式：podcast | 主播A：{args.speaker_a} | 主播B：{args.speaker_b}")
        asyncio.run(_run_podcast(app_id, token, text,
                                 args.speaker_a, args.speaker_b,
                                 output, args.format))

    print(f"\n✓ 音频已保存：{output.resolve()}")


if __name__ == "__main__":
    main()
