from datetime import date
from decimal import Decimal

from finance_app.domain import OperationType
from finance_app.services.ml_model import SimpleMLModel


def _make_ml_operations(make_operation):
    return [
        make_operation(
            op_id="op-ml-1",
            description="Taxi ride",
            merchant="Yandex Taxi",
            bank_category="Taxi",
            mcc="4121",
            amount=Decimal("-500"),
            op_type=OperationType.EXPENSE,
            category_id="base_transport_taxi",
            dt=date(2025, 1, 1),
        ),
        make_operation(
            op_id="op-ml-2",
            description="Burger King",
            merchant="Burger",
            bank_category="Fastfood",
            mcc="5814",
            amount=Decimal("-300"),
            op_type=OperationType.EXPENSE,
            category_id="base_food_fastfood",
            dt=date(2025, 1, 2),
        ),
        make_operation(
            op_id="op-ml-3",
            description="Another taxi",
            merchant="Taxi",
            bank_category="Taxi",
            mcc="4121",
            amount=Decimal("-200"),
            op_type=OperationType.EXPENSE,
            category_id="base_transport_taxi",
            dt=date(2025, 1, 3),
        ),
        make_operation(
            op_id="op-ml-4",
            description="Coffee shop",
            merchant="Coffee",
            bank_category="Cafe",
            mcc="5812",
            amount=Decimal("-150"),
            op_type=OperationType.EXPENSE,
            category_id="base_food_fastfood",
            dt=date(2025, 1, 4),
        ),
    ]


def test_ml_model_fit_predict_and_save(tmp_path, make_operation):
    operations = _make_ml_operations(make_operation)
    model = SimpleMLModel()
    status = model.fit(operations)
    assert status.trained is True
    assert status.samples == len(operations)
    assert set(status.classes) >= {"base_transport_taxi", "base_food_fastfood"}
    assert model.is_ready()
    prediction = model.predict(operations[0])
    assert prediction in status.classes

    save_path = tmp_path / "model.pkl"
    model.save(save_path)
    reloaded = SimpleMLModel()
    assert reloaded.load(save_path) is True
    assert reloaded.is_ready()
    assert reloaded.predict(operations[1]) in status.classes
