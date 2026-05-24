from pathlib import Path
from tempfile import NamedTemporaryFile
import os
import hashlib
import time
import threading
from datetime import datetime, date, timedelta, timezone

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, send_from_directory
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from finance_app import category_mapping, rules
from finance_app.category_tree import CATEGORY_INDEX, iter_leaf_categories
from finance_app.domain import Operation, OperationType
from finance_app.services import agent_service, analytics_service, corrections_service, database, export_service, import_service
from finance_app.services.categorization import CategorizationPipeline, reclassify_unknown
from finance_app.domain import Vault
from finance_app.services.ml_model import SimpleMLModel
from finance_app.services import storage
from finance_app.services import auth_service
from finance_app.services.llm_categorizer import LLMCategorizer
from finance_app.utils import build_features


BASE_DIR = Path(__file__).parent
INSTRUCTIONS_DIR = BASE_DIR / "instructions"
IMPORT_FORMATS = {
    "alfa": {"label": "CSV", "extensions": {".csv"}, "name": "Альфа"},
    "tinkoff": {"label": "CSV", "extensions": {".csv"}, "name": "Т-Банк"},
    "sber": {"label": "Excel", "extensions": {".xls", ".xlsx"}, "name": "Сбер"},
    "vtb": {"label": "PDF", "extensions": {".pdf"}, "name": "ВТБ"},
}

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
agent_llm_client = agent_service.AgentLLMClient(
    api_key=os.getenv("AGENT_LLM_API_KEY")
    or os.getenv("GROQ_API_KEY")
    or agent_service.read_token_file(BASE_DIR / "token_model_groq.txt")
    or os.getenv("LLM_API_KEY"),
    model=os.getenv("AGENT_LLM_MODEL") or os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant",
    api_url=os.getenv("AGENT_LLM_API_URL") or "https://api.groq.com/openai/v1/chat/completions",
)
vault.categories = CATEGORY_INDEX
uploaded_files: list = []
corrections_log: list[dict] = []
user_profile: dict = storage.normalize_profile({})
user_profile_exists = False
SESSION_TTL_SECONDS = 8 * 60 * 60
REQUEST_RUNTIME_LOCK = threading.RLock()

# путь для сохранения модели
MODEL_PATH = BASE_DIR / "models" / "expense_clf.pkl"

def initialize_database_with_retry() -> None:
    retries = int(os.getenv("DATABASE_INIT_RETRIES", "30"))
    delay_seconds = float(os.getenv("DATABASE_INIT_DELAY", "1"))
    should_retry = bool(os.getenv("DATABASE_URL")) and not database.DATABASE_URL.startswith("sqlite")
    last_error: OperationalError | None = None
    for attempt in range(retries if should_retry else 1):
        try:
            database.init_db()
            return
        except OperationalError as exc:
            last_error = exc
            if not should_retry or attempt == retries - 1:
                raise
            time.sleep(delay_seconds)
    if last_error:
        raise last_error


# при старте пытаемся загрузить модель
ml_model.load(MODEL_PATH)
initialize_database_with_retry()


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


def has_users(db=None) -> bool:
    owns_session = db is None
    db = db or database.SessionLocal()
    try:
        return db.scalar(select(database.UserModel.id).limit(1)) is not None
    finally:
        if owns_session:
            db.close()


def _session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def issue_session_token(db, user_id: int) -> str:
    database.cleanup_sessions(db)
    return database.issue_token(db, user_id, _session_expiry())


def user_public_payload(user: database.UserModel | None) -> dict | None:
    if not user:
        return None
    return {"id": user.id, "email": user.email}


def authenticated_user_from_token(db, token: str) -> database.UserModel | None:
    if not token:
        return None
    database.cleanup_sessions(db)
    session = db.get(database.SessionModel, token)
    if not session:
        return None
    if _aware(session.expires_at) <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return db.get(database.UserModel, session.user_id)


def verify_user_password(user: database.UserModel, password: str) -> bool:
    return auth_service.verify_password(password, user.password_record)


def load_user_runtime(db, user_id: int) -> None:
    global vault, uploaded_files, corrections_log, user_profile, user_profile_exists
    vault = database.vault_for_user(db, user_id)
    uploaded_files = database.uploaded_files_for_user(db, user_id)
    corrections_log = database.corrections_for_user(db, user_id)
    profile = database.load_profile(db, user_id)
    user_profile = storage.normalize_profile(profile or {})
    user_profile_exists = profile is not None
    pipeline.replace_custom_mappings(database.custom_mappings_for_user(db, user_id))
    rebuild_pipeline_counters()


def current_user_id() -> int:
    return int(g.current_user.id)


def current_db():
    return g.db


def save_runtime_state() -> None:
    # Legacy JSON persistence is intentionally disabled. Runtime state is stored in SQL tables.
    return None


def rebuild_pipeline_counters() -> None:
    pipeline.unmapped_counter.clear()
    pipeline.unknown_tracker.clear()
    for op in vault.operations:
        features = build_features(op)
        if not features.bank_category_norm:
            continue
        if rules.apply_rules(op, features):
            continue
        if pipeline._lookup_custom_mapping(op.bank, features.bank_category_norm):
            continue
        if category_mapping.lookup_base_category_norm(op.bank, features.bank_category_norm):
            continue
        pipeline._track_unmapped(op.bank, features.bank_category_norm)


def current_analytics_payload(start: date | None = None, end: date | None = None, exclude_transfers: bool = True) -> dict:
    ops_filtered = analytics_service.filter_operations(vault, start, end, exclude_transfers=exclude_transfers)
    transfer_ops = analytics_service.filter_operations(vault, start, end, transfers_only=True)
    unknown_ops = analytics_service.unknown_operations(vault, ops_filtered)
    all_dates = [op.date for op in vault.operations]
    period_all = {"start": min(all_dates).isoformat(), "end": max(all_dates).isoformat()} if all_dates else None
    return {
        "totals": analytics_service.compute_totals(vault, ops_filtered),
        "by_sys": analytics_service.breakdown_by_sys(vault, ops_filtered),
        "by_base": analytics_service.breakdown_by_base(vault, limit=None, operations=ops_filtered),
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
        "subscriptions": analytics_service.subscription_candidates(vault, ops_filtered),
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


def agent_analytics_payload() -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    spending_ops = analytics_service.filter_operations(vault, exclude_transfers=True)
    transfer_ops = analytics_service.filter_operations(vault, transfers_only=True)
    current_month_ops = analytics_service.filter_operations(vault, month_start, today, exclude_transfers=True)
    spending_dates = [op.date for op in spending_ops]
    data_start = min(spending_dates).isoformat() if spending_dates else None
    data_end = max(spending_dates).isoformat() if spending_dates else None
    return {
        "data_period": {
            "start": data_start,
            "end": data_end,
            "days": (max(spending_dates) - min(spending_dates)).days + 1 if spending_dates else 0,
            "current_month_start": month_start.isoformat(),
            "current_month_end": today.isoformat(),
            "current_month_has_operations": bool(current_month_ops),
        },
        "totals": analytics_service.compute_totals(vault, spending_ops),
        "all_totals": analytics_service.compute_totals(vault),
        "current_month_totals": analytics_service.compute_totals(vault, current_month_ops),
        "transfer_totals": analytics_service.compute_totals(vault, transfer_ops),
        "by_base_expense": analytics_service.breakdown_by_base(
            vault, limit=None, op_type=OperationType.EXPENSE, operations=spending_ops
        ),
        "by_base_income": analytics_service.breakdown_by_base(
            vault, limit=None, op_type=OperationType.INCOME, operations=spending_ops
        ),
        "transfers": analytics_service.breakdown_by_base(vault, limit=None, operations=transfer_ops),
        "subscriptions": analytics_service.subscription_candidates(vault, spending_ops),
        "trend_monthly": analytics_service.monthly_trend(vault, spending_ops),
        "trend_weekly": analytics_service.weekly_trend(vault, spending_ops),
        "trend_daily": analytics_service.daily_trend(vault, operations=spending_ops),
    }


def analytics_rows(analytics: dict) -> list[dict]:
    rows: list[dict] = []
    for section, value in analytics.items():
        if isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    rows.append({"section": section, "index": idx, **item})
                else:
                    rows.append({"section": section, "index": idx, "value": str(item)})
        elif isinstance(value, dict):
            rows.append({"section": section, **{k: json_value(v) for k, v in value.items()}})
        else:
            rows.append({"section": section, "value": json_value(value)})
    return rows


def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def is_valid_base_category(category_id: str) -> bool:
    return category_id in CATEGORY_INDEX and category_id.startswith("base_")


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_format_message(bank: str) -> str:
    spec = IMPORT_FORMATS.get(bank) or {}
    label = spec.get("label") or "поддерживаемый формат"
    bank_name = spec.get("name") or bank
    return f"Для банка {bank_name} загрузите файл в формате {label}."


def cleanup_failed_import(file_id: str) -> None:
    if not file_id:
        return
    vault.operations = [op for op in vault.operations if op.source_file_id != file_id]
    rebuild_pipeline_counters()


def unique_operations_for_storage(operations: list[Operation], import_report: dict) -> list[Operation]:
    seen: set[str] = set()
    unique: list[Operation] = []
    duplicate_rows = 0
    for op in operations:
        fingerprint = database.operation_fingerprint(op)
        if fingerprint in seen:
            duplicate_rows += 1
            continue
        seen.add(fingerprint)
        unique.append(op)
    if duplicate_rows:
        import_report["duplicates"] = int(import_report.get("duplicates", 0) or 0) + duplicate_rows
        import_report["skipped"] = int(import_report.get("skipped", 0) or 0) + duplicate_rows
        import_report["imported"] = max(0, int(import_report.get("imported", len(operations)) or 0) - duplicate_rows)
        errors = import_report.setdefault("errors", [])
        errors.append({"reason": f"duplicate operations inside file: {duplicate_rows}"})
    return unique


@app.before_request
def open_db_and_require_auth():
    g.db = database.SessionLocal()
    if (
        request.path in {"/", "/legacy", "/favicon.ico"}
        or request.path.startswith("/static")
        or request.path.startswith("/instructions")
        or request.path.startswith("/api/auth")
    ):
        return None

    token = request.headers.get("X-Auth-Token") or ""
    REQUEST_RUNTIME_LOCK.acquire()
    g.runtime_lock_acquired = True
    user = authenticated_user_from_token(g.db, token)
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    g.current_user = user
    load_user_runtime(g.db, user.id)


@app.teardown_request
def close_db_session(_exc):
    if g.pop("runtime_lock_acquired", False):
        REQUEST_RUNTIME_LOCK.release()
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/")
def index():
    return render_template("index_bento.html")


@app.route("/legacy")
def legacy_index():
    return redirect("/", code=302)


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.svg")


@app.route("/instructions/<path:filename>")
def instruction_image(filename):
    if Path(filename).suffix.lower() != ".png":
        abort(404)
    return send_from_directory(INSTRUCTIONS_DIR, filename)


@app.route("/api/auth/status")
def api_auth_status():
    db = current_db()
    token = request.headers.get("X-Auth-Token") or ""
    user = authenticated_user_from_token(db, token)
    return jsonify(
        {
            "has_users": has_users(db),
            "authenticated": user is not None,
            "user": user_public_payload(user),
        }
    )


@app.route("/api/auth/set", methods=["POST"])
def api_auth_set():
    # Backward-compatible alias for the old first-run password endpoint.
    return api_auth_register()


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    db = current_db()
    data = request.get_json() or {}
    email = database.normalize_email(data.get("email") or "demo@example.local")
    password = (data.get("password") or "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "invalid_email"}), 400
    if len(password) < 4:
        return jsonify({"error": "too_short"}), 400
    user = database.UserModel(email=email, password_record=auth_service.create_password_record(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return jsonify({"error": "email_exists"}), 409
    token = issue_session_token(db, user.id)
    db.commit()
    return jsonify({"token": token, "user": user_public_payload(user)})


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    db = current_db()
    data = request.get_json() or {}
    email = database.normalize_email(data.get("email") or "")
    password = (data.get("password") or "").strip()
    user = None
    if email:
        user = db.scalar(select(database.UserModel).where(database.UserModel.email == email))
    else:
        user = db.scalar(select(database.UserModel).order_by(database.UserModel.id.asc()).limit(1))
    if not user:
        return jsonify({"error": "not_found"}), 404
    if not verify_user_password(user, password):
        return jsonify({"error": "invalid"}), 401
    token = issue_session_token(db, user.id)
    db.commit()
    return jsonify({"token": token, "user": user_public_payload(user)})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    db = current_db()
    token = request.headers.get("X-Auth-Token") or ""
    database.revoke_token(db, token)
    db.commit()
    return jsonify({"status": "ok"})


@app.route("/api/auth/change", methods=["POST"])
def api_auth_change_password():
    db = current_db()
    token = request.headers.get("X-Auth-Token") or ""
    user = authenticated_user_from_token(db, token)
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    current_password = (data.get("current_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()
    if len(new_password) < 4:
        return jsonify({"error": "too_short"}), 400
    if not verify_user_password(user, current_password):
        return jsonify({"error": "invalid_current_password"}), 401

    user.password_record = auth_service.create_password_record(new_password)
    db.query(database.SessionModel).filter(database.SessionModel.user_id == user.id).delete(synchronize_session=False)
    new_token = issue_session_token(db, user.id)
    db.commit()
    return jsonify({"status": "ok", "token": new_token, "user": user_public_payload(user)})


@app.route("/api/import", methods=["POST"])
def api_import():
    db = current_db()
    user_id = current_user_id()
    uploaded = request.files.get("file")
    bank = (request.form.get("bank") or "").lower()
    if not uploaded or bank not in IMPORT_FORMATS:
        return jsonify({"error": "Укажите файл и банк (alfa / tinkoff / sber / vtb)."}), 400

    filename = uploaded.filename or ""
    suffix = Path(filename).suffix.lower()
    format_spec = IMPORT_FORMATS[bank]
    if suffix not in format_spec["extensions"]:
        return (
            jsonify(
                {
                    "error": "unsupported_file_format",
                    "message": import_format_message(bank),
                    "expected_format": format_spec["label"],
                    "allowed_extensions": sorted(format_spec["extensions"]),
                }
            ),
            400,
        )

    tmp_path = ""
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name

    file_id = ""
    try:
        content_hash = file_sha256(tmp_path)
        duplicate_file = database.find_duplicate_file(db, user_id, content_hash)
        if duplicate_file:
            return (
                jsonify(
                    {
                        "error": "duplicate_file",
                        "message": "Этот файл уже был загружен. Повторный импорт отменён.",
                        "duplicate_file": {
                            "id": duplicate_file.id,
                            "name": duplicate_file.name,
                            "bank": duplicate_file.bank,
                        },
                    }
                ),
                409,
            )

        file_id = storage.new_file_id()
        try:
            if bank == "alfa":
                count, import_report = import_service.import_alfa_file_into_vault(
                    vault, pipeline, tmp_path, file_id, include_report=True
                )
            elif bank == "tinkoff":
                count, import_report = import_service.import_tinkoff_file_into_vault(
                    vault, pipeline, tmp_path, file_id, include_report=True
                )
            elif bank == "sber":
                count, import_report = import_service.import_sber_file_into_vault(
                    vault, pipeline, tmp_path, file_id, include_report=True
                )
            else:
                count, import_report = import_service.import_vtb_file_into_vault(
                    vault, pipeline, tmp_path, file_id, include_report=True
                )
        except Exception:
            cleanup_failed_import(file_id)
            return (
                jsonify(
                    {
                        "error": "file_parse_failed",
                        "message": f"Не удалось прочитать файл. {import_format_message(bank)} Проверьте, что выбрана правильная выписка из банка.",
                    }
                ),
                400,
            )
        duplicates = int(import_report.get("duplicates", 0) or 0)
        if count == 0 and duplicates:
            rebuild_pipeline_counters()
            return (
                jsonify(
                    {
                        "error": "duplicate_operations",
                        "message": "Файл не добавлен как новый: все операции из него уже есть в хранилище.",
                        "import_report": import_report,
                    }
                ),
                409,
            )
        if count == 0:
            cleanup_failed_import(file_id)
            return (
                jsonify(
                    {
                        "error": "no_operations_found",
                        "message": f"В файле не найдено операций для импорта. {import_format_message(bank)} Проверьте период, банк и структуру выписки.",
                        "import_report": import_report,
                    }
                ),
                400,
            )
    finally:
        if tmp_path:
            os.remove(tmp_path)

    try:
        new_operations = unique_operations_for_storage(
            [op for op in vault.operations if op.source_file_id == file_id],
            import_report,
        )
        count = len(new_operations)
        if count == 0:
            cleanup_failed_import(file_id)
            return (
                jsonify(
                    {
                        "error": "duplicate_operations",
                        "message": "Файл не добавлен как новый: все операции из него уже есть в хранилище.",
                        "import_report": import_report,
                    }
                ),
                409,
            )
        database.upsert_accounts(db, user_id, vault.accounts.values())
        database.insert_operations(db, user_id, new_operations)
        database.add_uploaded_file(db, user_id, file_id, uploaded.filename or "", bank, count, content_hash)
        db.commit()
        load_user_runtime(db, user_id)
    except IntegrityError:
        db.rollback()
        cleanup_failed_import(file_id)
        return (
            jsonify(
                {
                    "error": "duplicate_operations",
                    "message": "Файл не добавлен как новый: все операции из него уже есть в хранилище.",
                    "import_report": import_report,
                }
            ),
            409,
        )
    return jsonify({"imported": count, "totals": analytics_service.compute_totals(vault), "import_report": import_report})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    db = current_db()
    database.clear_user_data(db, current_user_id())
    db.commit()
    load_user_runtime(db, current_user_id())
    return jsonify({"status": "ok"})


@app.route("/api/profile", methods=["GET", "PUT"])
def api_profile():
    global user_profile, user_profile_exists
    db = current_db()
    user_id = current_user_id()
    if request.method == "GET":
        return jsonify({"profile": user_profile, "exists": user_profile_exists})

    payload = request.get_json(force=True) or {}
    raw_profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
    user_profile = storage.normalize_profile(raw_profile)
    user_profile_exists = True
    database.save_profile(db, user_id, user_profile)
    db.commit()
    return jsonify({"status": "ok", "profile": user_profile})


@app.route("/api/analytics")
def api_analytics():
    start = parse_date(request.args.get("start_date") or "")
    end = parse_date(request.args.get("end_date") or "")
    exclude_transfers = (request.args.get("exclude_transfers") or "true").lower() == "true"
    return jsonify(current_analytics_payload(start=start, end=end, exclude_transfers=exclude_transfers))


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
    subscription_key = (request.args.get("subscription_key") or "").strip()

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
        if subscription_key and analytics_service.operation_subscription_key(op) != subscription_key:
            continue
        filtered.append(op)

    ordered = sorted(filtered, key=lambda o: o.date, reverse=True)
    return jsonify({"items": [serialize_operation(op) for op in ordered[:limit]]})


@app.route("/api/categories")
def api_categories():
    sys_items = []
    for cid, category in CATEGORY_INDEX.items():
        if not cid.startswith("sys_"):
            continue
        sys_items.append({"id": category.id, "name": category.name, "parent_id": category.parent_id})
    base_items = [
        {"id": category.id, "name": category.name, "parent_id": category.parent_id} for category in iter_leaf_categories()
    ]
    return jsonify({"sys": sys_items, "base": base_items})


@app.route("/api/unknown")
def api_unknown():
    limit = int(request.args.get("limit", 300))
    items = corrections_service.unknown_items(vault, limit=limit)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/operations/<operation_id>/category", methods=["POST"])
def api_set_operation_category(operation_id: str):
    db = current_db()
    user_id = current_user_id()
    payload = request.get_json(force=True) or {}
    category_id = (payload.get("category_id") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if not is_valid_base_category(category_id):
        return jsonify({"error": "invalid_category_id"}), 400
    change = corrections_service.apply_manual_category(vault, operation_id, category_id, reason=reason)
    if not change:
        return jsonify({"error": "operation_not_found"}), 404
    corrections_log.append(change)
    operation = corrections_service.find_operation(vault, operation_id)
    database.update_operations(db, user_id, [operation])
    database.add_correction(db, user_id, change)
    db.commit()
    return jsonify({"status": "ok", "change": change, "operation": serialize_operation(operation)})


@app.route("/api/corrections")
def api_corrections():
    items = sorted(corrections_log, key=lambda x: x.get("timestamp") or "", reverse=True)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/corrections/undo", methods=["POST"])
def api_corrections_undo():
    db = current_db()
    user_id = current_user_id()
    reverted = corrections_service.undo_last_change(vault, corrections_log)
    if not reverted:
        return jsonify({"error": "nothing_to_undo"}), 400
    operation = corrections_service.find_operation(vault, reverted.get("operation_id") or "")
    if operation:
        database.update_operations(db, user_id, [operation])
    database.replace_corrections(db, user_id, corrections_log)
    db.commit()
    return jsonify({"status": "ok", "reverted": reverted})


@app.route("/api/mappings/custom", methods=["GET", "POST"])
def api_custom_mappings():
    db = current_db()
    user_id = current_user_id()
    if request.method == "GET":
        return jsonify({"items": pipeline.list_custom_mappings(), "count": len(pipeline.list_custom_mappings())})

    payload = request.get_json(force=True) or {}
    bank = (payload.get("bank") or "").strip().lower()
    bank_category = (payload.get("bank_category") or "").strip()
    base_id = (payload.get("base_id") or "").strip()
    if not bank or not bank_category:
        return jsonify({"error": "bank and bank_category are required"}), 400
    if not is_valid_base_category(base_id):
        return jsonify({"error": "invalid_base_id"}), 400

    mapping = pipeline.set_custom_mapping(bank, bank_category, base_id)
    reclassified = reclassify_unknown(vault, pipeline)
    rebuild_pipeline_counters()
    database.upsert_custom_mapping(db, user_id, mapping)
    database.update_operations(db, user_id, vault.operations)
    db.commit()
    return jsonify({"status": "ok", "mapping": mapping, "reclassified": reclassified})


@app.route("/api/reclassify-unknown", methods=["POST"])
def api_reclassify_unknown():
    db = current_db()
    user_id = current_user_id()
    updated = reclassify_unknown(vault, pipeline)
    database.update_operations(db, user_id, vault.operations)
    db.commit()
    return jsonify({"status": "ok", "updated": updated})


@app.route("/api/operations/<operation_id>/explain")
def api_operation_explain(operation_id: str):
    op = corrections_service.find_operation(vault, operation_id)
    if not op:
        return jsonify({"error": "operation_not_found"}), 404
    source = op.categorization_source or "unknown"
    explanation_by_source = {
        "manual": "Категория установлена вручную пользователем.",
        "mapping_custom": "Категория назначена пользовательским mapping.",
        "mapping": "Категория назначена bank_category mapping.",
        "ml_model": "Категория назначена ML-моделью.",
        "ml_stub": "Категория назначена эвристическим ML-stub.",
        "llm": "Категория назначена LLM fallback.",
        "fallback_stub": "Категория назначена безопасным fallback.",
        "unknown": "Категорию определить не удалось.",
    }
    explanation = explanation_by_source.get(source, f"Категория назначена источником: {source}.")
    return jsonify(
        {
            "operation_id": op.id,
            "category_id": op.category_id,
            "category_name": CATEGORY_INDEX.get(op.category_id).name if op.category_id in CATEGORY_INDEX else None,
            "source": source,
            "reason": explanation,
        }
    )


@app.route("/api/export")
def api_export():
    kind = (request.args.get("kind") or "operations").strip().lower()
    fmt = (request.args.get("format") or "json").strip().lower()
    if fmt not in {"json", "csv"}:
        return jsonify({"error": "format must be json or csv"}), 400

    if kind == "operations":
        rows = export_service.operations_rows(vault.operations)
        payload = rows
    elif kind == "unknown":
        rows = corrections_service.unknown_items(vault, limit=100000)
        payload = rows
    elif kind == "corrections":
        rows = corrections_log
        payload = rows
    elif kind == "analytics":
        payload = current_analytics_payload()
        rows = analytics_rows(payload)
    elif kind == "ml_dataset":
        rows = analytics_service.export_ml_dataset(vault)
        payload = rows
    else:
        return jsonify({"error": "unsupported kind"}), 400

    if fmt == "json":
        return Response(
            export_service.json_text(payload),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{kind}.json"'},
        )

    return Response(
        export_service.csv_text(rows),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'},
    )


@app.route("/api/train-ml", methods=["POST"])
def api_train_ml():
    db = current_db()
    user_id = current_user_id()
    status = ml_model.fit(vault.operations)
    reclassified = 0
    if status.trained:
        reclassified = reclassify_unknown(vault, pipeline)
        database.update_operations(db, user_id, vault.operations)
        db.commit()
    return jsonify(
        {
            "trained": status.trained,
            "samples": status.samples,
            "classes": status.classes,
            "metrics": status.metrics,
            "reclassified_unknown": reclassified,
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

    result = agent_service.answer_agent_question(question, user_profile, agent_analytics_payload(), agent_llm_client)
    return jsonify({"answer": result.answer, "tier": result.tier, "source": result.source, "model": result.model})


@app.route("/api/files", methods=["GET"])
def api_list_files():
    return jsonify({"files": uploaded_files})


@app.route("/api/files/<file_id>", methods=["DELETE"])
def api_delete_file(file_id: str):
    global uploaded_files, corrections_log
    db = current_db()
    user_id = current_user_id()
    removed = [f for f in uploaded_files if f["id"] == file_id]
    if not removed:
        return jsonify({"error": "not found"}), 404
    deleted_operation_ids = database.delete_file_with_operations(db, user_id, file_id)
    db.commit()
    load_user_runtime(db, user_id)
    return jsonify(
        {
            "status": "deleted",
            "totals": analytics_service.compute_totals(vault),
            "files": uploaded_files,
            "removed_operations": len(deleted_operation_ids),
        }
    )


@app.route("/api/save", methods=["POST"])
def api_save():
    save_runtime_state()
    return jsonify({"status": "saved", "storage": "database"})


@app.route("/api/save-model", methods=["POST"])
def api_save_model():
    if not ml_model.is_ready():
        return jsonify({"error": "model not trained"}), 400
    ml_model.save(MODEL_PATH)
    return jsonify({"status": "saved", "path": str(MODEL_PATH)})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5059)
