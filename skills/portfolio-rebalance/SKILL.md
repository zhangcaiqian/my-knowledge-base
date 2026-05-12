---
name: portfolio-rebalance
description: >-
  计算资产配置组合的调仓方案：根据目标权重、当前持仓、增量资金，分别生成
  固定增量资金、增量资金充裕但只买不卖、无增量资金三种调仓场景，并在调仓
  完成后输出可视化调仓报告。当用户提到资产配置、组合调仓、再平衡、目标占
  比、买入卖出方案、调仓报告时使用。
---

# 资产配置组合调仓

本 Skill 位于 `skills/portfolio-rebalance/`，知识库根目录为仓库根。

- 脚本目录: `skills/portfolio-rebalance/scripts/`
- 输入模板: `skills/portfolio-rebalance/references/input-template.json`
- 主脚本: `python3 skills/portfolio-rebalance/scripts/rebalance.py`

## 适用范围

适用于“先有目标权重，再根据当前持仓与现金条件生成调仓方案”的场景。

当前默认支持三种场景，且每次都要分别输出：

1. 已知当前资产比例，且**给定固定增量资金**时，如何分配这笔新增资金
2. **增量资金充裕**、且**只买不卖**时，达到目标权重所需的最小新增资金与买入方案
3. **没有增量资金**时，如何通过买卖互换调到目标权重

## 关键规则

1. **优先用脚本计算**：不要手算金额和比例，统一通过 `rebalance.py` 生成
2. **目标权重和当前金额必须结构化**：先整理成 JSON，再运行脚本
3. **若缺少子资产目标权重，只能精确到大类层面**：脚本会提示哪些类别仍需补充拆分规则
4. **报告先区分“计划调仓”和“确认完成”**：确认完成后再生成最终报告
5. **默认忽略手续费、税费、最小交易单位与流动性限制**：除非用户明确提供这些约束

## 输入格式

先按需要创建一个 JSON 文件，可参考 `skills/portfolio-rebalance/references/input-template.json`。

最常用字段：

```json
{
  "currency": "CNY",
  "incremental_cash": 50000,
  "categories": [
    {
      "id": "large_growth",
      "name": "大盘成长",
      "target_weight": 0.23,
      "assets": [
        {
          "id": "fund_a",
          "name": "基金A",
          "current_amount": 120000,
          "target_weight_in_category": 0.6
        },
        {
          "id": "fund_b",
          "name": "基金B",
          "current_amount": 80000,
          "target_weight_in_category": 0.4
        }
      ]
    }
  ]
}
```

字段说明：

- `categories[].target_weight`: 大类目标占比，所有大类合计必须为 1
- `assets[].current_amount`: 当前市值或当前持仓金额
- `assets[].target_weight_in_category`: 子资产在所属大类中的目标占比
- `incremental_cash`: 场景 1 的固定增量资金额
- `confirmed_trades`: 用户确认调仓完成后，可把真实成交额写回输入文件，再生成报告

如果某个大类下有多个资产，但**还没定义子资产目标权重**，脚本会退化为“按大类聚合计算”，不会擅自分配到具体产品。

## 工作流

### 步骤 1：整理输入

让用户确认或补充以下信息：

1. 当前持仓金额是按**大类**提供，还是按**具体资产**提供
2. 每个大类下多个资产的**目标拆分比例**
3. 场景 1 的**固定新增资金金额**
4. 是否考虑手续费、最小交易单位、赎回时滞、不可卖出约束

### 步骤 2：生成三种调仓方案

```bash
python3 skills/portfolio-rebalance/scripts/rebalance.py \
  plan \
  --input skills/portfolio-rebalance/references/input-template.json
```

默认输出 Markdown，可直接贴给用户。

如需机器可读结果：

```bash
python3 skills/portfolio-rebalance/scripts/rebalance.py \
  plan \
  --input /absolute/path/to/portfolio.json \
  --format json
```

### 步骤 3：用户确认完成后生成报告

如果用户确认按某个方案执行完毕，可以：

1. 将真实成交额填入 `confirmed_trades`
2. 或直接基于某个场景的计划方案生成“计划完成版”报告

示例：

```bash
python3 skills/portfolio-rebalance/scripts/rebalance.py \
  report \
  --input /absolute/path/to/portfolio.json \
  --scenario no_increment
```

如需写入文件：

```bash
python3 skills/portfolio-rebalance/scripts/rebalance.py \
  report \
  --input /absolute/path/to/portfolio.json \
  --scenario fixed_increment \
  --output /tmp/rebalance-report.md
```

## 场景算法说明

### 场景 1：固定增量资金

给定一笔固定新增资金，只允许买入，不卖出。脚本会在“最终总资产 = 当前总资产 + 新增资金”条件下，计算**最接近目标权重**的买入分配方案。

### 场景 2：增量资金充裕，只买不卖

脚本会计算“为了在不卖出的前提下达到目标权重，最少需要再投入多少钱”，并给出对应买入方案。

### 场景 3：无增量资金

总资产不变，直接按目标权重计算应买入和卖出的金额，给出净买卖清单。

## 报告要求

生成报告时，优先包含：

1. 调仓前后各大类金额与占比
2. 调仓前后偏离目标的程度
3. 买入卖出清单
4. 类别级可视化（Mermaid 饼图）
5. 若输入中有子资产目标，则附子资产级明细

## 常见确认问题

若用户尚未提供完整数据，优先追问这些问题：

1. 每个大类下面具体有哪些资产？当前金额分别是多少？
2. 每个大类内多个资产，目标权重怎么拆？
3. 场景 1 的增量资金具体是多少？
4. 调仓是否允许卖出？是否有某些资产只能加仓不能减仓？
5. 是否要把手续费、最小交易单位、赎回到账时间纳入计算？
