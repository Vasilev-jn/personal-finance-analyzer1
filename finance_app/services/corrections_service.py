from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from finance_app.domain import Operation, Vault


def find_operation(vault: Vault, operation_id: str) -> Optional[Operation]:
    for op in vault.operations:
        if op.id == operation_id:
            return op
    return None


def apply_manual_category(
    vault: Vault,
    operation_id: str,
    category_id: str,
    reason: str = "",
) -> dict | None:
    operation = find_operation(vault, operation_id)
    if not operation:
        return None

    change = {
        "id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation_id": operation.id,
        "old_category_id": operation.category_id,
        "new_category_id": category_id,
        "old_source": operation.categorization_source,
        "new_source": "manual",
        "reason": reason.strip(),
    }
    operation.category_id = category_id
    operation.categorization_source = "manual"
    return change


def undo_last_change(vault: Vault, corrections: List[dict]) -> dict | None:
    if not corrections:
        return None

    last = corrections.pop()
    operation = find_operation(vault, last.get("operation_id") or "")
    if operation:
        operation.category_id = last.get("old_category_id")
        operation.categorization_source = last.get("old_source")
    return last


def unknown_items(vault: Vault, limit: int = 300) -> List[dict]:
    items: List[dict] = []
    for op in vault.operations:
        if op.category_id and op.category_id != "base_unknown":
            continue
        items.append(
            {
                "id": op.id,
                "date": op.date.isoformat(),
                "bank": op.bank,
                "description": op.description,
                "merchant": op.merchant,
                "bank_category": op.bank_category,
                "amount": float(op.amount),
                "source": op.categorization_source,
            }
        )
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[:limit]
