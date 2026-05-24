from datetime import date, timedelta
from decimal import Decimal
import io

import pytest
from openpyxl import Workbook
from sqlalchemy.exc import IntegrityError

import app as app_module
from finance_app.domain import Account, Vault
from finance_app.services import storage


class AuthenticatedClient:
    def __init__(self, raw_client, token: str, user_id: int):
        self.raw = raw_client
        self.token = token
        self.user_id = user_id

    def _headers(self, path: str, headers: dict | None = None) -> dict:
        merged = dict(headers or {})
        public_auth_paths = ("/api/auth/login", "/api/auth/register", "/api/auth/set")
        if not path.startswith(public_auth_paths):
            merged.setdefault("X-Auth-Token", self.token)
        return merged

    def get(self, path: str, **kwargs):
        kwargs["headers"] = self._headers(path, kwargs.get("headers"))
        return self.raw.get(path, **kwargs)

    def post(self, path: str, **kwargs):
        kwargs["headers"] = self._headers(path, kwargs.get("headers"))
        return self.raw.post(path, **kwargs)

    def put(self, path: str, **kwargs):
        kwargs["headers"] = self._headers(path, kwargs.get("headers"))
        return self.raw.put(path, **kwargs)

    def delete(self, path: str, **kwargs):
        kwargs["headers"] = self._headers(path, kwargs.get("headers"))
        return self.raw.delete(path, **kwargs)

    def seed_operation(self, op):
        app_module.vault.add_operation(op)
        account = Account(id=op.account_id, bank=op.bank, name="Test", number="123")
        with app_module.database.SessionLocal() as db:
            app_module.database.upsert_accounts(db, self.user_id, [account])
            try:
                app_module.database.insert_operations(db, self.user_id, [op])
                db.commit()
            except IntegrityError:
                db.rollback()
                app_module.database.update_operations(db, self.user_id, [op])
                db.commit()

    def seed_file(self, *, file_id: str, name: str, bank: str, count: int, content_hash: str | None = None):
        with app_module.database.SessionLocal() as db:
            app_module.database.add_uploaded_file(
                db,
                self.user_id,
                file_id,
                name,
                bank,
                count,
                content_hash or f"hash-{file_id}",
            )
            db.commit()

    def seed_correction(self, change: dict):
        app_module.corrections_log.append(change)
        with app_module.database.SessionLocal() as db:
            app_module.database.add_correction(db, self.user_id, change)
            db.commit()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STATE_PATH", tmp_path / "vault_state.json")
    monkeypatch.setattr(storage, "PASS_PATH", tmp_path / "auth.json")
    app_module.database.reset_db_for_tests(f"sqlite:///{tmp_path / 'moneymap-test.db'}")

    app_module.vault = Vault()
    app_module.vault.categories = app_module.CATEGORY_INDEX
    app_module.uploaded_files.clear()
    app_module.corrections_log.clear()
    app_module.pipeline.replace_custom_mappings([])
    app_module.user_profile = storage.normalize_profile({})
    app_module.user_profile_exists = False
    app_module.agent_llm_client = app_module.agent_service.AgentLLMClient()

    with app_module.app.test_client() as test_client:
        register = test_client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "12345"},
        )
        assert register.status_code == 200
        payload = register.get_json()
        yield AuthenticatedClient(test_client, payload["token"], payload["user"]["id"])


def test_manual_recategorization_and_undo(client, make_operation):
    op = make_operation(
        op_id="api-op-1",
        dt=date(2025, 2, 1),
        amount=Decimal("-200"),
        description="Manual recategorize me",
        category_id="base_unknown",
        categorization_source="fallback_stub",
    )
    client.seed_operation(op)

    resp = client.post(
        "/api/operations/api-op-1/category",
        json={"category_id": "base_food_fastfood", "reason": "user correction"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["operation"]["category_id"] == "base_food_fastfood"
    assert payload["operation"]["categorization_source"] == "manual"

    resp_undo = client.post("/api/corrections/undo")
    assert resp_undo.status_code == 200
    assert app_module.vault.operations[0].category_id == "base_unknown"


def test_custom_mapping_and_unknown_reclassify(client, make_operation):
    op = make_operation(
        op_id="api-op-2",
        dt=date(2025, 2, 2),
        amount=Decimal("-150"),
        bank="alfa",
        description="Needs custom mapping",
        bank_category="my custom category",
        category_id="base_unknown",
        categorization_source="fallback_stub",
    )
    client.seed_operation(op)

    resp = client.post(
        "/api/mappings/custom",
        json={"bank": "alfa", "bank_category": "my custom category", "base_id": "base_shopping_groceries"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["mapping"]["base_id"] == "base_shopping_groceries"
    assert app_module.vault.operations[0].category_id == "base_shopping_groceries"


def test_export_operations_json(client, make_operation):
    op = make_operation(
        op_id="api-op-3",
        dt=date(2025, 2, 3),
        amount=Decimal("-99"),
        description="Export me",
        category_id="base_food_fastfood",
    )
    client.seed_operation(op)

    resp = client.get("/api/export?kind=operations&format=json")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "api-op-3" in resp.get_data(as_text=True)


def test_auth_session_token_and_protected_endpoints(client):
    token = client.token

    resp_unauth = client.raw.get("/api/files")
    assert resp_unauth.status_code == 401

    resp_auth = client.raw.get("/api/files", headers={"X-Auth-Token": token})
    assert resp_auth.status_code == 200


def test_auth_logout_and_change_password(client):
    old_token = client.token

    wrong_change = client.raw.post(
        "/api/auth/change",
        json={"current_password": "wrong", "new_password": "67890"},
        headers={"X-Auth-Token": old_token},
    )
    assert wrong_change.status_code == 401
    assert wrong_change.get_json()["error"] == "invalid_current_password"

    changed = client.raw.post(
        "/api/auth/change",
        json={"current_password": "12345", "new_password": "67890"},
        headers={"X-Auth-Token": old_token},
    )
    assert changed.status_code == 200
    new_token = changed.get_json()["token"]
    assert new_token and new_token != old_token

    assert client.raw.get("/api/files", headers={"X-Auth-Token": old_token}).status_code == 401
    assert client.raw.get("/api/files", headers={"X-Auth-Token": new_token}).status_code == 200
    assert client.raw.post("/api/auth/login", json={"email": "test@example.com", "password": "12345"}).status_code == 401
    assert client.raw.post("/api/auth/login", json={"email": "test@example.com", "password": "67890"}).status_code == 200

    logout = client.raw.post("/api/auth/logout", headers={"X-Auth-Token": new_token})
    assert logout.status_code == 200
    assert client.raw.get("/api/files", headers={"X-Auth-Token": new_token}).status_code == 401


def test_users_do_not_see_each_other_operations_or_profile(client, make_operation):
    second_register = client.raw.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": "12345"},
    )
    assert second_register.status_code == 200
    second_token = second_register.get_json()["token"]

    client.seed_operation(
        make_operation(
            op_id="owner-food",
            dt=date(2025, 2, 10),
            amount=Decimal("-500"),
            description="Owner lunch",
            category_id="base_food_fastfood",
        )
    )
    client.put("/api/profile", json={"income": "120000", "priority": "Owner priority"})

    owner_ops = client.get("/api/operations").get_json()["items"]
    assert [item["id"] for item in owner_ops] == ["owner-food"]

    second_ops = client.raw.get("/api/operations", headers={"X-Auth-Token": second_token}).get_json()["items"]
    assert second_ops == []
    second_profile = client.raw.get("/api/profile", headers={"X-Auth-Token": second_token}).get_json()
    assert second_profile["exists"] is False


def test_profile_persists_in_backend_state(client):
    resp = client.put(
        "/api/profile",
        json={
            "name": "Vasya",
            "income": "120000",
            "payday": "10",
            "goal_title": "Подушка",
            "goal_amount": "100000",
            "goal_saved": "20000",
            "goal_deadline": "2026-12-31",
            "goals": "Хочу накопить 100000 рублей",
            "mode": "Коплю",
            "priority": "Накопить подушку",
            "tone": "Прямой",
        },
    )
    assert resp.status_code == 200
    profile = resp.get_json()["profile"]
    assert profile["income"] == "120000"
    assert profile["goal_title"] == "Подушка"
    assert profile["goal_amount"] == "100000"
    assert profile["goal_saved"] == "20000"
    assert profile["goal_deadline"] == "2026-12-31"
    assert profile["goals"] == "Хочу накопить 100000 рублей"

    resp_get = client.get("/api/profile")
    assert resp_get.status_code == 200
    assert resp_get.get_json()["exists"] is True
    assert resp_get.get_json()["profile"]["priority"] == "Накопить подушку"


def test_agent_uses_profile_for_local_analytical_fallback(client):
    payday = (date.today() + timedelta(days=3)).day
    client.put(
        "/api/profile",
        json={
            "income": "120000",
            "payday": str(payday),
            "goal_title": "Подушка",
            "goal_amount": "100000",
            "goal_saved": "20000",
            "goals": "",
            "mode": "Коплю",
            "priority": "Накопить подушку",
            "tone": "Мягкий",
        },
    )

    resp = client.post("/api/agent-answer", json={"question": "Сколько можно тратить в день до зарплаты?"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "analytical"
    assert payload["source"] == "local_calculation"
    assert "дневной лимит" in payload["answer"]
    assert "Подушка" in payload["answer"]
    assert "80 000" in payload["answer"]


def test_agent_expense_answer_excludes_transfers(client, make_operation):
    client.seed_operation(
        make_operation(
            op_id="food-op",
            dt=date.today(),
            amount=Decimal("-100"),
            description="Lunch",
            category_id="base_food_fastfood",
        )
    )
    client.seed_operation(
        make_operation(
            op_id="transfer-op",
            dt=date.today(),
            amount=Decimal("-10000"),
            description="Transfer to own account",
            category_id="base_transfer_out",
        )
    )

    resp = client.post("/api/agent-answer", json={"question": "Куда ушло больше всего денег?"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "factual"
    assert payload["source"] == "local"
    assert "100" in payload["answer"]
    assert "10 000" not in payload["answer"]
    assert "Перевод" not in payload["answer"]


def test_agent_greeting_does_not_trigger_financial_report_or_llm(client):
    class FakeLLM:
        model = "fake-model"

        def __init__(self):
            self.calls = 0

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.calls += 1
            return "LLM financial report"

    fake = FakeLLM()
    app_module.agent_llm_client = fake

    resp = client.post("/api/agent-answer", json={"question": "привет"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "conversation"
    assert payload["source"] == "local"
    assert payload["model"] is None
    assert fake.calls == 0
    assert "конкретные вопросы" in payload["answer"]
    assert "Доходы:" not in payload["answer"]
    assert "Расходы:" not in payload["answer"]


def test_agent_transfer_answer_uses_separate_transfer_bucket(client, make_operation):
    client.seed_operation(
        make_operation(
            op_id="food-op",
            dt=date.today(),
            amount=Decimal("-100"),
            description="Lunch",
            category_id="base_food_fastfood",
        )
    )
    client.seed_operation(
        make_operation(
            op_id="transfer-op",
            dt=date.today(),
            amount=Decimal("-10000"),
            description="Transfer to own account",
            category_id="base_transfer_out",
        )
    )

    resp = client.post("/api/agent-answer", json={"question": "Покажи переводы"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "factual"
    assert payload["source"] == "local"
    assert "10 000" in payload["answer"]
    assert "не входят в расходы" in payload["answer"]


def test_analytics_and_operations_expose_subscriptions(client, make_operation):
    for idx, dt in enumerate([date(2025, 1, 5), date(2025, 2, 5), date(2025, 3, 5)], start=1):
        client.seed_operation(
            make_operation(
                op_id=f"netflix-{idx}",
                dt=dt,
                amount=Decimal("-399"),
                description="Netflix monthly",
                merchant="Netflix",
                category_id="base_entertainment_online_video",
            )
        )
    client.seed_operation(
        make_operation(
            op_id="music-once",
            dt=date(2025, 3, 6),
            amount=Decimal("-199"),
            description="Music once",
            merchant="Music",
            category_id="base_entertainment_music",
        )
    )

    analytics = client.get("/api/analytics?exclude_transfers=true").get_json()
    subscriptions = analytics["subscriptions"]

    assert subscriptions[0]["key"] == "netflix"
    assert subscriptions[0]["operations_count"] == 3

    ops = client.get("/api/operations?type=expense&subscription_key=netflix").get_json()["items"]
    assert [op["id"] for op in ops] == ["netflix-3", "netflix-2", "netflix-1"]


def test_agent_subscription_question_stays_local(client, make_operation):
    class RaisingLLM:
        model = "should-not-be-used"

        def __init__(self):
            self.called = False

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.called = True
            raise AssertionError("subscription answer should stay local")

    fake = RaisingLLM()
    app_module.agent_llm_client = fake
    client.put("/api/profile", json={"income": "100000"})
    for idx, dt in enumerate([date(2025, 1, 5), date(2025, 2, 5), date(2025, 3, 5)], start=1):
        client.seed_operation(
            make_operation(
                op_id=f"netflix-agent-{idx}",
                dt=dt,
                amount=Decimal("-399"),
                description="Netflix monthly",
                merchant="Netflix",
                category_id="base_entertainment_online_video",
            )
        )

    resp = client.post("/api/agent-answer", json={"question": "Сколько я трачу на подписки?"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "analytical"
    assert payload["source"] == "local_calculation"
    assert fake.called is False
    assert "Netflix" in payload["answer"]
    assert "399" in payload["answer"]


def test_agent_budget_question_skips_llm_and_uses_question_goal(client, make_operation):
    class RaisingLLM:
        model = "should-not-be-used"

        def __init__(self):
            self.called = False

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.called = True
            raise AssertionError("budget calculation should stay local")

    fake = RaisingLLM()
    app_module.agent_llm_client = fake
    payday = (date.today() + timedelta(days=5)).day
    client.put(
        "/api/profile",
        json={
            "income": "120000",
            "payday": str(payday),
            "goals": "",
            "mode": "Коплю",
            "priority": "Снизить расходы",
            "tone": "Прямой",
        },
    )
    client.seed_operation(
        make_operation(
            op_id="current-month-food",
            dt=date.today(),
            amount=Decimal("-2000"),
            description="Current month food",
            category_id="base_food_fastfood",
        )
    )

    resp = client.post(
        "/api/agent-answer",
        json={"question": "Сколько можно тратить в день до зарплаты, если я хочу накопить 100000 рублей?"},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "analytical"
    assert payload["source"] == "local_calculation"
    assert fake.called is False
    assert "100 000" in payload["answer"]
    assert "2 000" in payload["answer"]


def test_agent_goal_question_stays_local(client, make_operation):
    class RaisingLLM:
        model = "should-not-be-used"

        def __init__(self):
            self.called = False

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.called = True
            raise AssertionError("goal planning should stay local")

    fake = RaisingLLM()
    app_module.agent_llm_client = fake
    deadline = (date.today() + timedelta(days=90)).isoformat()
    client.put(
        "/api/profile",
        json={
            "income": "120000",
            "payday": "15",
            "goal_title": "Подушка",
            "goal_amount": "100000",
            "goal_saved": "25000",
            "goal_deadline": deadline,
            "tone": "Прямой",
        },
    )
    client.seed_operation(
        make_operation(
            op_id="goal-food",
            dt=date.today(),
            amount=Decimal("-20000"),
            description="Current month food",
            category_id="base_food_fastfood",
        )
    )

    resp = client.post("/api/agent-answer", json={"question": "Почему я не успеваю накопить цель?"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "analytical"
    assert payload["source"] == "local_calculation"
    assert fake.called is False
    assert "Подушка" in payload["answer"]
    assert "75 000" in payload["answer"]
    assert "Нужно откладывать" in payload["answer"]


def test_agent_forecast_question_stays_local(client, make_operation):
    class RaisingLLM:
        model = "should-not-be-used"

        def __init__(self):
            self.called = False

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.called = True
            raise AssertionError("forecast should stay local")

    fake = RaisingLLM()
    app_module.agent_llm_client = fake
    payday = (date.today() + timedelta(days=5)).day
    client.put("/api/profile", json={"income": "100000", "payday": str(payday)})
    client.seed_operation(
        make_operation(
            op_id="forecast-food",
            dt=date.today(),
            amount=Decimal("-20000"),
            description="Current month food",
            category_id="base_food_fastfood",
        )
    )

    resp = client.post("/api/agent-answer", json={"question": "Хватит ли мне до зарплаты?"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "analytical"
    assert payload["source"] == "local_calculation"
    assert fake.called is False
    assert "Точного прогноза" in payload["answer"]
    assert "до зарплаты" in payload["answer"].lower()


def test_agent_anomaly_question_stays_local(client, make_operation):
    class RaisingLLM:
        model = "should-not-be-used"

        def __init__(self):
            self.called = False

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.called = True
            raise AssertionError("anomaly scan should stay local")

    fake = RaisingLLM()
    app_module.agent_llm_client = fake
    client.seed_operation(
        make_operation(
            op_id="anomaly-food",
            dt=date.today(),
            amount=Decimal("-900"),
            description="Fast food",
            category_id="base_food_fastfood",
        )
    )
    client.seed_operation(
        make_operation(
            op_id="anomaly-taxi",
            dt=date.today(),
            amount=Decimal("-100"),
            description="Taxi",
            category_id="base_transport_taxi",
        )
    )

    resp = client.post("/api/agent-answer", json={"question": "Есть аномалии в расходах?"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["tier"] == "analytical"
    assert payload["source"] == "local_calculation"
    assert fake.called is False
    assert "сигналы" in payload["answer"]
    assert "900" in payload["answer"]


def test_agent_sends_profile_context_to_llm_for_analytical_query(client):
    class FakeLLM:
        model = "fake-model"

        def __init__(self):
            self.messages = []

        def is_ready(self):
            return True

        def complete(self, messages, max_tokens=900):
            self.messages = messages
            return "LLM ответ с учётом профиля"

    fake = FakeLLM()
    app_module.agent_llm_client = fake
    client.put(
        "/api/profile",
        json={
            "income": "90000",
            "payday": "15",
            "goals": "Хочу накопить 100000 рублей",
            "priority": "Снизить расходы",
            "tone": "Прямой",
        },
    )

    resp = client.post(
        "/api/agent-answer",
        json={"question": "Проанализируй мои траты и предложи стратегию оптимизации"},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["source"] == "llm"
    assert payload["model"] == "fake-model"
    prompt = fake.messages[-1]["content"]
    assert "Хочу накопить 100000 рублей" in prompt
    assert "\"income\":\"90000\"" in prompt


def test_import_returns_report_with_skipped_rows(client):
    csv_data = "\n".join(
        [
            "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
            "01.12.2025,Main,123,income,1000,RUB,Salary,Employer,,Salary",
            "bad-date,Main,123,income,1000,RUB,Broken,Employer,,Salary",
            ",Main,123,income,1000,RUB,Missing date,Employer,,Salary",
        ]
    )
    resp = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(csv_data.encode("utf-8")), "alfa.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["imported"] == 1
    assert payload["import_report"]["rows_total"] == 3
    assert payload["import_report"]["skipped"] == 2


def test_import_rejects_wrong_file_format_with_clear_message(client):
    resp = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(b"%PDF-1.4"), "statement.pdf")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["error"] == "unsupported_file_format"
    assert "CSV" in payload["message"]
    assert len(app_module.uploaded_files) == 0
    assert len(app_module.vault.operations) == 0


def test_import_rejects_file_without_operations_with_clear_message(client):
    empty_csv = "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category\n".encode("utf-8")

    resp = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(empty_csv), "empty.csv")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["error"] == "no_operations_found"
    assert "не найдено операций" in payload["message"]
    assert len(app_module.uploaded_files) == 0
    assert len(app_module.vault.operations) == 0


def test_import_rejects_corrupted_file_with_clear_message(client):
    resp = client.post(
        "/api/import",
        data={"bank": "sber", "file": (io.BytesIO(b"not an xlsx file"), "broken.xlsx")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["error"] == "file_parse_failed"
    assert "Не удалось прочитать файл" in payload["message"]
    assert "Excel" in payload["message"]
    assert len(app_module.uploaded_files) == 0
    assert len(app_module.vault.operations) == 0


def test_import_rejects_same_file_content(client):
    csv_data = "\n".join(
        [
            "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
            "01.12.2025,Main,123,income,1000,RUB,Salary,Employer,,Salary",
        ]
    ).encode("utf-8")

    first = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(csv_data), "first.csv")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(csv_data), "renamed.csv")},
        content_type="multipart/form-data",
    )

    assert duplicate.status_code == 409
    payload = duplicate.get_json()
    assert payload["error"] == "duplicate_file"
    assert payload["duplicate_file"]["name"] == "first.csv"
    assert len(app_module.uploaded_files) == 1
    assert len(app_module.vault.operations) == 1


def test_import_skips_duplicate_operations_inside_same_file(client):
    row = "01.12.2025,Main,123,income,1000,RUB,Salary,Employer,,Salary"
    csv_data = "\n".join(
        [
            "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
            row,
            row,
        ]
    ).encode("utf-8")

    resp = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(csv_data), "same-file-duplicates.csv")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["imported"] == 1
    assert payload["import_report"]["duplicates"] == 1
    assert len(app_module.uploaded_files) == 1
    assert len(app_module.vault.operations) == 1


def test_same_file_content_can_be_imported_by_different_users(client):
    csv_data = "\n".join(
        [
            "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
            "01.12.2025,Main,123,income,1000,RUB,Salary,Employer,,Salary",
        ]
    ).encode("utf-8")
    second_register = client.raw.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": "12345"},
    )
    assert second_register.status_code == 200
    second_token = second_register.get_json()["token"]

    first = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(csv_data), "first.csv")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200

    second = client.raw.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(csv_data), "second.csv")},
        content_type="multipart/form-data",
        headers={"X-Auth-Token": second_token},
    )
    assert second.status_code == 200
    assert second.get_json()["imported"] == 1


def test_import_rejects_same_operations_from_different_file_content(client):
    first_csv = "\n".join(
        [
            "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
            "01.12.2025,Main,123,income,1000,RUB,Salary,Employer,,Salary",
        ]
    ).encode("utf-8")
    second_csv = "\n".join(
        [
            "operationDate,accountName,accountNumber,type,amount,currency,comment,merchant,mcc,category",
            "01.12.2025,Main,123,income,1000.00,RUB,Salary,Employer,,Salary",
            "",
        ]
    ).encode("utf-8")

    first = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(first_csv), "first.csv")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200

    duplicate_ops = client.post(
        "/api/import",
        data={"bank": "alfa", "file": (io.BytesIO(second_csv), "second.csv")},
        content_type="multipart/form-data",
    )

    assert duplicate_ops.status_code == 409
    payload = duplicate_ops.get_json()
    assert payload["error"] == "duplicate_operations"
    assert payload["import_report"]["duplicates"] == 1
    assert len(app_module.uploaded_files) == 1
    assert len(app_module.vault.operations) == 1


def test_import_sber_xlsx_via_api(client):
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
    payload_file = io.BytesIO()
    workbook.save(payload_file)
    payload_file.seek(0)

    resp = client.post(
        "/api/import",
        data={"bank": "sber", "file": (payload_file, "sber.xlsx")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["imported"] == 1
    assert payload["import_report"]["source"] == "sber"
    assert app_module.vault.operations[0].bank == "sber"


def test_delete_file_refreshes_derived_state(client, make_operation):
    op_deleted = make_operation(
        op_id="op-delete-me",
        dt=date(2025, 3, 1),
        amount=Decimal("-100"),
        description="Deleted file op",
        category_id="base_unknown",
        source_file_id="file-delete",
    )
    op_kept = make_operation(
        op_id="op-keep-me",
        dt=date(2025, 3, 2),
        amount=Decimal("-40"),
        description="Kept file op",
        category_id="base_food_fastfood",
        source_file_id="file-keep",
    )
    client.seed_operation(op_deleted)
    client.seed_operation(op_kept)
    client.seed_file(file_id="file-delete", name="delete.csv", bank="alfa", count=1)
    client.seed_file(file_id="file-keep", name="keep.csv", bank="alfa", count=1)
    client.seed_correction({"operation_id": "op-delete-me", "reason": "old correction"})
    app_module.pipeline._track_unmapped("alfa", "old category")

    resp = client.delete("/api/files/file-delete")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["removed_operations"] == 1
    assert [op.id for op in app_module.vault.operations] == ["op-keep-me"]
    assert app_module.corrections_log == []
    assert app_module.pipeline.unmapped_summary() == []
    assert payload["files"] == [{"id": "file-keep", "name": "keep.csv", "bank": "alfa", "count": 1}]

    analytics = client.get("/api/analytics?exclude_transfers=true").get_json()
    assert analytics["totals"]["expense"] == 40.0
    assert analytics["unknown"] == 0
