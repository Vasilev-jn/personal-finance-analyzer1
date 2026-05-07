import csv
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from finance_app.domain import Operation, OperationType, Vault
from finance_app.utils import parse_decimal


def _push_skip(report: Dict[str, object], row_index: int, reason: str) -> None:
    report["skipped"] = int(report.get("skipped", 0)) + 1
    errors = report.setdefault("errors", [])
    if isinstance(errors, list) and len(errors) < 30:
        errors.append({"row": row_index, "reason": reason})


def _detect_operation_type(type_raw: str) -> OperationType:
    value = (type_raw or "").strip().lower()
    if value.startswith("income") or value.startswith("\u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d"):
        return OperationType.INCOME
    if value.startswith("transfer") or "\u043f\u0435\u0440\u0435\u0432\u043e\u0434" in value:
        return OperationType.TRANSFER
    return OperationType.EXPENSE


def import_alfa_csv(
    vault: Vault,
    path: str,
    file_id: str,
    report: Optional[Dict[str, object]] = None,
) -> List[Operation]:
    operations: List[Operation] = []
    report_ref = report if report is not None else {}
    report_ref.setdefault("source", "alfa")
    report_ref.setdefault("rows_total", 0)
    report_ref.setdefault("skipped", 0)
    report_ref.setdefault("errors", [])
    with open(path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        for row_index, row in enumerate(reader, start=2):
            report_ref["rows_total"] = int(report_ref["rows_total"]) + 1
            op_date_raw = row.get("operationDate") or row.get("\ufeffoperationDate")
            if not op_date_raw:
                _push_skip(report_ref, row_index, "missing operationDate")
                continue

            try:
                op_date = datetime.strptime(op_date_raw, "%d.%m.%Y").date()
            except Exception:
                _push_skip(report_ref, row_index, "invalid operationDate")
                continue

            raw_amount = parse_decimal(row.get("amount"))
            op_type = _detect_operation_type(row.get("type") or "")
            amount = raw_amount.copy_abs() if op_type != OperationType.EXPENSE else -raw_amount.copy_abs()
            account_id = vault.ensure_account(
                bank="alfa",
                name=row.get("accountName") or "\u0421\u0447\u0451\u0442",
                number=row.get("accountNumber"),
            )
            description = row.get("comment") or row.get("merchant") or ""
            operation = Operation(
                id=str(uuid4()),
                account_id=account_id,
                bank="alfa",
                date=op_date,
                amount=amount,
                currency=(row.get("currency") or "").upper() or "RUR",
                type=op_type,
                description=description,
                merchant=row.get("merchant") or None,
                mcc=(row.get("mcc") or "").strip() or None,
                bank_category=row.get("category") or None,
                source_file_id=file_id,
            )
            if vault.add_operation(operation):
                operations.append(operation)
            else:
                report_ref["duplicates"] = int(report_ref.get("duplicates", 0)) + 1
                _push_skip(report_ref, row_index, "duplicate operation")

    report_ref["imported"] = len(operations)
    return operations
