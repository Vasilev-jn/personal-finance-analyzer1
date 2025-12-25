import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from finance_app.domain import Operation


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    lowered = value.lower().replace("ё", "е")
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def parse_decimal(value: Optional[str]) -> Decimal:
    if value is None:
        return Decimal("0")
    normalized = value.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not normalized:
        return Decimal("0")
    try:
        return Decimal(normalized)
    except Exception:
        return Decimal("0")


def build_feature_text(*parts: Optional[str]) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


@dataclass
class Features:
    text: str
    bank_category_norm: str
    merchant_norm: str
    mcc: Optional[str]
    amount_abs: Decimal
    bank: str


def build_features(operation: Operation) -> Features:
    bank_category_norm = normalize_text(operation.bank_category)
    merchant_norm = normalize_text(operation.merchant)
    text = normalize_text(
        build_feature_text(operation.description, operation.merchant, operation.bank_category)
    )
    return Features(
        text=text,
        bank_category_norm=bank_category_norm,
        merchant_norm=merchant_norm,
        mcc=(operation.mcc or "").strip() or None,
        amount_abs=abs(operation.amount),
        bank=normalize_text(operation.bank),
    )
