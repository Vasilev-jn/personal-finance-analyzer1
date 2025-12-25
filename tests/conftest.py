from datetime import date
from decimal import Decimal

import pytest

from finance_app.category_tree import CATEGORY_INDEX
from finance_app.domain import Account, Operation, OperationType, Vault


@pytest.fixture
def make_operation():
    def _make(
        *,
        op_id: str = "op-1",
        account_id: str = "acc-1",
        bank: str = "alfa",
        dt: date = date(2025, 1, 1),
        amount: Decimal = Decimal("-100"),
        currency: str = "RUB",
        op_type: OperationType = OperationType.EXPENSE,
        description: str = "",
        merchant: str | None = None,
        mcc: str | None = None,
        bank_category: str | None = None,
        category_id: str | None = None,
        categorization_source: str | None = None,
        source_file_id: str | None = None,
    ) -> Operation:
        return Operation(
            id=op_id,
            account_id=account_id,
            bank=bank,
            date=dt,
            amount=amount,
            currency=currency,
            type=op_type,
            description=description,
            merchant=merchant,
            mcc=mcc,
            bank_category=bank_category,
            category_id=category_id,
            categorization_source=categorization_source,
            source_file_id=source_file_id,
        )

    return _make


@pytest.fixture
def sample_vault(make_operation):
    vault = Vault()
    vault.categories = CATEGORY_INDEX
    op = make_operation()
    vault.accounts[op.account_id] = Account(id=op.account_id, bank=op.bank, name="Test", number="123")
    vault.add_operation(op)
    return vault
