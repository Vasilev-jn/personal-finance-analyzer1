from decimal import Decimal

from finance_app.domain import Vault
from finance_app.services import corrections_service


def test_apply_manual_and_undo(make_operation):
    vault = Vault()
    op = make_operation(
        op_id="op-1",
        amount=Decimal("-120"),
        description="Some expense",
        category_id="base_unknown",
        categorization_source="fallback_stub",
    )
    vault.add_operation(op)

    change = corrections_service.apply_manual_category(
        vault, "op-1", "base_shopping_groceries", reason="manual fix"
    )
    assert change is not None
    assert op.category_id == "base_shopping_groceries"
    assert op.categorization_source == "manual"
    assert change["old_category_id"] == "base_unknown"
    assert change["new_category_id"] == "base_shopping_groceries"

    log = [change]
    reverted = corrections_service.undo_last_change(vault, log)
    assert reverted is not None
    assert log == []
    assert op.category_id == "base_unknown"
    assert op.categorization_source == "fallback_stub"


def test_unknown_items_returns_only_unknown(make_operation):
    vault = Vault()
    unknown = make_operation(op_id="u1", category_id=None, description="Unknown")
    known = make_operation(op_id="k1", category_id="base_food_fastfood", description="Known")
    vault.add_operation(unknown)
    vault.add_operation(known)

    items = corrections_service.unknown_items(vault)
    assert len(items) == 1
    assert items[0]["id"] == "u1"
