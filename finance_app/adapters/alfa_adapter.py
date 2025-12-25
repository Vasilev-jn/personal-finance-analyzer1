import csv
from datetime import datetime
from typing import List
from uuid import uuid4

from finance_app.domain import Operation, OperationType, Vault
from finance_app.utils import parse_decimal


def import_alfa_csv(vault: Vault, path: str, file_id: str) -> List[Operation]:
  operations: List[Operation] = []
  # utf-8-sig BOM, поэтому берём поле operationDate и \ufeffoperationDate
  with open(path, newline="", encoding="utf-8-sig") as fp:
    reader = csv.DictReader(fp)
    for row in reader:
      # пропускаем строки без даты
      op_date_raw = row.get("operationDate") or row.get("\ufeffoperationDate")
      if not op_date_raw:
        continue

      raw_amount = parse_decimal(row.get("amount"))
      type_raw = (row.get("type") or "").lower()

      op_type = OperationType.EXPENSE
      if type_raw.startswith("попол") or "пополн" in type_raw:
        op_type = OperationType.TRANSFER
      elif type_raw.startswith("рїр?рїр?р>р?"):  # legacy encoding for "пополн"
        op_type = OperationType.TRANSFER
      elif "transfer" in type_raw:
        op_type = OperationType.TRANSFER
      elif type_raw.startswith("income"):
        op_type = OperationType.INCOME

      amount = raw_amount if op_type != OperationType.EXPENSE else -raw_amount
      op_date = datetime.strptime(op_date_raw, "%d.%m.%Y").date()
      account_id = vault.ensure_account(
        bank="alfa",
        name=row.get("accountName") or "Счёт",
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
      vault.add_operation(operation)
      operations.append(operation)
  return operations
