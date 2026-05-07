import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import uuid4

from finance_app.domain import Account, Operation, OperationType, Vault
from finance_app.services import security


STATE_PATH = Path("data") / "vault_state.json"
PASS_PATH = Path("data") / "auth.json"

DEFAULT_PROFILE = {
    "name": "",
    "currency": "RUB",
    "language": "ru",
    "timezone": "MSK (UTC+3)",
    "income": "",
    "payday": "",
    "mode": "Коплю",
    "goal_title": "",
    "goal_amount": "",
    "goal_saved": "",
    "goal_deadline": "",
    "goals": "",
    "priority": "Снизить расходы",
    "tone": "Мягкий",
}

_PROFILE_LIMITS = {
    "name": 80,
    "currency": 8,
    "language": 8,
    "timezone": 40,
    "income": 24,
    "payday": 2,
    "mode": 80,
    "goal_title": 120,
    "goal_amount": 24,
    "goal_saved": 24,
    "goal_deadline": 10,
    "goals": 5000,
    "priority": 80,
    "tone": 80,
}

_ALLOWED_CURRENCIES = {"RUB", "USD", "EUR"}
_ALLOWED_LANGUAGES = {"ru", "en"}
_ALLOWED_TIMEZONES = {"MSK (UTC+3)", "UTC"}
_ALLOWED_MODES = {"Коплю", "От зарплаты до зарплаты", "Инвестирую"}
_ALLOWED_PRIORITIES = {"Снизить расходы", "Увеличить остаток", "Накопить подушку"}
_ALLOWED_TONES = {"Мягкий", "Прямой", "Жёсткий коуч"}


@dataclass
class LoadedState:
    uploaded_files: List[dict] = field(default_factory=list)
    has_state: bool = False
    corrections: List[dict] = field(default_factory=list)
    custom_mappings: List[dict] = field(default_factory=list)
    profile: dict = field(default_factory=lambda: dict(DEFAULT_PROFILE))
    has_profile: bool = False


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


def _normalize_custom_mappings(raw: object) -> List[dict]:
    if not isinstance(raw, list):
        return []
    items: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        bank = (item.get("bank") or "").strip().lower()
        bank_category = (item.get("bank_category") or "").strip()
        base_id = (item.get("base_id") or "").strip()
        if not bank or not bank_category or not base_id:
            continue
        items.append({"bank": bank, "bank_category": bank_category, "base_id": base_id})
    return items


def normalize_profile(raw: object) -> dict:
    if not isinstance(raw, dict):
        return dict(DEFAULT_PROFILE)

    profile = dict(DEFAULT_PROFILE)
    for key, default in DEFAULT_PROFILE.items():
        value = raw.get(key, default)
        if value is None:
            value = ""
        value = str(value).strip()
        limit = _PROFILE_LIMITS.get(key)
        if limit:
            value = value[:limit]
        profile[key] = value

    if profile["currency"] not in _ALLOWED_CURRENCIES:
        profile["currency"] = DEFAULT_PROFILE["currency"]
    if profile["language"] not in _ALLOWED_LANGUAGES:
        profile["language"] = DEFAULT_PROFILE["language"]
    if profile["timezone"] not in _ALLOWED_TIMEZONES:
        profile["timezone"] = DEFAULT_PROFILE["timezone"]
    if profile["mode"] not in _ALLOWED_MODES:
        profile["mode"] = DEFAULT_PROFILE["mode"]
    if profile["priority"] not in _ALLOWED_PRIORITIES:
        profile["priority"] = DEFAULT_PROFILE["priority"]
    if profile["tone"] not in _ALLOWED_TONES:
        profile["tone"] = DEFAULT_PROFILE["tone"]

    try:
        income = float(profile["income"].replace(",", "."))
        profile["income"] = str(max(income, 0)).rstrip("0").rstrip(".")
    except Exception:
        profile["income"] = ""

    for money_key in ("goal_amount", "goal_saved"):
        try:
            value = float(profile[money_key].replace(",", "."))
            profile[money_key] = str(max(value, 0)).rstrip("0").rstrip(".")
        except Exception:
            profile[money_key] = ""

    try:
        payday = int(profile["payday"])
        profile["payday"] = str(payday) if 1 <= payday <= 31 else ""
    except Exception:
        profile["payday"] = ""

    try:
        if profile["goal_deadline"]:
            datetime.strptime(profile["goal_deadline"], "%Y-%m-%d")
    except Exception:
        profile["goal_deadline"] = ""

    return profile


def _load_state_payload(password_hash: str = "") -> dict | None:
    if not STATE_PATH.exists():
        return None

    raw = STATE_PATH.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None

    if isinstance(parsed, dict) and parsed.get("_enc") == "moneymap.v1":
        if not password_hash:
            return None
        return security.decrypt_json(raw, password_hash)

    if isinstance(parsed, dict):
        return parsed
    return None


def save_full_state(
    vault: Vault,
    uploaded_files: List[dict],
    corrections: List[dict] | None = None,
    custom_mappings: List[dict] | None = None,
    profile: dict | None = None,
    password_hash: str = "",
) -> None:
    ensure_state_dir()
    data = {
        "uploaded_files": uploaded_files,
        "accounts": {k: vars(v) for k, v in vault.accounts.items()},
        "operations": [serialize_operation(op) for op in vault.operations],
        "corrections": corrections or [],
        "custom_mappings": custom_mappings or [],
    }
    if profile is not None:
        data["profile"] = normalize_profile(profile)
    if password_hash:
        payload = security.encrypt_json(data, password_hash)
    else:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    STATE_PATH.write_text(payload, encoding="utf-8")


def load_full_state(vault: Vault, password_hash: str = "") -> LoadedState:
    payload = _load_state_payload(password_hash=password_hash)
    if payload is None:
        return LoadedState(has_state=False)

    uploaded_files = payload.get("uploaded_files") or []
    accounts_raw = payload.get("accounts") or {}
    vault.accounts = {acc_id: deserialize_account(acc_data) for acc_id, acc_data in accounts_raw.items()}
    vault.operations.clear()
    for op_data in payload.get("operations", []):
        vault.operations.append(deserialize_operation(op_data))

    corrections_raw = payload.get("corrections") or []
    corrections = [item for item in corrections_raw if isinstance(item, dict)]
    custom_mappings = _normalize_custom_mappings(payload.get("custom_mappings"))
    has_profile = isinstance(payload.get("profile"), dict)
    profile = normalize_profile(payload.get("profile"))
    return LoadedState(
        uploaded_files=uploaded_files,
        has_state=True,
        corrections=corrections,
        custom_mappings=custom_mappings,
        profile=profile,
        has_profile=has_profile,
    )


def save_state(vault: Vault, uploaded_files: List[dict]) -> None:
    save_full_state(vault, uploaded_files)


def load_state(vault: Vault) -> Tuple[List[dict], bool]:
    loaded = load_full_state(vault)
    return loaded.uploaded_files, loaded.has_state


def new_file_id() -> str:
    return str(uuid4())


def load_password_hash() -> str:
    payload = _load_auth_payload()
    return payload.get("password_hash") or ""


def save_password_hash(password_hash: str) -> None:
    payload = _load_auth_payload()
    payload["password_hash"] = password_hash
    _save_auth_payload(payload)


def load_password_record() -> dict | None:
    payload = _load_auth_payload()
    record = payload.get("password_record")
    if isinstance(record, dict):
        return record
    return None


def save_password_record(password_record: dict) -> None:
    payload = _load_auth_payload()
    payload["password_record"] = password_record
    _save_auth_payload(payload)


def _load_auth_payload() -> dict:
    if not PASS_PATH.exists():
        return {}
    try:
        content = json.loads(PASS_PATH.read_text(encoding="utf-8"))
        if isinstance(content, dict):
            return content
        return {}
    except Exception:
        return {}


def _save_auth_payload(payload: dict) -> None:
    ensure_state_dir()
    PASS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
