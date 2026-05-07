import csv
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from finance_app.domain import Operation, OperationType, Vault
from finance_app.utils import parse_decimal


DATE_COLS = ["\u0414\u0430\u0442\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438", "operationDate"]
AMOUNT_COLS = ["\u0421\u0443\u043c\u043c\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438", "amount"]
CURRENCY_COLS = ["\u0412\u0430\u043b\u044e\u0442\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438", "currency"]
DESC_COLS = ["\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435", "description"]
CATEGORY_COLS = ["\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f", "category"]
CARD_COLS = ["\u041d\u043e\u043c\u0435\u0440 \u043a\u0430\u0440\u0442\u044b", "card"]
MCC_COLS = ["MCC", "mcc"]


def _push_skip(report: Dict[str, object], row_index: int, reason: str) -> None:
    report["skipped"] = int(report.get("skipped", 0)) + 1
    errors = report.setdefault("errors", [])
    if isinstance(errors, list) and len(errors) < 30:
        errors.append({"row": row_index, "reason": reason})


def _repair_utf8_mojibake(value: str) -> str:
    repaired = value
    for _ in range(2):
        try:
            candidate = repaired.encode("cp1251").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if candidate == repaired:
            break
        repaired = candidate
    return repaired


def _normalize_header(value: Optional[str]) -> str:
    header = (value or "").strip().lstrip("\ufeff")
    if not header:
        return ""
    return _repair_utf8_mojibake(header)


def _normalize_row(row: Dict[Optional[str], Optional[str]]) -> Dict[str, str]:
    return {
        _normalize_header(key): value or ""
        for key, value in row.items()
        if key is not None
    }


def _first_value(row: Dict[str, str], keys: List[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return ""


def import_tinkoff_csv(
    vault: Vault,
    path: str,
    file_id: str,
    report: Optional[Dict[str, object]] = None,
) -> List[Operation]:
    operations: List[Operation] = []
    report_ref = report if report is not None else {}
    report_ref.setdefault("source", "tinkoff")
    report_ref.setdefault("rows_total", 0)
    report_ref.setdefault("skipped", 0)
    report_ref.setdefault("errors", [])
    with open(path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp, delimiter=";")
        for row_index, row in enumerate(reader, start=2):
            report_ref["rows_total"] = int(report_ref["rows_total"]) + 1
            normalized_row = _normalize_row(row)
            date_raw = _first_value(normalized_row, DATE_COLS)
            if not date_raw:
                _push_skip(report_ref, row_index, "missing date")
                continue

            try:
                op_date = datetime.strptime(date_raw, "%d.%m.%Y %H:%M:%S").date()
            except Exception:
                _push_skip(report_ref, row_index, "invalid date format")
                continue

            raw_amount = parse_decimal(_first_value(normalized_row, AMOUNT_COLS))
            op_type = OperationType.EXPENSE if raw_amount < 0 else OperationType.INCOME
            card = _first_value(normalized_row, CARD_COLS) or "Tinkoff"
            account_id = vault.ensure_account(bank="tinkoff", name="Tinkoff", number=card)
            operation = Operation(
                id=str(uuid4()),
                account_id=account_id,
                bank="tinkoff",
                date=op_date,
                amount=raw_amount,
                currency=(_first_value(normalized_row, CURRENCY_COLS) or "").upper() or "RUB",
                type=op_type,
                description=_first_value(normalized_row, DESC_COLS) or "",
                merchant=_first_value(normalized_row, DESC_COLS) or None,
                mcc=(_first_value(normalized_row, MCC_COLS) or "").strip() or None,
                bank_category=_first_value(normalized_row, CATEGORY_COLS) or None,
                source_file_id=file_id,
            )
            if vault.add_operation(operation):
                operations.append(operation)
            else:
                report_ref["duplicates"] = int(report_ref.get("duplicates", 0)) + 1
                _push_skip(report_ref, row_index, "duplicate operation")

    report_ref["imported"] = len(operations)
    return operations
