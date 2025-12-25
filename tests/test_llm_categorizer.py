from decimal import Decimal

from finance_app.services.llm_categorizer import LLMCategorizer


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def json(self):
        return self.payload


def test_not_ready_returns_none(make_operation):
    categorizer = LLMCategorizer(api_key=None, model=None)
    op = make_operation(description="Sample", merchant="Shop", bank_category="Other", amount=Decimal("-10"))
    assert categorizer.predict(op) is None


def test_parse_response_and_cache(monkeypatch, make_operation):
    categorizer = LLMCategorizer(api_key="key", model="model", api_url="http://test")
    payload = {"choices": [{"message": {"content": {"category_id": "base_transport_taxi"}}}]}
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(json)
        return DummyResponse(payload)

    monkeypatch.setattr("finance_app.services.llm_categorizer.requests.post", fake_post)

    op = make_operation(
        description="Taxi ride", merchant="Yandex Taxi", bank_category="Taxi", amount=Decimal("-300"), mcc="4121"
    )
    first = categorizer.predict(op)
    second = categorizer.predict(op)
    assert first == "base_transport_taxi"
    assert second == "base_transport_taxi"
    assert len(calls) == 1  # cache hit on second call

    data = {"choices": [{"message": {"content": '{"category": "base_food_fastfood"}'}}]}
    assert categorizer._parse_response(data) == "base_food_fastfood"
