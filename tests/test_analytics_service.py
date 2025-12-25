from datetime import date, timedelta
from decimal import Decimal

from finance_app.domain import OperationType, Vault
from finance_app.services import analytics_service


def _build_vault(make_operation) -> Vault:
    vault = Vault()
    ops = [
        make_operation(
            op_id="groceries",
            description="Groceries",
            merchant="Store",
            bank_category="Supermarket",
            amount=Decimal("-100"),
            op_type=OperationType.EXPENSE,
            category_id="base_shopping_groceries",
            dt=date(2025, 1, 1),
        ),
        make_operation(
            op_id="taxi",
            description="Taxi ride",
            merchant="Taxi",
            bank_category="Taxi",
            amount=Decimal("-50"),
            op_type=OperationType.EXPENSE,
            category_id="base_transport_taxi",
            dt=date(2025, 1, 2),
        ),
        make_operation(
            op_id="salary",
            description="Salary",
            merchant="Employer",
            bank_category="Salary",
            amount=Decimal("1000"),
            op_type=OperationType.INCOME,
            category_id="base_income_salary",
            dt=date(2025, 1, 5),
        ),
        make_operation(
            op_id="hotel",
            description="Hotel",
            merchant="Hotel",
            bank_category="Hotel",
            amount=Decimal("-300"),
            op_type=OperationType.EXPENSE,
            category_id="base_travel_hotels",
            dt=date(2025, 1, 10),
        ),
        make_operation(
            op_id="transfer",
            description="Transfer out",
            merchant="Transfer",
            bank_category="Transfer",
            amount=Decimal("-200"),
            op_type=OperationType.TRANSFER,
            category_id="base_transfer_out",
            dt=date(2025, 1, 12),
        ),
        make_operation(
            op_id="unknown",
            description="Unknown",
            merchant="Unknown",
            bank_category="Other",
            amount=Decimal("-20"),
            op_type=OperationType.EXPENSE,
            category_id=None,
            dt=date(2025, 1, 15),
        ),
    ]
    for op in ops:
        vault.add_operation(op)
    return vault


def test_filter_and_totals(make_operation):
    vault = _build_vault(make_operation)
    filtered = analytics_service.filter_operations(
        vault, start=date(2025, 1, 2), end=date(2025, 1, 31), exclude_transfers=True
    )
    assert all(op.category_id != "base_transfer_out" for op in filtered)
    totals = analytics_service.compute_totals(vault, filtered)
    assert totals["income"] == 1000.0
    assert totals["expense"] == 370.0  # transfer excluded, unknown included


def test_breakdowns(make_operation):
    vault = _build_vault(make_operation)
    sys_breakdown = analytics_service.breakdown_by_sys(vault)
    assert any(item["id"] == "sys_income" and item["amount"] > 0 for item in sys_breakdown)
    base_breakdown = analytics_service.breakdown_by_base(vault, limit=2)
    assert base_breakdown[0]["id"] in {"base_income_salary", "base_travel_hotels"}
    travel = analytics_service.travel_breakdown(vault)
    assert any(item["id"] == "base_travel_hotels" for item in travel)
    service = analytics_service.service_operations(vault)
    assert service["base_transfer_out"] == -200.0


def test_trends_and_unknown(make_operation):
    vault = _build_vault(make_operation)
    monthly = analytics_service.monthly_trend(vault)
    assert monthly == [{"label": "01.25", "income": 1000.0, "expense": 470.0}]
    weekly = analytics_service.weekly_trend(vault)
    assert weekly  # at least one bucket present
    daily = analytics_service.daily_trend(vault, days=0, operations=vault.operations)
    assert len(daily) == 5
    unknown_ops = analytics_service.unknown_operations(vault)
    assert len(unknown_ops) == 1


def test_export_and_hierarchy(make_operation):
    vault = _build_vault(make_operation)
    dataset = analytics_service.export_ml_dataset(vault)
    assert any(item["label"] == "base_income_salary" for item in dataset)
    hierarchy = analytics_service.base_by_sys_hierarchy(vault, per_sys_limit=3)
    assert hierarchy[0]["id"] == "sys_travel"
    assert hierarchy[0]["children"][0]["id"] == "base_travel_hotels"


def test_merchant_breakdown_and_quick_answers(make_operation):
    vault = _build_vault(make_operation)
    breakdown = analytics_service.merchant_breakdown(vault, "base_transport_taxi", op_type=OperationType.EXPENSE)
    assert breakdown[0]["merchant"] == "taxi"
    answers = analytics_service.quick_answers(
        vault, vault.operations, start=date(2025, 1, 1), end=date(2025, 1, 31)
    )
    assert answers["balance"]["expense"] == 470.0
    assert answers["top_expense_category"]["id"]
