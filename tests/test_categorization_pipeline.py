from decimal import Decimal

from finance_app.domain import OperationType
from finance_app.services.categorization import CategorizationPipeline


class DummyMLModel:
    def __init__(self, prediction: str | None, ready: bool = True):
        self.prediction = prediction
        self.ready = ready
        self.calls = 0

    def is_ready(self) -> bool:
        return self.ready

    def predict(self, operation):
        self.calls += 1
        return self.prediction


class DummyLLM:
    def __init__(self, prediction: str | None, ready: bool = True):
        self.prediction = prediction
        self.ready = ready
        self.calls = 0

    def is_ready(self) -> bool:
        return self.ready

    def predict(self, operation):
        self.calls += 1
        return self.prediction

    def status(self):
        return None


def test_rule_precedence_over_ml_and_llm(make_operation):
    op = make_operation(
        op_id="rule-1",
        description="Salary payment",
        op_type=OperationType.INCOME,
        amount=Decimal("1000"),
    )
    ml = DummyMLModel(prediction="base_income_other")
    llm = DummyLLM(prediction="base_travel_other")
    pipeline = CategorizationPipeline(ml_model=ml, llm_categorizer=llm)
    category = pipeline.categorize(op)
    assert category == "base_income_salary"
    assert op.categorization_source.startswith("rule")
    assert ml.calls == 0
    assert llm.calls == 0


def test_mapping_applied_before_models(make_operation):
    op = make_operation(
        op_id="map-1",
        description="Marketplace",
        merchant="OZON",
        bank_category="ozon",
    )
    pipeline = CategorizationPipeline()
    category = pipeline.categorize(op)
    assert category == "base_shopping_marketplace"
    assert op.categorization_source in {"mapping", "rule: marketplace merchant"}


def test_ml_model_prediction_is_used(make_operation):
    op = make_operation(
        op_id="ml-1",
        description="Unmapped expense",
        merchant="Some shop",
        bank_category="unknown",
    )
    ml = DummyMLModel(prediction="base_food_fastfood", ready=True)
    pipeline = CategorizationPipeline(ml_model=ml)
    category = pipeline.categorize(op)
    assert category == "base_food_fastfood"
    assert op.categorization_source == "ml_model"
    assert ml.calls == 1


def test_llm_prediction_used_when_ml_not_ready(make_operation):
    op = make_operation(
        op_id="llm-1",
        description="LLM category guess",
        merchant="Vendor",
        bank_category="unknown",
    )
    ml = DummyMLModel(prediction=None, ready=False)
    llm = DummyLLM(prediction="base_travel_other", ready=True)
    pipeline = CategorizationPipeline(ml_model=ml, llm_categorizer=llm)
    category = pipeline.categorize(op)
    assert category == "base_travel_other"
    assert op.categorization_source == "llm"
    assert llm.calls == 1


def test_fallback_stub_when_nothing_matches(make_operation):
    op = make_operation(
        op_id="fallback-1",
        description="Unknown expense",
        merchant="Vendor",
        bank_category="",
        amount=Decimal("-20"),
        op_type=OperationType.EXPENSE,
    )
    pipeline = CategorizationPipeline()
    category = pipeline.categorize(op)
    assert category == "base_unknown"
    assert op.categorization_source == "fallback_stub"
