from decimal import Decimal

import pytest
from openpyxl import Workbook

from finance_app.adapters.vtb_adapter import _parse_vtb_text_rows
from finance_app.domain import OperationType, Vault
from finance_app.services import import_service


TINKOFF_DATE_COL = "\u0414\u0430\u0442\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438"
TINKOFF_AMOUNT_COL = "\u0421\u0443\u043c\u043c\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438"
TINKOFF_CURRENCY_COL = "\u0412\u0430\u043b\u044e\u0442\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438"
TINKOFF_DESC_COL = "\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435"
TINKOFF_CATEGORY_COL = "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f"
TINKOFF_CARD_COL = "\u041d\u043e\u043c\u0435\u0440 \u043a\u0430\u0440\u0442\u044b"


class DummyPipeline:
    def __init__(self):
        self.calls = 0

    def categorize(self, operation):
        self.calls += 1
        operation.category_id = operation.category_id or "base_dummy"
        operation.categorization_source = "dummy"
        return operation.category_id


def _mojibake_utf8_as_cp1251(value: str, rounds: int) -> str:
    broken = value
    for _ in range(rounds):
        broken = broken.encode("utf-8").decode("cp1251")
    return broken


def _write_tinkoff_csv(
    path,
    *,
    encoding: str = "utf-8",
    header_rounds: int = 0,
    header_rounds_by_col=None,
) -> None:
    header_cols = [
        TINKOFF_DATE_COL,
        TINKOFF_AMOUNT_COL,
        TINKOFF_CURRENCY_COL,
        TINKOFF_DESC_COL,
        TINKOFF_CATEGORY_COL,
        "MCC",
        TINKOFF_CARD_COL,
    ]
    header = ";".join(
        _mojibake_utf8_as_cp1251(
            col,
            header_rounds_by_col.get(col, header_rounds) if header_rounds_by_col else header_rounds,
        )
        if col != "MCC"
        else col
        for col in header_cols
    )
    path.write_text(
        "\n".join(
            [
                header,
                "01.12.2025 10:00:00;-150;RUB;Taxi ride;Transport;4121;5555",
                "02.12.2025 12:00:00;500;RUB;Salary;Income;;5555",
            ]
        ),
        encoding=encoding,
    )


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
    _write_tinkoff_csv(tink_csv, encoding="utf-8-sig")

    imported_tink = import_service.import_tinkoff_file_into_vault(vault, pipeline, str(tink_csv), "file-2")
    assert imported_tink == 2
    assert pipeline.calls == 3  # two more categorized
    assert len(vault.operations) == 4


def test_import_alfa_russian_operation_types(tmp_path):
    vault = Vault()
    pipeline = DummyPipeline()
    alfa_csv = tmp_path / "alfa-ru.csv"
    alfa_csv.write_text(
        "\n".join(
            [
                "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
                "01.12.2025,Main,123,\u0421\u043f\u0438\u0441\u0430\u043d\u0438\u0435,150,RUB,Purchase,Shop,5411,\u041f\u0440\u043e\u0434\u0443\u043a\u0442\u044b",
                "02.12.2025,Main,123,\u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435,1000,RUB,Topup,Sender,,\u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f",
            ]
        ),
        encoding="utf-8",
    )

    imported = import_service.import_alfa_file_into_vault(vault, pipeline, str(alfa_csv), "file-ru")

    assert imported == 2
    assert [op.type for op in vault.operations] == [OperationType.EXPENSE, OperationType.INCOME]
    assert [op.amount for op in vault.operations] == [pytest.approx(-150), pytest.approx(1000)]


def test_import_tinkoff_repairs_mojibake_headers(tmp_path):
    vault = Vault()
    pipeline = DummyPipeline()
    tink_csv = tmp_path / "tinkoff-mojibake.csv"

    _write_tinkoff_csv(tink_csv, header_rounds=1)

    imported = import_service.import_tinkoff_file_into_vault(vault, pipeline, str(tink_csv), "file-mojibake")
    assert imported == 2
    assert pipeline.calls == 2
    assert [op.description for op in vault.operations] == ["Taxi ride", "Salary"]


def test_import_tinkoff_repairs_multi_pass_mojibake_headers(tmp_path):
    vault = Vault()
    pipeline = DummyPipeline()
    tink_csv = tmp_path / "tinkoff-multi-pass.csv"

    _write_tinkoff_csv(
        tink_csv,
        header_rounds_by_col={
            TINKOFF_DATE_COL: 2,
            TINKOFF_AMOUNT_COL: 1,
            TINKOFF_CURRENCY_COL: 2,
            TINKOFF_DESC_COL: 2,
            TINKOFF_CATEGORY_COL: 2,
            TINKOFF_CARD_COL: 1,
        },
    )

    imported = import_service.import_tinkoff_file_into_vault(vault, pipeline, str(tink_csv), "file-multi-pass")
    assert imported == 2
    assert pipeline.calls == 2
    assert [op.bank_category for op in vault.operations] == ["Transport", "Income"]


def test_import_sber_xlsx(tmp_path):
    vault = Vault()
    pipeline = DummyPipeline()
    path = tmp_path / "sber.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "data"
    sheet.append(
        [
            "Номер",
            "Дата",
            "Тип операции",
            "Категория",
            "Сумма",
            "Валюта",
            "Сумма в рублях",
            "Описание",
            "Состояние",
            "Номер счета/карты списания",
        ]
    )
    sheet.append([1, "06 мая 2025, 14:00", "Расходы", "Супермаркеты", 484.57, "RUB", 484.57, "Shop", "Активная", "**** 3937"])
    sheet.append([2, "07 июн. 2025, 10:00", "Доходы", "Пополнения", 1000, "RUB", 1000, "Top up", "Активная", "**** 3937"])
    workbook.save(path)

    imported = import_service.import_sber_file_into_vault(vault, pipeline, str(path), "file-sber")

    assert imported == 2
    assert [op.bank for op in vault.operations] == ["sber", "sber"]
    assert [op.type for op in vault.operations] == [OperationType.EXPENSE, OperationType.INCOME]
    assert [op.amount for op in vault.operations] == [Decimal("-484.57"), Decimal("1000")]
    assert [op.bank_category for op in vault.operations] == ["Супермаркеты", "Пополнения"]
    assert pipeline.calls == 2


def test_parse_vtb_pdf_text_rows():
    report = {"rows_total": 0, "skipped": 0, "errors": []}
    text = "\n".join(
        [
            "Номер карты 220024******3264",
            "11.04.2026",
            "03:41:04 14.04.2026 -500.0 RUB -500.0 0.0 RUB Оплата товаров и услуг. BEELINE.",
            "12.04.2026",
            "03:41:04 14.04.2026 100.0 RUB 100.0 0.0 RUB Возврат. TEST.",
        ]
    )

    rows = _parse_vtb_text_rows(text, report)

    assert report["rows_total"] == 2
    assert report["skipped"] == 0
    assert len(rows) == 2
    assert rows[0]["amount"] == pytest.approx(-500)
    assert rows[0]["merchant"] == "BEELINE"
    assert rows[0]["bank_category"] == "Оплата товаров и услуг"
