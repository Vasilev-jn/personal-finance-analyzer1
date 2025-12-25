from datetime import date
from decimal import Decimal

from finance_app.domain import OperationType
from finance_app.utils import build_feature_text, build_features, normalize_text, parse_decimal


def test_normalize_text_and_parse_decimal():
    assert normalize_text("  Hello, World!  ") == "hello world"
    assert normalize_text(None) == ""
    assert parse_decimal("1 234,56") == Decimal("1234.56")
    assert parse_decimal("bad input") == Decimal("0")
    assert parse_decimal(None) == Decimal("0")


def test_build_feature_text():
    assert build_feature_text(" First ", "", None, "Second") == "First Second"


def test_build_features(make_operation):
    op = make_operation(
        description="Coffee purchase",
        merchant="Coffee Bar",
        bank_category="Cafe",
        mcc="5814",
        amount=Decimal("-120.5"),
        op_type=OperationType.EXPENSE,
        dt=date(2025, 1, 2),
    )
    features = build_features(op)
    assert "coffee" in features.text
    assert features.bank_category_norm == "cafe"
    assert features.merchant_norm == "coffee bar"
    assert features.mcc == "5814"
    assert features.amount_abs == Decimal("120.5")
