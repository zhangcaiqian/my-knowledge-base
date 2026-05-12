#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any

getcontext().prec = 28

ZERO = Decimal("0")
ONE = Decimal("1")
MONEY_Q = Decimal("0.01")
WEIGHT_TOL = Decimal("0.0001")


@dataclass
class Leaf:
    id: str
    name: str
    category_id: str
    category_name: str
    current_amount: Decimal
    target_weight: Decimal
    source: str


@dataclass
class Portfolio:
    currency: str
    incremental_cash: Decimal | None
    categories: list[dict[str, Any]]
    leaves: list[Leaf]
    total_current: Decimal
    notes: list[str]
    confirmed_trades: dict[str, Decimal]


def parse_decimal(value: Any, field_name: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field_name} 不能为空")
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"{field_name} 不是合法数字: {value}") from exc


def q_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def fmt_money(value: Decimal, currency: str) -> str:
    return f"{currency} {q_money(value):,.2f}"


def fmt_pct(value: Decimal) -> str:
    pct = (value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{pct}%"


def sum_decimals(values: list[Decimal]) -> Decimal:
    total = ZERO
    for value in values:
        total += value
    return total


def make_leaf_id(prefix: str, raw_id: str) -> str:
    return f"{prefix}:{raw_id}"


def load_portfolio(path: Path) -> Portfolio:
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = data.get("categories")
    if not categories:
        raise ValueError("缺少 categories")

    currency = data.get("currency", "CNY")
    incremental_cash_raw = data.get("incremental_cash")
    incremental_cash = None if incremental_cash_raw is None else parse_decimal(incremental_cash_raw, "incremental_cash")

    category_weights: list[Decimal] = []
    leaves: list[Leaf] = []
    notes: list[str] = []
    category_rows: list[dict[str, Any]] = []

    for idx, category in enumerate(categories, start=1):
        cat_id = str(category.get("id") or f"category_{idx}")
        cat_name = str(category.get("name") or cat_id)
        cat_weight = parse_decimal(category.get("target_weight"), f"{cat_name}.target_weight")
        category_weights.append(cat_weight)

        assets = category.get("assets") or []
        if assets:
            asset_rows = []
            asset_weights = []
            has_asset_targets = all(asset.get("target_weight_in_category") is not None for asset in assets)
            current_sum = ZERO

            for a_idx, asset in enumerate(assets, start=1):
                asset_id = str(asset.get("id") or f"{cat_id}_asset_{a_idx}")
                asset_name = str(asset.get("name") or asset_id)
                current_amount = parse_decimal(asset.get("current_amount"), f"{cat_name}.{asset_name}.current_amount")
                current_sum += current_amount
                asset_rows.append(
                    {
                        "id": asset_id,
                        "name": asset_name,
                        "current_amount": current_amount,
                        "target_weight_in_category": asset.get("target_weight_in_category"),
                    }
                )
                if asset.get("target_weight_in_category") is not None:
                    asset_weights.append(parse_decimal(asset.get("target_weight_in_category"), f"{cat_name}.{asset_name}.target_weight_in_category"))

            category_rows.append(
                {
                    "id": cat_id,
                    "name": cat_name,
                    "target_weight": cat_weight,
                    "current_amount": current_sum,
                }
            )

            if has_asset_targets:
                if abs(sum_decimals(asset_weights) - ONE) > WEIGHT_TOL:
                    raise ValueError(f"{cat_name} 的子资产目标权重合计不等于 1")
                for row, asset_weight in zip(asset_rows, asset_weights):
                    leaves.append(
                        Leaf(
                            id=make_leaf_id("asset", row["id"]),
                            name=row["name"],
                            category_id=cat_id,
                            category_name=cat_name,
                            current_amount=row["current_amount"],
                            target_weight=cat_weight * asset_weight,
                            source="asset",
                        )
                    )
            else:
                if len(asset_rows) > 1:
                    notes.append(f"{cat_name} 下有多个资产，但未提供子资产目标权重；本次仅按大类聚合计算。")
                leaves.append(
                    Leaf(
                        id=make_leaf_id("category", cat_id),
                        name=cat_name,
                        category_id=cat_id,
                        category_name=cat_name,
                        current_amount=current_sum,
                        target_weight=cat_weight,
                        source="category",
                    )
                )
        else:
            current_amount = parse_decimal(category.get("current_amount"), f"{cat_name}.current_amount")
            category_rows.append(
                {
                    "id": cat_id,
                    "name": cat_name,
                    "target_weight": cat_weight,
                    "current_amount": current_amount,
                }
            )
            leaves.append(
                Leaf(
                    id=make_leaf_id("category", cat_id),
                    name=cat_name,
                    category_id=cat_id,
                    category_name=cat_name,
                    current_amount=current_amount,
                    target_weight=cat_weight,
                    source="category",
                )
            )

    if abs(sum_decimals(category_weights) - ONE) > WEIGHT_TOL:
        raise ValueError("大类 target_weight 合计不等于 1")

    leaf_weight_sum = sum_decimals([leaf.target_weight for leaf in leaves])
    if abs(leaf_weight_sum - ONE) > WEIGHT_TOL:
        raise ValueError("叶子层 target_weight 合计不等于 1，请检查子资产目标权重")

    total_current = sum_decimals([row["current_amount"] for row in category_rows])
    if total_current <= ZERO:
        raise ValueError("当前总资产必须大于 0")

    confirmed_trades: dict[str, Decimal] = {}
    for item in data.get("confirmed_trades", []):
        raw_id = item.get("id")
        if raw_id is None:
            raise ValueError("confirmed_trades 缺少 id")
        confirmed_trades[str(raw_id)] = parse_decimal(item.get("amount"), f"confirmed_trades[{raw_id}].amount")

    return Portfolio(
        currency=currency,
        incremental_cash=incremental_cash,
        categories=category_rows,
        leaves=leaves,
        total_current=total_current,
        notes=notes,
        confirmed_trades=confirmed_trades,
    )


def project_to_simplex(values: list[Decimal], total: Decimal) -> list[Decimal]:
    sorted_values = sorted(values, reverse=True)
    partial = ZERO
    rho = 0
    theta = ZERO

    for index, value in enumerate(sorted_values, start=1):
        partial += value
        candidate = (partial - total) / Decimal(index)
        if value - candidate > ZERO:
            rho = index
            theta = candidate

    if rho == 0:
        theta = (sum_decimals(sorted_values) - total) / Decimal(len(sorted_values))

    projected = [max(value - theta, ZERO) for value in values]
    residual = total - sum_decimals(projected)
    if residual != ZERO:
        positive_indexes = [i for i, value in enumerate(projected) if value > ZERO or residual > ZERO]
        if positive_indexes:
            projected[positive_indexes[0]] += residual
    return projected


def compute_target_amounts(leaves: list[Leaf], final_total: Decimal) -> dict[str, Decimal]:
    targets = {leaf.id: final_total * leaf.target_weight for leaf in leaves}
    residual = final_total - sum_decimals(list(targets.values()))
    if residual != ZERO:
        first_key = next(iter(targets))
        targets[first_key] += residual
    return targets


def scenario_fixed_increment(portfolio: Portfolio) -> dict[str, Any]:
    if portfolio.incremental_cash is None:
        raise ValueError("场景 fixed_increment 需要 incremental_cash")
    if portfolio.incremental_cash < ZERO:
        raise ValueError("incremental_cash 不能为负数")

    final_total = portfolio.total_current + portfolio.incremental_cash
    target_amounts = compute_target_amounts(portfolio.leaves, final_total)
    desired_delta = [target_amounts[leaf.id] - leaf.current_amount for leaf in portfolio.leaves]
    buy_amounts = project_to_simplex(desired_delta, portfolio.incremental_cash)
    trades = {leaf.id: amount for leaf, amount in zip(portfolio.leaves, buy_amounts)}
    return make_plan("fixed_increment", portfolio, trades, final_total)


def scenario_buy_only(portfolio: Portfolio) -> dict[str, Any]:
    ratios = []
    for leaf in portfolio.leaves:
        if leaf.target_weight <= ZERO:
            if leaf.current_amount > ZERO:
                raise ValueError(f"{leaf.name} 的目标权重为 0，无法在只买不卖时达成目标")
            ratios.append(ZERO)
            continue
        ratios.append(leaf.current_amount / leaf.target_weight)

    final_total = max(ratios)
    target_amounts = compute_target_amounts(portfolio.leaves, final_total)
    trades = {leaf.id: max(target_amounts[leaf.id] - leaf.current_amount, ZERO) for leaf in portfolio.leaves}
    return make_plan("buy_only", portfolio, trades, final_total)


def scenario_no_increment(portfolio: Portfolio) -> dict[str, Any]:
    final_total = portfolio.total_current
    target_amounts = compute_target_amounts(portfolio.leaves, final_total)
    trades = {leaf.id: target_amounts[leaf.id] - leaf.current_amount for leaf in portfolio.leaves}
    return make_plan("no_increment", portfolio, trades, final_total)


def make_plan(name: str, portfolio: Portfolio, trades: dict[str, Decimal], final_total: Decimal) -> dict[str, Any]:
    final_amounts = {leaf.id: leaf.current_amount + trades.get(leaf.id, ZERO) for leaf in portfolio.leaves}
    category_before: dict[str, Decimal] = {}
    category_after: dict[str, Decimal] = {}
    category_target: dict[str, Decimal] = {}

    for category in portfolio.categories:
        category_before[category["id"]] = category["current_amount"]
        category_after[category["id"]] = ZERO
        category_target[category["id"]] = category["target_weight"]

    leaf_rows = []
    total_buy = ZERO
    total_sell = ZERO
    for leaf in portfolio.leaves:
        trade = trades.get(leaf.id, ZERO)
        if trade > ZERO:
            total_buy += trade
        elif trade < ZERO:
            total_sell += -trade
        after_amount = final_amounts[leaf.id]
        category_after[leaf.category_id] += after_amount
        leaf_rows.append(
            {
                "id": leaf.id,
                "name": leaf.name,
                "category_id": leaf.category_id,
                "category_name": leaf.category_name,
                "before_amount": q_money(leaf.current_amount),
                "after_amount": q_money(after_amount),
                "trade_amount": q_money(trade),
                "target_weight": leaf.target_weight,
                "before_weight": leaf.current_amount / portfolio.total_current,
                "after_weight": after_amount / final_total if final_total > ZERO else ZERO,
                "source": leaf.source,
            }
        )

    category_rows = []
    for category in portfolio.categories:
        before_amount = category_before[category["id"]]
        after_amount = category_after[category["id"]]
        target_weight = category_target[category["id"]]
        category_rows.append(
            {
                "id": category["id"],
                "name": category["name"],
                "before_amount": q_money(before_amount),
                "after_amount": q_money(after_amount),
                "before_weight": before_amount / portfolio.total_current,
                "after_weight": after_amount / final_total if final_total > ZERO else ZERO,
                "target_weight": target_weight,
                "before_deviation": before_amount / portfolio.total_current - target_weight,
                "after_deviation": after_amount / final_total - target_weight if final_total > ZERO else ZERO,
            }
        )

    return {
        "scenario": name,
        "currency": portfolio.currency,
        "initial_total": q_money(portfolio.total_current),
        "final_total": q_money(final_total),
        "incremental_cash": q_money(final_total - portfolio.total_current),
        "total_buy": q_money(total_buy),
        "total_sell": q_money(total_sell),
        "notes": portfolio.notes,
        "category_rows": category_rows,
        "leaf_rows": leaf_rows,
    }


def plans_for_portfolio(portfolio: Portfolio) -> dict[str, Any]:
    result: dict[str, Any] = {
        "currency": portfolio.currency,
        "notes": portfolio.notes,
        "scenarios": {},
    }
    if portfolio.incremental_cash is not None:
        result["scenarios"]["fixed_increment"] = scenario_fixed_increment(portfolio)
    else:
        result["scenarios"]["fixed_increment"] = {
            "scenario": "fixed_increment",
            "error": "未提供 incremental_cash，无法计算固定增量资金场景。"
        }
    result["scenarios"]["buy_only"] = scenario_buy_only(portfolio)
    result["scenarios"]["no_increment"] = scenario_no_increment(portfolio)
    return result


def render_plan_markdown(plan_bundle: dict[str, Any]) -> str:
    lines = ["# 调仓方案", ""]
    if plan_bundle.get("notes"):
        lines.append("## 提示")
        for note in plan_bundle["notes"]:
            lines.append(f"- {note}")
        lines.append("")

    titles = {
        "fixed_increment": "场景 1：固定增量资金",
        "buy_only": "场景 2：增量资金充裕，只买不卖",
        "no_increment": "场景 3：没有增量资金",
    }

    for key in ["fixed_increment", "buy_only", "no_increment"]:
        plan = plan_bundle["scenarios"][key]
        lines.append(f"## {titles[key]}")
        if plan.get("error"):
            lines.append(plan["error"])
            lines.append("")
            continue

        lines.append(f"- 初始总资产：{fmt_money(plan['initial_total'], plan['currency'])}")
        lines.append(f"- 调整后总资产：{fmt_money(plan['final_total'], plan['currency'])}")
        lines.append(f"- 新增资金：{fmt_money(plan['incremental_cash'], plan['currency'])}")
        lines.append(f"- 买入合计：{fmt_money(plan['total_buy'], plan['currency'])}")
        lines.append(f"- 卖出合计：{fmt_money(plan['total_sell'], plan['currency'])}")
        lines.append("")
        lines.append("### 大类对比")
        lines.append("| 大类 | 调整前金额 | 调整前占比 | 目标占比 | 调整后金额 | 调整后占比 | 调整后偏差 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in plan["category_rows"]:
            lines.append(
                f"| {row['name']} | {fmt_money(row['before_amount'], plan['currency'])} | {fmt_pct(row['before_weight'])} | "
                f"{fmt_pct(row['target_weight'])} | {fmt_money(row['after_amount'], plan['currency'])} | "
                f"{fmt_pct(row['after_weight'])} | {fmt_pct(row['after_deviation'])} |"
            )
        lines.append("")
        lines.append("### 买卖明细")
        lines.append("| 资产 | 所属大类 | 调整金额 | 调整后金额 | 调整后占比 |")
        lines.append("| --- | --- | ---: | ---: | ---: |")
        for row in plan["leaf_rows"]:
            if row["trade_amount"] == ZERO:
                continue
            lines.append(
                f"| {row['name']} | {row['category_name']} | {fmt_money(row['trade_amount'], plan['currency'])} | "
                f"{fmt_money(row['after_amount'], plan['currency'])} | {fmt_pct(row['after_weight'])} |"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_mermaid_pie(title: str, rows: list[dict[str, Any]], amount_key: str, currency: str) -> list[str]:
    lines = ["```mermaid", "pie showData", f'    title {title}']
    for row in rows:
        lines.append(f'    "{row["name"]}" : {q_money(row[amount_key])}')
    lines.append("```")
    lines.append("")
    return lines


def normalize_trade_id(portfolio: Portfolio, raw_id: str) -> str:
    if raw_id in {leaf.id for leaf in portfolio.leaves}:
        return raw_id

    for leaf in portfolio.leaves:
        short_id = leaf.id.split(":", 1)[1]
        if raw_id == short_id:
            return leaf.id
    raise ValueError(f"confirmed_trades 中存在未知 id: {raw_id}")


def plan_from_confirmed_trades(portfolio: Portfolio) -> dict[str, Any]:
    trades: dict[str, Decimal] = {}
    for raw_id, amount in portfolio.confirmed_trades.items():
        trades[normalize_trade_id(portfolio, raw_id)] = amount
    final_total = portfolio.total_current + sum_decimals(list(trades.values()))
    return make_plan("confirmed", portfolio, trades, final_total)


def render_report_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# 调仓报告",
        "",
        f"- 方案：{plan['scenario']}",
        f"- 调整前总资产：{fmt_money(plan['initial_total'], plan['currency'])}",
        f"- 调整后总资产：{fmt_money(plan['final_total'], plan['currency'])}",
        f"- 买入合计：{fmt_money(plan['total_buy'], plan['currency'])}",
        f"- 卖出合计：{fmt_money(plan['total_sell'], plan['currency'])}",
        "",
        "## 大类调整前后",
        "",
        "| 大类 | 调整前金额 | 调整前占比 | 目标占比 | 调整后金额 | 调整后占比 | 调整前偏差 | 调整后偏差 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in plan["category_rows"]:
        lines.append(
            f"| {row['name']} | {fmt_money(row['before_amount'], plan['currency'])} | {fmt_pct(row['before_weight'])} | "
            f"{fmt_pct(row['target_weight'])} | {fmt_money(row['after_amount'], plan['currency'])} | "
            f"{fmt_pct(row['after_weight'])} | {fmt_pct(row['before_deviation'])} | {fmt_pct(row['after_deviation'])} |"
        )
    lines.append("")
    lines.append("## 调整前配置")
    lines.append("")
    lines.extend(render_mermaid_pie("调整前", plan["category_rows"], "before_amount", plan["currency"]))
    lines.append("## 调整后配置")
    lines.append("")
    lines.extend(render_mermaid_pie("调整后", plan["category_rows"], "after_amount", plan["currency"]))
    lines.extend(
        [
            "## 买卖明细",
            "",
            "| 资产 | 所属大类 | 调整前金额 | 买入/卖出金额 | 调整后金额 | 调整后占比 |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in plan["leaf_rows"]:
        if row["trade_amount"] == ZERO:
            continue
        lines.append(
            f"| {row['name']} | {row['category_name']} | {fmt_money(row['before_amount'], plan['currency'])} | "
            f"{fmt_money(row['trade_amount'], plan['currency'])} | {fmt_money(row['after_amount'], plan['currency'])} | "
            f"{fmt_pct(row['after_weight'])} |"
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="资产配置组合调仓计算器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="生成三种调仓方案")
    plan_parser.add_argument("--input", required=True, type=Path)
    plan_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    plan_parser.add_argument("--output", type=Path)

    report_parser = subparsers.add_parser("report", help="生成调仓报告")
    report_parser.add_argument("--input", required=True, type=Path)
    report_parser.add_argument("--scenario", choices=["fixed_increment", "buy_only", "no_increment", "confirmed"], default="confirmed")
    report_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    portfolio = load_portfolio(args.input)

    if args.command == "plan":
        plan_bundle = plans_for_portfolio(portfolio)
        if args.format == "json":
            output_text = json.dumps(plan_bundle, ensure_ascii=False, indent=2, default=str) + "\n"
        else:
            output_text = render_plan_markdown(plan_bundle)
    else:
        if args.scenario == "confirmed":
            if not portfolio.confirmed_trades:
                raise ValueError("scenario=confirmed 需要在输入文件中提供 confirmed_trades")
            plan = plan_from_confirmed_trades(portfolio)
        elif args.scenario == "fixed_increment":
            plan = scenario_fixed_increment(portfolio)
        elif args.scenario == "buy_only":
            plan = scenario_buy_only(portfolio)
        else:
            plan = scenario_no_increment(portfolio)
        output_text = render_report_markdown(plan)

    if getattr(args, "output", None):
        args.output.write_text(output_text, encoding="utf-8")
    else:
        print(output_text, end="")


if __name__ == "__main__":
    main()
