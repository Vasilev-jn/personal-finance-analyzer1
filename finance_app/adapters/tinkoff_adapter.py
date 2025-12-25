import csv
from datetime import datetime
from typing import List
from uuid import uuid4

from finance_app.domain import Operation, OperationType, Vault
from finance_app.utils import parse_decimal


def import_tinkoff_csv(vault: Vault, path: str, file_id: str) -> List[Operation]:
    operations: List[Operation] = []
    with open(path, newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp, delimiter=";")
        for row in reader:
            if not row.get("Дата операции"):
                continue
            raw_amount = parse_decimal(row.get("Сумма операции"))
            op_type = OperationType.EXPENSE if raw_amount < 0 else OperationType.INCOME
            amount = raw_amount
            op_date = datetime.strptime(row.get("Дата операции"), "%d.%m.%Y %H:%M:%S").date()
            card = row.get("Номер карты") or "Tinkoff"
            account_id = vault.ensure_account(bank="tinkoff", name="Tinkoff", number=card)
            operation = Operation(
                id=str(uuid4()),
                account_id=account_id,
                bank="tinkoff",
                date=op_date,
                amount=amount,
                currency=(row.get("Валюта операции") or "").upper() or "RUB",
                type=op_type,
                description=row.get("Описание") or "",
                merchant=row.get("Описание") or None,
                mcc=(row.get("MCC") or "").strip() or None,
                bank_category=row.get("Категория") or None,
                source_file_id=file_id,
            )
            vault.add_operation(operation)
            operations.append(operation)
    return operations
