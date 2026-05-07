import csv
import json
from io import StringIO
from typing import Iterable, List

from finance_app.category_tree import CATEGORY_INDEX
from finance_app.domain import Operation


def operations_rows(operations: Iterable[Operation]) -> List[dict]:
    rows: List[dict] = []
    for op in operations:
        cat = CATEGORY_INDEX.get(op.category_id) if op.category_id else None
        rows.append(
            {
                "id": op.id,
                "date": op.date.isoformat(),
                "bank": op.bank,
                "amount": float(op.amount),
                "currency": op.currency,
                "type": op.type.value,
                "description": op.description,
                "merchant": op.merchant or "",
                "mcc": op.mcc or "",
                "bank_category": op.bank_category or "",
                "category_id": op.category_id or "",
                "category_name": cat.name if cat else "",
                "categorization_source": op.categorization_source or "",
                "source_file_id": op.source_file_id or "",
            }
        )
    return rows


def json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def csv_text(rows: List[dict]) -> str:
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
