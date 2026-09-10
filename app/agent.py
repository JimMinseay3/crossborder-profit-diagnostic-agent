import csv
import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from .models import RunRequest, Step
from .providers import enhance_result

MAX_FILE_BYTES = 3 * 1024 * 1024
REQUIRED = {"date", "order_id", "sku", "units", "revenue", "refunds", "cogs", "amazon_fees", "ad_spend", "shipping"}
MONEY_FIELDS = ["revenue", "refunds", "cogs", "amazon_fees", "ad_spend", "shipping"]


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value).strip() or "0")
    except InvalidOperation as exc:
        raise ValueError(f"无效金额：{value}") from exc


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _load(request: RunRequest, base_dir: Path) -> tuple[str, str]:
    if request.example:
        path = base_dir / "samples" / request.example
        if not path.is_file():
            raise ValueError("样例不存在。")
        return path.name, path.read_text(encoding="utf-8-sig")
    if not request.file_name or request.file_content is None:
        raise ValueError("请上传 CSV 或选择样例。")
    if not request.file_name.lower().endswith(".csv"):
        raise ValueError("利润诊断仅接受 CSV。")
    if len(request.file_content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("文件超过 3 MB 限制。")
    return request.file_name, request.file_content


def run(request: RunRequest, base_dir: Path) -> dict[str, Any]:
    source, content = _load(request, base_dir)
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError(f"CSV 缺少字段：{', '.join(sorted(REQUIRED - set(reader.fieldnames or [])))}")
    rows, warnings, missing_cost_orders = [], [], []
    for number, raw in enumerate(reader, start=2):
        if not raw.get("order_id") or not raw.get("sku"):
            warnings.append(f"第 {number} 行缺少订单或 SKU，已跳过。")
            continue
        if raw.get("cogs", "").strip() == "":
            missing_cost_orders.append(raw["order_id"])
        try:
            row = {**raw, "units": int(raw["units"])}
            row.update({field: _money(raw[field]) for field in MONEY_FIELDS})
        except (ValueError, TypeError) as exc:
            warnings.append(f"第 {number} 行数据无效，已跳过：{exc}")
            continue
        rows.append(row)
    if not rows:
        raise ValueError("没有可计算的有效订单。")

    totals = defaultdict(Decimal)
    by_sku: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    by_date: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for row in rows:
        profit = row["revenue"] - row["refunds"] - row["cogs"] - row["amazon_fees"] - row["ad_spend"] - row["shipping"]
        row["net_profit"] = profit
        for field in MONEY_FIELDS + ["net_profit"]:
            totals[field] += row[field]
            by_sku[row["sku"]][field] += row[field]
            by_date[row["date"]][field] += row[field]
        by_sku[row["sku"]]["units"] += Decimal(row["units"])

    def metrics(bucket: dict[str, Decimal], key: str) -> dict[str, Any]:
        revenue = bucket["revenue"]
        margin = bucket["net_profit"] / revenue * 100 if revenue else Decimal("0")
        return {
            "key": key,
            **{field: _round(bucket[field]) for field in MONEY_FIELDS + ["net_profit"]},
            "net_margin_pct": _round(margin),
            **({"units": int(bucket["units"])} if "units" in bucket else {}),
        }

    sku_metrics = [metrics(bucket, sku) for sku, bucket in sorted(by_sku.items())]
    date_metrics = [metrics(bucket, date) for date, bucket in sorted(by_date.items())]
    anomalies = []
    for item in sku_metrics:
        revenue = item["revenue"]
        if item["net_margin_pct"] < 10:
            anomalies.append({"sku": item["key"], "type": "low_margin", "severity": "high", "detail": f"净利率仅 {item['net_margin_pct']}%"})
        if revenue and item["refunds"] / revenue > 0.2:
            anomalies.append({"sku": item["key"], "type": "high_refund", "severity": "high", "detail": "退款超过收入的 20%"})
        if revenue and item["ad_spend"] / revenue > 0.3:
            anomalies.append({"sku": item["key"], "type": "high_ad_spend", "severity": "medium", "detail": "广告花费超过收入的 30%"})
        if revenue and item["amazon_fees"] / revenue > 0.25:
            anomalies.append({"sku": item["key"], "type": "high_platform_fee", "severity": "medium", "detail": "Amazon 费用超过收入的 25%"})
    for previous, current in zip(date_metrics, date_metrics[1:]):
        if current["revenue"] > previous["revenue"] and current["net_profit"] < previous["net_profit"]:
            anomalies.append({"date": current["key"], "type": "sales_up_profit_down", "severity": "high", "detail": f"相比 {previous['key']}，收入上升但净利润下降"})

    review_reasons = []
    if missing_cost_orders:
        review_reasons.append(f"{len(missing_cost_orders)} 个订单缺少 COGS，利润可能被高估。")
        warnings.append(review_reasons[-1])
    result = {
        "currency": "USD",
        "orders": len(rows),
        "totals": metrics(totals, "all"),
        "by_sku": sku_metrics,
        "by_date": date_metrics,
        "anomalies": anomalies,
        "actions": [
            "优先复核高退款 SKU 的商品与售后原因。",
            "将广告和平台费用异常与活动、类目费率逐项核对。",
            "补齐缺失成本后再用于经营决策。" if missing_cost_orders else "对低毛利 SKU 设置促销与广告预算护栏。",
        ],
        "calculation": "net_profit = revenue - refunds - cogs - amazon_fees - ad_spend - shipping",
    }
    result, provider, provider_warnings = enhance_result("Amazon profit anomaly diagnosis", result)
    warnings.extend(provider_warnings)
    return {
        "input_summary": f"{source}：{len(rows)} 个订单，{len(by_sku)} 个 SKU",
        "steps": [
            Step(name="数据校验", detail=f"读取 {len(rows)} 个有效订单。"),
            Step(name="确定性核算", detail="按订单、SKU 和日期复算 USD 净利润。"),
            Step(name="异常诊断", detail=f"识别 {len(anomalies)} 个异常信号。"),
        ],
        "evidence": [{"source": source, "type": "order_cost_ledger", "rows": len(rows)}],
        "result": result,
        "warnings": warnings,
        "confidence": 0.62 if missing_cost_orders else 0.94,
        "needs_human_review": bool(review_reasons),
        "review_reasons": review_reasons,
        "model_provider": provider,
    }

