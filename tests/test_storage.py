from datetime import date
from decimal import Decimal

from finance_app.domain import Account, Vault
from finance_app.services import storage


def test_save_and_load_state(tmp_path, make_operation, monkeypatch):
    state_path = tmp_path / "vault_state.json"
    pass_path = tmp_path / "auth.json"
    # isolate test data
    monkeypatch.setattr(storage, "STATE_PATH", state_path)
    monkeypatch.setattr(storage, "PASS_PATH", pass_path)

    vault = Vault()
    account = Account(id="acc-1", bank="alfa", name="Primary", number="1234")
    vault.accounts[account.id] = account
    op = make_operation(
        op_id="stored-1",
        account_id=account.id,
        bank=account.bank,
        dt=date(2025, 1, 5),
        amount=Decimal("-50"),
        description="Groceries",
        bank_category="Groceries",
        merchant="Store",
    )
    vault.add_operation(op)

    uploaded = [{"id": "file-1", "name": "ops.csv"}]
    storage.save_state(vault, uploaded)

    new_vault = Vault()
    files_loaded, has_state = storage.load_state(new_vault)
    assert has_state is True
    assert files_loaded == uploaded
    assert new_vault.accounts[account.id].name == "Primary"
    assert len(new_vault.operations) == 1
    assert new_vault.operations[0].description == "Groceries"

    storage.save_password_hash("secret")
    assert storage.load_password_hash() == "secret"
