from pathlib import Path
from tempfile import NamedTemporaryFile
import os
import hashlib
from datetime import datetime, date

from flask import Flask, jsonify, render_template, request

from finance_app.category_tree import CATEGORY_INDEX
from finance_app.domain import Operation, OperationType
from finance_app.services import analytics_service, import_service
from finance_app.services.categorization import CategorizationPipeline
from finance_app.domain import Vault
from finance_app.services.ml_model import SimpleMLModel
from finance_app.services import storage
from finance_app.services.llm_categorizer import LLMCategorizer


BASE_DIR = Path(__file__).parent

app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "finance_app" / "static"),
    template_folder=str(BASE_DIR / "finance_app" / "templates"),
)

vault = Vault()
ml_model = SimpleMLModel()
llm_categorizer = LLMCategorizer(
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "allenai/olmo-3.1-32b-think:free",
    api_url=os.getenv("LLM_API_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/chat/completions",
)
pipeline = CategorizationPipeline(ml_model=ml_model, llm_categorizer=llm_categorizer)
vault.categories = CATEGORY_INDEX
uploaded_files: list = []
PASSWORD_HASH: str = storage.load_password_hash()

# путь для сохранения модели
MODEL_PATH = BASE_DIR / "models" / "expense_clf.pkl"

# при старте пробуем поднять сохранённое состояние
loaded_files, has_state = storage.load_state(vault)
if has_state:
    uploaded_files = loaded_files

# при старте пытаемся загрузить модель
ml_model.load(MODEL_PATH)


def serialize_operation(op: Operation) -> dict:
    return {
        "id": op.id,
        "date": op.date.isoformat(),
        "amount": float(op.amount),
        "currency": op.currency,
        "type": op.type.value,
        "description": op.description,
        "merchant": op.merchant,
        "bank": op.bank,
        "bank_category": op.bank_category,
        "category_id": op.category_id,
        "category_name": CATEGORY_INDEX.get(op.category_id).name
        if op.category_id and op.category_id in CATEGORY_INDEX
        else None,
        "categorization_source": op.categorization_source,
    }


def parse_date(val: str) -> date | None:
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except Exception:
        return None


@app.before_request
def require_auth():
    global PASSWORD_HASH
    # allow static and auth endpoints
    if request.path in {"/", "/favicon.ico"} or request.path.startswith("/static") or request.path.startswith("/api/auth"):
        return None
    if not PASSWORD_HASH:
        return None
    token = request.headers.get("X-Auth-Token")
    if token != PASSWORD_HASH:
        return jsonify({"error": "unauthorized"}), 401


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/auth/status")
def api_auth_status():
    return jsonify({"password_set": bool(PASSWORD_HASH)})


@app.route("/api/auth/set", methods=["POST"])
def api_auth_set():
    global PASSWORD_HASH
    if PASSWORD_HASH:
        return jsonify({"error": "already_set"}), 400
    data = request.get_json() or {}
    password = (data.get("password") or "").strip()
    if len(password) < 4:
        return jsonify({"error": "too_short"}), 400
    PASSWORD_HASH = hashlib.sha256(password.encode("utf-8")).hexdigest()
    storage.save_password_hash(PASSWORD_HASH)
    return jsonify({"token": PASSWORD_HASH})


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data = request.get_json() or {}
    password = (data.get("password") or "").strip()
    if not PASSWORD_HASH:
        return jsonify({"error": "not_set"}), 400
    if hashlib.sha256(password.encode("utf-8")).hexdigest() != PASSWORD_HASH:
        return jsonify({"error": "invalid"}), 401
    return jsonify({"token": PASSWORD_HASH})


@app.route("/api/import", methods=["POST"])
def api_import():
    uploaded = request.files.get("file")
    bank = (request.form.get("bank") or "").lower()
    if not uploaded or bank not in {"alfa", "tinkoff"}:
        return jsonify({"error": "Укажите файл и банк (alfa / tinkoff)."}), 400

    with NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name

    file_id = storage.new_file_id()
    try:
        if bank == "alfa":
            count = import_service.import_alfa_file_into_vault(vault, pipeline, tmp_path, file_id)
        else:
            count = import_service.import_tinkoff_file_into_vault(vault, pipeline, tmp_path, file_id)
    finally:
        os.remove(tmp_path)

    uploaded_files.append({"id": file_id, "name": uploaded.filename, "bank": bank, "count": count})
    storage.save_state(vault, uploaded_files)
    return jsonify({"imported": count, "totals": analytics_service.compute_totals(vault)})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    vault.reset()
    uploaded_files.clear()
    storage.save_state(vault, uploaded_files)
    return jsonify({"status": "ok"})


@app.route("/api/analytics")
def api_analytics():
    start = parse_date(request.args.get("start_date") or "")
    end = parse_date(request.args.get("end_date") or "")
    exclude_transfers = (request.args.get("exclude_transfers") or "true").lower() == "true"

    ops_filtered = analytics_service.filter_operations(vault, start, end, exclude_transfers=exclude_transfers)
    transfer_ops = analytics_service.filter_operations(vault, start, end, transfers_only=True)
    all_ops = vault.operations
    all_dates = [op.date for op in all_ops]
    period_all = None
    if all_dates:
        period_all = {"start": min(all_dates).isoformat(), "end": max(all_dates).isoformat()}

    unknown_ops = analytics_service.unknown_operations(vault, ops_filtered)
    data = {
        "totals": analytics_service.compute_totals(vault, ops_filtered),
        "by_sys": analytics_service.breakdown_by_sys(vault, ops_filtered),
        "by_base": analytics_service.breakdown_by_base(vault, limit=None, operations=ops_filtered),  # backward compatible
        "by_base_expense": analytics_service.breakdown_by_base(
            vault, limit=None, op_type=OperationType.EXPENSE, operations=ops_filtered
        ),
        "by_base_income": analytics_service.breakdown_by_base(
            vault, limit=None, op_type=OperationType.INCOME, operations=ops_filtered
        ),
        "by_sys_hierarchy": analytics_service.base_by_sys_hierarchy(vault, operations=ops_filtered),
        "travel": analytics_service.travel_breakdown(vault, ops_filtered),
        "service": analytics_service.service_operations(vault, transfer_ops),
        "transfers": analytics_service.breakdown_by_base(vault, operations=transfer_ops),
        "trend": analytics_service.monthly_trend(vault, ops_filtered),
        "trend_weekly": analytics_service.weekly_trend(vault, ops_filtered),
        "trend_daily": analytics_service.daily_trend(vault, operations=ops_filtered),
        "ops_count": len(ops_filtered),
        "ops_count_total": len(vault.operations),
        "unknown": len(unknown_ops),
        "period_all": period_all,
        "unknown_samples": [
            {
                "date": op.date.isoformat(),
                "bank": op.bank,
                "description": op.description,
                "amount": float(op.amount),
            }
            for op in unknown_ops[:10]
        ],
        "unmapped": pipeline.unmapped_summary(),
        "ml_status": ml_model.status(),
        "llm_status": llm_categorizer.status(),
        "quick_answers": analytics_service.quick_answers(vault, ops_filtered, start, end),
    }
    return jsonify(data)


@app.route("/api/merchant-breakdown")
def api_merchant_breakdown():
    base_id = request.args.get("base_id")
    op_type_raw = (request.args.get("op_type") or "").lower()
    op_type = None
    if op_type_raw == "expense":
        op_type = OperationType.EXPENSE
    elif op_type_raw == "income":
        op_type = OperationType.INCOME
    if not base_id:
        return jsonify({"error": "base_id is required"}), 400
    items = analytics_service.merchant_breakdown(vault, base_id, op_type=op_type)
    return jsonify({"items": items})


@app.route("/api/operations")
def api_operations():
    limit = int(request.args.get("limit", 200))
    start_raw = request.args.get("start_date")
    end_raw = request.args.get("end_date")
    type_raw = (request.args.get("type") or "").lower()
    exclude_transfers = request.args.get("exclude_transfers", "").lower() == "true"

    start_dt = parse_date(start_raw) if start_raw else None
    end_dt = parse_date(end_raw) if end_raw else None

    filtered = []
    for op in vault.operations:
        if start_dt and op.date < start_dt:
            continue
        if end_dt and op.date > end_dt:
            continue
        if type_raw == "income" and op.type != OperationType.INCOME:
            continue
        if type_raw == "expense" and op.type != OperationType.EXPENSE:
            continue
        if exclude_transfers and op.category_id in analytics_service.SERVICE_BASE_IDS:
            continue
        filtered.append(op)

    ordered = sorted(filtered, key=lambda o: o.date, reverse=True)
    return jsonify({"items": [serialize_operation(op) for op in ordered[:limit]]})


@app.route("/api/train-ml", methods=["POST"])
def api_train_ml():
    status = ml_model.fit(vault.operations)
    return jsonify(
        {
            "trained": status.trained,
            "samples": status.samples,
            "classes": status.classes,
            "metrics": status.metrics,
        }
    )


@app.route("/api/agent-context")
def api_agent_context():
    # Контекст для внешнего LLM-чата (не используется в категоризации)
    unknown_ops = analytics_service.unknown_operations(vault)
    return jsonify(
        {
            "totals": analytics_service.compute_totals(vault),
            "by_sys": analytics_service.breakdown_by_sys(vault),
            "by_base": analytics_service.breakdown_by_base(vault),
            "trend": analytics_service.monthly_trend(vault),
            "unknown_examples": [
                {
                    "date": op.date.isoformat(),
                    "bank": op.bank,
                    "description": op.description,
                    "bank_category": op.bank_category,
                    "amount": float(op.amount),
                    "mcc": op.mcc,
                    "source": op.categorization_source,
                }
                for op in unknown_ops[:20]
            ],
        }
    )


@app.route("/api/agent-answer", methods=["POST"])
def api_agent_answer():
    payload = request.get_json(force=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    analytics = {
        "totals": analytics_service.compute_totals(vault),
        "by_base_expense": analytics_service.breakdown_by_base(vault, limit=None, op_type=OperationType.EXPENSE),
        "by_base_income": analytics_service.breakdown_by_base(vault, limit=None, op_type=OperationType.INCOME),
        "trend_monthly": analytics_service.monthly_trend(vault),
        "trend_weekly": analytics_service.weekly_trend(vault),
        "trend_daily": analytics_service.daily_trend(vault),
    }

    answer = build_simple_answer(question, analytics)
    return jsonify({"answer": answer})


@app.route("/api/files", methods=["GET"])
def api_list_files():
    return jsonify({"files": uploaded_files})


@app.route("/api/files/<file_id>", methods=["DELETE"])
def api_delete_file(file_id: str):
    global uploaded_files
    removed = [f for f in uploaded_files if f["id"] == file_id]
    if not removed:
        return jsonify({"error": "not found"}), 404
    uploaded_files = [f for f in uploaded_files if f["id"] != file_id]
    vault.operations = [op for op in vault.operations if op.source_file_id != file_id]
    storage.save_state(vault, uploaded_files)
    return jsonify({"status": "deleted", "totals": analytics_service.compute_totals(vault), "files": uploaded_files})


@app.route("/api/save", methods=["POST"])
def api_save():
    storage.save_state(vault, uploaded_files)
    return jsonify({"status": "saved"})


@app.route("/api/save-model", methods=["POST"])
def api_save_model():
    if not ml_model.is_ready():
        return jsonify({"error": "model not trained"}), 400
    ml_model.save(MODEL_PATH)
    return jsonify({"status": "saved", "path": str(MODEL_PATH)})


def build_simple_answer(question: str, analytics: dict) -> str:
    q = question.lower()
    totals = analytics.get("totals", {})
    expenses = totals.get("expense", 0)
    income = totals.get("income", 0)
    net = totals.get("net", 0)

    def top_cat(key: str):
        items = analytics.get(key) or []
        if not items:
            return None
        sorted_items = sorted(items, key=lambda x: abs(x["amount"]), reverse=True)
        return sorted_items[0]

    if any(x in q for x in ["куда", "больше всего", "трат", "категор"]):
        top_exp = top_cat("by_base_expense")
        if top_exp:
            return f"Больше всего расходов — {top_exp['name']}: {abs(top_exp['amount']):,.0f} ₽ ({abs(top_exp['amount'])/expenses*100:.1f}% расходов)." if expenses else f"Больше всего расходов — {top_exp['name']}."
        return "Не нашёл расходов по категориям."

    if "доход" in q or "заработ" in q:
        top_inc = top_cat("by_base_income")
        if top_inc:
            return f"Доходы: {income:,.0f} ₽. Основной источник — {top_inc['name']}: {top_inc['amount']:,.0f} ₽."
        return f"Доходы: {income:,.0f} ₽."

    if "итог" in q or "баланс" in q or "остаток" in q:
        return f"Итог: {net:,.0f} ₽ (доходы {income:,.0f} ₽, расходы {expenses:,.0f} ₽)."

    if "месяц" in q and "измен" in q:
        trend = analytics.get("trend_monthly") or []
        if len(trend) >= 2:
            last, prev = trend[-1], trend[-2]
            diff = last["expense"] - prev["expense"]
            direction = "выросли" if diff > 0 else "снизились"
            return f"Расходы {direction} на {abs(diff):,.0f} ₽: было {prev['expense']:,.0f} ₽, стало {last['expense']:,.0f} ₽."
        return "Недостаточно данных для сравнения месяцев."

    # Fallback
    return "Открой аналитику: там донаты по категориям и динамика. Спроси точнее — например: 'сколько потратил на фастфуд?' или 'почему итог месяца в минусе?'."


if __name__ == "__main__":
    app.run(debug=True, port=5000)
