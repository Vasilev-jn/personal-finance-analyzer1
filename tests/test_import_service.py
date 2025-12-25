from pathlib import Path

from finance_app.domain import OperationType, Vault
from finance_app.services import import_service


class DummyPipeline:
    def __init__(self):
        self.calls = 0

    def categorize(self, operation):
        self.calls += 1
        operation.category_id = operation.category_id or "base_dummy"
        operation.categorization_source = "dummy"
        return operation.category_id


def test_import_alfa_and_tinkoff(tmp_path):
    vault = Vault()
    pipeline = DummyPipeline()

    alfa_csv = tmp_path / "alfa.csv"
    alfa_csv.write_text(
        "\n".join(
            [
                "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
                "01.12.2025,Main,123,income,1000,RUB,Salary,Employer,,Salary",
                "02.12.2025,Main,123,transfer,200,RUB,Transfer,ATM,,Cash",
            ]
        ),
        encoding="utf-8",
    )

    imported = import_service.import_alfa_file_into_vault(vault, pipeline, str(alfa_csv), "file-1")
    assert imported == 2
    assert pipeline.calls == 1  # transfer operation skipped
    assert any(op.category_id == "base_topup" for op in vault.operations if op.type == OperationType.TRANSFER)

    tink_csv = tmp_path / "tinkoff.csv"
    date_col = "Дата операции"
    amount_col = "Сумма операции"
    currency_col = "Валюта операции"
    desc_col = "Описание"
    cat_col = "Категория"
    card_col = "Номер карты"

    tink_csv.write_text(
        "\n".join(
            [
                f"{date_col};{amount_col};{currency_col};{desc_col};{cat_col};MCC;{card_col}",
                f"01.12.2025 10:00:00;-150;RUB;Taxi ride;Transport;4121;5555",
                f"02.12.2025 12:00:00;500;RUB;Salary;Income;;5555",
            ]
        ),
        encoding="utf-8",
    )

    imported_tink = import_service.import_tinkoff_file_into_vault(vault, pipeline, str(tink_csv), "file-2")
    assert imported_tink == 2
    assert pipeline.calls == 3  # two more categorized
    assert len(vault.operations) == 4
