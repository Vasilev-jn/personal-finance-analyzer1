from datetime import date
from decimal import Decimal

from finance_app.domain import Operation, OperationType
from finance_app.rules import apply_rules
from finance_app.utils import Features


def test_salary_rule_has_priority():
    op = Operation(
        id="op-salary",
        account_id="acc",
        bank="alfa",
        date=date(2025, 1, 1),
        amount=Decimal("1000"),
        currency="RUB",
        type=OperationType.INCOME,
        description="Salary for November",
        merchant=None,
        mcc=None,
        bank_category=None,
    )
    features = Features(
        text="salary payment",
        bank_category_norm="",
        merchant_norm="",
        mcc=None,
        amount_abs=Decimal("1000"),
        bank="alfa",
    )
    result = apply_rules(op, features)
    assert result is not None
    assert result[0] == "base_income_salary"


def test_already_service_category_is_preserved():
    op = Operation(
        id="op-service",
        account_id="acc",
        bank="alfa",
        date=date(2025, 1, 2),
        amount=Decimal("-50"),
        currency="RUB",
        type=OperationType.EXPENSE,
        description="",
        merchant=None,
        mcc=None,
        bank_category=None,
        category_id="base_transfer_out",
    )
    features = Features(
        text="",
        bank_category_norm="",
        merchant_norm="",
        mcc=None,
        amount_abs=Decimal("50"),
        bank="alfa",
    )
    result = apply_rules(op, features)
    assert result == ("base_transfer_out", "rule: already service")
