from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from finance_app.category_tree import CATEGORY_INDEX, SERVICE_BASE_IDS, TRAVEL_BASE_IDS, find_parent_sys
from finance_app.domain import Operation, OperationType, Vault
from finance_app.utils import normalize_text


SUBSCRIPTION_BASE_IDS = {
    "base_entertainment_games",
    "base_entertainment_online_video",
    "base_entertainment_music",
    "base_entertainment_digital",
    "base_home_internet",
    "base_home_services",
    "base_health_fitness",
}

SUBSCRIPTION_TEXT_MARKERS = (
    "подпис",
    "subscription",
    "subscribe",
    "premium",
    "pro",
    "plus",
    "яндекс плюс",
    "yandex plus",
    "icloud",
    "netflix",
    "kinopoisk",
    "кинопоиск",
    "okko",
    "ivi",
    "wink",
    "spotify",
    "youtube",
)


def _select_ops(vault: Vault, operations: Optional[List[Operation]] = None) -> List[Operation]:
    return operations if operations is not None else vault.operations


def filter_operations(
    vault: Vault,
    start: Optional[date] = None,
    end: Optional[date] = None,
    exclude_transfers: bool = False,
    transfers_only: bool = False,
) -> List[Operation]:
    ops = []
    for op in vault.operations:
        if start and op.date < start:
            continue
        if end and op.date > end:
            continue
        if transfers_only and op.category_id not in SERVICE_BASE_IDS:
            continue
        if exclude_transfers and op.category_id in SERVICE_BASE_IDS:
            continue
        ops.append(op)
    return ops


def compute_totals(vault: Vault, operations: Optional[List[Operation]] = None) -> Dict[str, float]:
    ops = _select_ops(vault, operations)
    income = Decimal("0")
    expense = Decimal("0")
    for op in ops:
        if op.type == OperationType.INCOME:
            income += op.amount
        elif op.type == OperationType.EXPENSE:
            expense += abs(op.amount)
    return {
        "income": float(income),
        "expense": float(expense),
        "net": float(income - expense),
    }


def breakdown_by_sys(vault: Vault, operations: Optional[List[Operation]] = None) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    for op in ops:
        sys_cat = find_parent_sys(op.category_id) or "sys_unknown"
        value = op.amount if op.type == OperationType.INCOME else abs(op.amount) * -1
        totals[sys_cat] += value
    results = []
    for cid, amount in totals.items():
        cat = CATEGORY_INDEX.get(cid)
        results.append(
            {"id": cid, "name": cat.name if cat else cid, "amount": float(amount)}
        )
    results.sort(key=lambda x: x["amount"])
    return results


def breakdown_by_base(
    vault: Vault,
    limit: Optional[int] = None,
    op_type: Optional[OperationType] = None,
    operations: Optional[List[Operation]] = None,
) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    for op in ops:
        if op_type and op.type != op_type:
            continue
        base = op.category_id or "base_unknown"
        value = op.amount if op.type == OperationType.INCOME else abs(op.amount) * -1
        totals[base] += value
    results = []
    for cid, amount in totals.items():
        cat = CATEGORY_INDEX.get(cid)
        results.append({"id": cid, "name": cat.name if cat else cid, "amount": float(amount)})
    results.sort(key=lambda x: abs(x["amount"]), reverse=True)
    if limit:
        return results[:limit]
    return results


def travel_breakdown(vault: Vault, operations: Optional[List[Operation]] = None) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    for op in ops:
        if op.category_id in TRAVEL_BASE_IDS:
            value = op.amount if op.type == OperationType.INCOME else abs(op.amount) * -1
            totals[op.category_id] += value
    return [
        {"id": cid, "name": CATEGORY_INDEX[cid].name, "amount": float(amount)}
        for cid, amount in totals.items()
    ]


def service_operations(vault: Vault, operations: Optional[List[Operation]] = None) -> Dict[str, float]:
    ops = _select_ops(vault, operations)
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    for op in ops:
        if op.category_id in SERVICE_BASE_IDS:
            value = op.amount if op.type == OperationType.INCOME else abs(op.amount) * -1
            totals[op.category_id] += value
    return {cid: float(amount) for cid, amount in totals.items()}


def operation_subscription_key(op: Operation) -> str:
    source = normalize_text(op.merchant) or normalize_text(op.description)
    if not source:
        return ""
    return " ".join(part for part in source.split() if not part.isdigit())[:80]


def subscription_candidates(
    vault: Vault,
    operations: Optional[List[Operation]] = None,
    limit: int = 20,
) -> List[Dict[str, object]]:
    ops = [
        op
        for op in _select_ops(vault, operations)
        if op.type == OperationType.EXPENSE
        and op.category_id not in SERVICE_BASE_IDS
        and _looks_like_subscription_operation(op)
    ]
    groups: Dict[str, List[Operation]] = defaultdict(list)
    for op in ops:
        key = operation_subscription_key(op)
        if key:
            groups[key].append(op)

    results: List[Dict[str, object]] = []
    for key, items in groups.items():
        unique_dates = sorted({op.date for op in items})
        if len(unique_dates) < 2:
            continue

        amounts = [float(abs(op.amount)) for op in items]
        if not amounts:
            continue
        rounded_amounts = [round(amount) for amount in amounts]
        common_amount, common_count = Counter(rounded_amounts).most_common(1)[0]
        amount_stability = common_count / len(amounts)
        avg_amount = sum(amounts) / len(amounts)
        spread = (max(amounts) - min(amounts)) / avg_amount if avg_amount else 0
        amount_stable = amount_stability >= 0.6 or spread <= 0.2

        intervals = [(right - left).days for left, right in zip(unique_dates, unique_dates[1:])]
        median_interval = _median(intervals)
        interval_regular = (
            median_interval is not None
            and (6 <= median_interval <= 8 or 20 <= median_interval <= 45 or 85 <= median_interval <= 100)
        )
        if not (amount_stable and (interval_regular or len(items) >= 3)):
            continue

        monthly_amount = float(common_amount if common_count > 1 else avg_amount)
        if median_interval and 6 <= median_interval <= 8:
            monthly_amount *= 4.33
        elif median_interval and 85 <= median_interval <= 100:
            monthly_amount /= 3

        last_date = max(unique_dates)
        next_date = None
        if median_interval:
            next_date = date.fromordinal(last_date.toordinal() + int(round(median_interval)))
        category_id = Counter(op.category_id for op in items if op.category_id).most_common(1)
        category_id = category_id[0][0] if category_id else None
        category = CATEGORY_INDEX.get(category_id)
        last_op = max(items, key=lambda op: op.date)
        label = _subscription_label(items[0], key)
        results.append(
            {
                "key": key,
                "name": label,
                "amount": monthly_amount,
                "last_amount": float(abs(last_op.amount)),
                "operations_count": len(items),
                "first_date": min(unique_dates).isoformat(),
                "last_date": last_date.isoformat(),
                "next_estimated_date": next_date.isoformat() if next_date else None,
                "median_interval_days": median_interval,
                "category_id": category_id,
                "category_name": category.name if category else None,
            }
        )

    results.sort(key=lambda item: (float(item["amount"]), item["operations_count"]), reverse=True)
    return results[:limit]


def _subscription_label(op: Operation, key: str) -> str:
    return (op.merchant or op.description or key).strip() or key


def _looks_like_subscription_operation(op: Operation) -> bool:
    if op.category_id in SUBSCRIPTION_BASE_IDS:
        return True
    text = normalize_text(" ".join(part for part in (op.description, op.merchant, op.bank_category) if part))
    return any(marker in text for marker in SUBSCRIPTION_TEXT_MARKERS)


def _median(values: List[int]) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return float(sorted_values[mid])
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def monthly_trend(vault: Vault, operations: Optional[List[Operation]] = None) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    buckets: Dict[Tuple[int, int], Dict[str, Decimal]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0")}
    )
    for op in ops:
        bucket = (op.date.year, op.date.month)
        if op.type == OperationType.INCOME:
            buckets[bucket]["income"] += op.amount
        elif op.type == OperationType.EXPENSE:
            buckets[bucket]["expense"] += abs(op.amount)
    trend = []
    for (year, month), values in sorted(buckets.items()):
        trend.append(
            {
                "label": f"{month:02d}.{str(year)[2:]}",
                "income": float(values["income"]),
                "expense": float(values["expense"]),
            }
        )
    return trend


def weekly_trend(vault: Vault, operations: Optional[List[Operation]] = None) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    buckets: Dict[Tuple[int, int], Dict[str, Decimal]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0")}
    )
    for op in ops:
        bucket = (op.date.isocalendar().year, op.date.isocalendar().week)
        if op.type == OperationType.INCOME:
            buckets[bucket]["income"] += op.amount
        elif op.type == OperationType.EXPENSE:
            buckets[bucket]["expense"] += abs(op.amount)
    trend = []
    for (year, week), values in sorted(buckets.items()):
        trend.append(
            {
                "label": f"W{week:02d}.{str(year)[2:]}",
                "income": float(values["income"]),
                "expense": float(values["expense"]),
            }
        )
    return trend


def daily_trend(vault: Vault, days: int = 30, operations: Optional[List[Operation]] = None) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    buckets: Dict[date, Dict[str, Decimal]] = defaultdict(lambda: {"income": Decimal("0"), "expense": Decimal("0")})
    cutoff = None
    if days:
        cutoff = date.today().toordinal() - days
    for op in ops:
        if cutoff and op.date.toordinal() < cutoff:
            continue
        if op.type == OperationType.INCOME:
            buckets[op.date]["income"] += op.amount
        elif op.type == OperationType.EXPENSE:
            buckets[op.date]["expense"] += abs(op.amount)
    trend = []
    for d, values in sorted(buckets.items()):
        label = d.strftime("%d.%m")
        trend.append({"label": label, "income": float(values["income"]), "expense": float(values["expense"])})
    return trend


def unknown_operations(vault: Vault, operations: Optional[List[Operation]] = None) -> List[Operation]:
    ops = _select_ops(vault, operations)
    return [op for op in ops if not op.category_id or op.category_id == "base_unknown"]


def export_ml_dataset(vault: Vault) -> List[Dict[str, object]]:
    dataset: List[Dict[str, object]] = []
    for op in vault.operations:
        if not op.category_id:
            continue
        dataset.append(
            {
                "text": normalize_text(op.description),
                "merchant": normalize_text(op.merchant),
                "bank_category": normalize_text(op.bank_category),
                "mcc": op.mcc,
                "amount_abs": float(abs(op.amount)),
                "bank": op.bank,
                "label": op.category_id,
            }
        )
    return dataset


def base_by_sys_hierarchy(
    vault: Vault, per_sys_limit: int = 5, operations: Optional[List[Operation]] = None
) -> List[Dict[str, object]]:
    ops = _select_ops(vault, operations)
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    children: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    for op in ops:
        if op.type != OperationType.EXPENSE:
            continue
        sys_cat = find_parent_sys(op.category_id) or "sys_unknown"
        base_cat = op.category_id or "base_unknown"
        amount = abs(op.amount)
        totals[sys_cat] += amount
        children[sys_cat][base_cat] += amount

    results: List[Dict[str, object]] = []
    for sys_id, amount in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        sys_cat = CATEGORY_INDEX.get(sys_id)
        childs = []
        for base_id, child_amount in sorted(children[sys_id].items(), key=lambda x: x[1], reverse=True)[
            :per_sys_limit
        ]:
            cat = CATEGORY_INDEX.get(base_id)
            childs.append({"id": base_id, "name": cat.name if cat else base_id, "amount": float(child_amount)})
        results.append(
            {
                "id": sys_id,
                "name": sys_cat.name if sys_cat else sys_id,
                "amount": float(amount),
                "children": childs,
            }
        )
    return results


def merchant_breakdown(vault: Vault, base_id: str, limit: int = 10, op_type: Optional[OperationType] = None) -> List[Dict[str, object]]:
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    for op in vault.operations:
        if op_type and op.type != op_type:
            continue
        if op.category_id != base_id:
            continue
        merchant = normalize_text(op.merchant) or "unknown_merchant"
        totals[merchant] += abs(op.amount)
    items = []
    for merchant, amount in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]:
        items.append({"merchant": merchant, "amount": float(amount)})
    return items


def quick_answers(
    vault: Vault,
    operations: List[Operation],
    start: Optional[date],
    end: Optional[date],
) -> Dict[str, object]:
    expenses = [op for op in operations if op.type == OperationType.EXPENSE]
    incomes = [op for op in operations if op.type == OperationType.INCOME]

    def serialize_ops(ops: List[Operation]) -> List[Dict[str, object]]:
        return [
            {
                "date": op.date.isoformat(),
                "title": op.description or op.merchant or "операция",
                "amount": float(abs(op.amount)),
            }
            for op in ops
        ]

    top_exp = sorted(expenses, key=lambda o: abs(o.amount), reverse=True)[:5]
    top_inc = sorted(incomes, key=lambda o: abs(o.amount), reverse=True)[:5]

    totals_now = compute_totals(vault, operations)

    top_exp_cat = breakdown_by_base(vault, op_type=OperationType.EXPENSE, limit=1, operations=operations)
    top_inc_cat = breakdown_by_base(vault, op_type=OperationType.INCOME, limit=1, operations=operations)

    delta_exp = 0.0
    delta_inc = 0.0
    if start and end:
        delta_days = (end - start).days + 1
        prev_end = date.fromordinal(start.toordinal() - 1)
        prev_start = date.fromordinal(prev_end.toordinal() - delta_days + 1)
        prev_ops = filter_operations(vault, prev_start, prev_end, exclude_transfers=True)
        prev_totals = compute_totals(vault, prev_ops)
        delta_exp = totals_now["expense"] - prev_totals["expense"]
        delta_inc = totals_now["income"] - prev_totals["income"]

    return {
        "top_expenses": serialize_ops(top_exp),
        "top_incomes": serialize_ops(top_inc),
        "balance": totals_now,
        "top_expense_category": top_exp_cat[0] if top_exp_cat else None,
        "top_income_category": top_inc_cat[0] if top_inc_cat else None,
        "delta": {"expense": delta_exp, "income": delta_inc} if start and end else None,
    }
