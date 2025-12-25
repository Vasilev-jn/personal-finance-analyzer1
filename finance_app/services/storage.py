import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

from finance_app.domain import Account, Operation, OperationType, Vault


STATE_PATH = Path("data") / "vault_state.json"
PASS_PATH = Path("data") / "auth.json"


def ensure_state_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def serialize_operation(op: Operation) -> dict:
    return {
        "id": op.id,
        "account_id": op.account_id,
        "bank": op.bank,
        "date": op.date.isoformat(),
        "amount": str(op.amount),
        "currency": op.currency,
        "type": op.type.value,
        "description": op.description,
        "merchant": op.merchant,
        "mcc": op.mcc,
        "bank_category": op.bank_category,
        "category_id": op.category_id,
        "categorization_source": op.categorization_source,
        "source_file_id": op.source_file_id,
    }


def deserialize_operation(data: dict) -> Operation:
    return Operation(
        id=data["id"],
        account_id=data["account_id"],
        bank=data["bank"],
        date=datetime.fromisoformat(data["date"]).date(),
        amount=Decimal(data["amount"]),
        currency=data["currency"],
        type=OperationType(data["type"]),
        description=data.get("description") or "",
        merchant=data.get("merchant"),
        mcc=data.get("mcc"),
        bank_category=data.get("bank_category"),
        category_id=data.get("category_id"),
        categorization_source=data.get("categorization_source"),
        source_file_id=data.get("source_file_id"),
    )


def deserialize_account(data: dict) -> Account:
    if isinstance(data, Account):
        return data
    return Account(
        id=data.get("id") or "",
        bank=data.get("bank") or "",
        name=data.get("name") or "",
        number=data.get("number"),
    )


def save_state(vault: Vault, uploaded_files: List[dict]) -> None:
    ensure_state_dir()
    data = {
        "uploaded_files": uploaded_files,
        "accounts": {k: vars(v) for k, v in vault.accounts.items()},
        "operations": [serialize_operation(op) for op in vault.operations],
    }
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(vault: Vault) -> Tuple[List[dict], bool]:
    if not STATE_PATH.exists():
        return [], False
    content = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    uploaded_files = content.get("uploaded_files") or []
    accounts_raw = content.get("accounts") or {}
    vault.accounts = {acc_id: deserialize_account(acc_data) for acc_id, acc_data in accounts_raw.items()}
    vault.operations.clear()
    for op_data in content.get("operations", []):
        vault.operations.append(deserialize_operation(op_data))
    return uploaded_files, True


def new_file_id() -> str:
    return str(uuid4())


def load_password_hash() -> str:
    if not PASS_PATH.exists():
        return ""
    try:
        content = json.loads(PASS_PATH.read_text(encoding="utf-8"))
        return content.get("password_hash") or ""
    except Exception:
        return ""


def save_password_hash(password_hash: str) -> None:
    ensure_state_dir()
    PASS_PATH.write_text(json.dumps({"password_hash": password_hash}, ensure_ascii=False, indent=2), encoding="utf-8")
