# -*- coding: utf-8 -*-
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import uuid4

from pypdf import PdfReader

from finance_app.domain import Operation, OperationType, Vault
from finance_app.utils import parse_decimal


DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
DETAIL_RE = re.compile(
    r"^(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<processed>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<amount>[+-]?\d+(?:[.,]\d+)?)\s+"
    r"(?P<currency>[A-Z]{3})\s+"
    r"(?P<card_amount>[+-]?\d+(?:[.,]\d+)?)\s+"
    r"(?P<fee>[+-]?\d+(?:[.,]\d+)?)\s+"
    r"(?P<fee_currency>[A-Z]{3})\s+"
    r"(?P<description>.+)$"
)


def _push_skip(report: Dict[str, object], row_index: int, reason: str) -> None:
    report["skipped"] = int(report.get("skipped", 0)) + 1
    errors = report.setdefault("errors", [])
    if isinstance(errors, list) and len(errors) < 30:
        errors.append({"row": row_index, "reason": reason})


def _extract_card_number(text: str) -> str:
    match = re.search(r"Номер карты\s+([^\n]+)", text)
    return (match.group(1).strip() if match else "") or "VTB"


def _parse_description(description: str) -> tuple[str, Optional[str], Optional[str]]:
    cleaned = re.sub(r"\s+", " ", description).strip()
    cleaned = cleaned.strip(". ")
    if "." not in cleaned:
        return cleaned, cleaned or None, None
    category, merchant = cleaned.split(".", 1)
    category = category.strip() or None
    merchant = merchant.strip(" .") or None
    return cleaned, merchant, category


def _parse_vtb_text_rows(text: str, report: Dict[str, object]) -> List[dict]:
    rows: List[dict] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if not DATE_RE.match(line):
            index += 1
            continue

        report["rows_total"] = int(report.get("rows_total", 0)) + 1
        row_number = index + 1
        if index + 1 >= len(lines):
            _push_skip(report, row_number, "missing detail line")
            break

        detail = lines[index + 1]
        match = DETAIL_RE.match(detail)
        if not match:
            _push_skip(report, row_number, "invalid operation line")
            index += 1
            continue

        try:
            op_date = datetime.strptime(line, "%d.%m.%Y").date()
        except Exception:
            _push_skip(report, row_number, "invalid date")
            index += 2
            continue

        amount = parse_decimal(match.group("amount"))
        description, merchant, bank_category = _parse_description(match.group("description"))
        rows.append(
            {
                "date": op_date,
                "amount": amount,
                "currency": match.group("currency") or "RUB",
                "description": description,
                "merchant": merchant,
                "bank_category": bank_category,
            }
        )
        index += 2
    return rows


def import_vtb_pdf(
    vault: Vault,
    path: str,
    file_id: str,
    report: Optional[Dict[str, object]] = None,
) -> List[Operation]:
    operations: List[Operation] = []
    report_ref = report if report is not None else {}
    report_ref.setdefault("source", "vtb")
    report_ref.setdefault("rows_total", 0)
    report_ref.setdefault("skipped", 0)
    report_ref.setdefault("errors", [])

    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    account_number = _extract_card_number(text)
    account_id = vault.ensure_account(bank="vtb", name="ВТБ", number=account_number)

    for row in _parse_vtb_text_rows(text, report_ref):
        amount: Decimal = row["amount"]
        op_type = OperationType.INCOME if amount >= 0 else OperationType.EXPENSE
        operation = Operation(
            id=str(uuid4()),
            account_id=account_id,
            bank="vtb",
            date=row["date"],
            amount=amount,
            currency=(row["currency"] or "RUB").upper(),
            type=op_type,
            description=row["description"],
            merchant=row["merchant"],
            mcc=None,
            bank_category=row["bank_category"],
            source_file_id=file_id,
        )
        if vault.add_operation(operation):
            operations.append(operation)
        else:
            report_ref["duplicates"] = int(report_ref.get("duplicates", 0)) + 1
            report_ref["skipped"] = int(report_ref.get("skipped", 0)) + 1

    report_ref["imported"] = len(operations)
    return operations
