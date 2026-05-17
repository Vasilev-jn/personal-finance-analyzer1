import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests


ANALYTICAL_MARKERS = (
    "почему",
    "прогноз",
    "спрогноз",
    "сколько можно",
    "можно тратить",
    "дневной лимит",
    "лимит",
    "накоп",
    "цель",
    "рекоменд",
    "совет",
    "оптимиз",
    "сэконом",
    "паттерн",
    "аномал",
    "неочевид",
    "план",
    "до зарплаты",
    "хватит",
)


FACTUAL_MARKERS = (
    "сколько потрат",
    "куда уш",
    "топ",
    "категор",
    "баланс",
    "итог",
    "доход",
    "расход",
    "динамик",
    "перевод",
)


BUDGET_CALCULATION_MARKERS = (
    "сколько можно",
    "можно тратить",
    "дневной лимит",
    "лимит в день",
    "безопасно тратить",
)

SMALLTALK_MARKERS = (
    "привет",
    "здравствуй",
    "здравствуйте",
    "добрый день",
    "доброе утро",
    "добрый вечер",
    "хай",
    "hello",
    "hi",
    "спасибо",
    "благодарю",
    "ок",
    "понял",
    "поняла",
)

FINANCE_MARKERS = (
    "деньг",
    "финанс",
    "бюджет",
    "банк",
    "карт",
    "операц",
    "выписк",
    "покуп",
    "платеж",
    "платёж",
    "трата",
    "трат",
    "доход",
    "расход",
    "остат",
    "баланс",
    "перевод",
    "подпис",
    "зарплат",
    "лимит",
    "цель",
    "накоп",
    "сэконом",
    "кэшбек",
    "кэшбэк",
    "категор",
)

REQUEST_MARKERS = (
    "покажи",
    "посчитай",
    "расскажи",
    "проанализ",
    "анализ",
    "дай",
    "составь",
    "объясни",
    "оцени",
    "найди",
    "проверь",
    "подскажи",
    "сравни",
    "предлож",
    "помоги",
)

QUESTION_MARKERS = (
    "что",
    "где",
    "когда",
    "сколько",
    "почему",
    "зачем",
    "как",
    "какой",
    "какая",
    "какие",
    "куда",
    "откуда",
    "можно ли",
    "есть ли",
    "хватит ли",
    "стоит ли",
)


@dataclass
class AgentResult:
    answer: str
    tier: str
    source: str
    model: Optional[str] = None


class AgentLLMClient:
    def __init__(
        self,
        api_key: Optional[str] = "",
        model: Optional[str] = "llama-3.1-8b-instant",
        api_url: Optional[str] = "https://api.groq.com/openai/v1/chat/completions",
        timeout: int = 20,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.api_url = (api_url or "").strip()
        self.timeout = timeout

    def is_ready(self) -> bool:
        return bool(self.api_key and self.model and self.api_url)

    def complete(self, messages: list[dict], max_tokens: int = 900) -> Optional[str]:
        if not self.is_ready():
            return None

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
        except Exception:
            return None
        if response.status_code != 200:
            return None
        try:
            data = response.json()
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            return None


def read_token_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def classify_question(question: str) -> str:
    return "factual" if detect_intent(question) == "factual" else "analytical"


def is_smalltalk(question: str) -> bool:
    q = _normalized_query(question)
    if not q:
        return False
    if any(marker in q for marker in FINANCE_MARKERS + FACTUAL_MARKERS + ANALYTICAL_MARKERS):
        return False
    if len(q.split()) <= 4 and any(q == marker or q.startswith(f"{marker} ") for marker in SMALLTALK_MARKERS):
        return True
    return False


def is_finance_related(question: str) -> bool:
    q = question.lower()
    return any(marker in q for marker in FINANCE_MARKERS + FACTUAL_MARKERS + ANALYTICAL_MARKERS)


def looks_like_question_or_request(question: str) -> bool:
    q = _normalized_query(question)
    if not q:
        return False
    return (
        "?" in question
        or any(q.startswith(marker) or f" {marker} " in f" {q} " for marker in QUESTION_MARKERS)
        or any(marker in q for marker in REQUEST_MARKERS)
    )


def conversation_answer(question: str) -> str:
    if is_smalltalk(question):
        q = _normalized_query(question)
        if q.startswith("спасибо") or q.startswith("благодарю"):
            return "Пожалуйста. Если нужен разбор, задай конкретный вопрос по расходам, доходам, переводам, подпискам или цели."
        if q.startswith("ок") or q.startswith("понял") or q.startswith("поняла"):
            return "Ок. Жду конкретный вопрос по твоим финансам."
        return (
            "Привет. Я отвечаю только на конкретные вопросы по твоим финансам: расходы, доходы, "
            "переводы, подписки, цели и лимит до зарплаты.\n\n"
            "Например: «Куда ушло больше всего денег?» или «Сколько можно тратить в день до зарплаты?»"
        )
    if not is_finance_related(question):
        return (
            "Я отвечаю только на вопросы по данным MoneyMap. Задай финансовый вопрос: про расходы, "
            "доходы, переводы, подписки, категории, цель или лимит до зарплаты."
        )
    return (
        "Уточни вопрос по финансам. Например: «Сколько я потратил на подписки?», "
        "«Куда ушло больше всего денег?» или «Есть аномалии в расходах?»"
    )


def is_budget_calculation(question: str) -> bool:
    q = question.lower()
    if any(marker in q for marker in BUDGET_CALCULATION_MARKERS):
        return True
    return "до зарплат" in q and any(marker in q for marker in ("трат", "лимит", "накоп"))


def detect_intent(question: str) -> str:
    q = question.lower()
    if is_smalltalk(question):
        return "conversation"
    if is_budget_calculation(q):
        return "daily_limit"
    if any(marker in q for marker in ("подпис", "регулярн", "списан", "списыва")):
        return "subscriptions"
    if any(marker in q for marker in ("хватит", "дожить", "доживу", "в минус", "запас")) and (
        "зарплат" in q or "месяц" in q
    ):
        return "forecast"
    if any(marker in q for marker in ("цель", "накоп", "откладывать", "успеваю", "успеть")):
        return "goal_plan"
    if any(marker in q for marker in ("аномал", "необыч", "резко", "выбивается", "паттерн", "странн")):
        return "anomalies"
    if any(marker in q for marker in FACTUAL_MARKERS):
        return "factual"
    if any(marker in q for marker in ANALYTICAL_MARKERS):
        return "llm_analysis"
    if is_finance_related(q) and looks_like_question_or_request(q):
        return "llm_analysis"
    return "conversation"


def profile_insights(
    profile: dict,
    analytics: dict,
    today: Optional[date] = None,
    goal_amount_override: Optional[float] = None,
) -> dict:
    today = today or date.today()
    payday = _int_or_none(profile.get("payday"))
    income = _float_or_none(profile.get("income")) or 0.0
    current_month_totals = analytics.get("current_month_totals") or {}
    current_month_expense = float(current_month_totals.get("expense") or 0)
    structured_goal_amount = _float_or_none(profile.get("goal_amount"))
    text_goal_amount = extract_goal_amount(profile.get("goals") or "")
    goal_amount = goal_amount_override or structured_goal_amount or text_goal_amount
    goal_source = "question" if goal_amount_override else "profile" if structured_goal_amount else "text" if text_goal_amount else None
    goal_saved = _float_or_none(profile.get("goal_saved")) or 0.0
    goal_remaining = max(goal_amount - goal_saved, 0) if goal_amount else None
    goal_deadline = _date_or_none(profile.get("goal_deadline"))
    days_until_goal_deadline = max((goal_deadline - today).days, 0) if goal_deadline else None
    days_left = days_until_payday(today, payday) if payday else None

    monthly_reserve = 0.0
    goal_horizon_months = None
    if goal_remaining:
        if days_until_goal_deadline is not None:
            goal_horizon_months = max(days_until_goal_deadline / 30, 1)
            monthly_reserve = goal_remaining / goal_horizon_months
        else:
            goal_horizon_months = 6
            monthly_reserve = goal_remaining / goal_horizon_months

    safe_daily_limit = None
    if days_left and income:
        remaining = max(income - current_month_expense - monthly_reserve, 0)
        safe_daily_limit = remaining / days_left

    return {
        "today": today.isoformat(),
        "days_until_payday": days_left,
        "configured_monthly_income": income,
        "current_month_expense": current_month_expense,
        "goal_title": (profile.get("goal_title") or "").strip(),
        "goal_amount_detected": goal_amount,
        "goal_saved": goal_saved,
        "goal_remaining": goal_remaining,
        "goal_deadline": goal_deadline.isoformat() if goal_deadline else None,
        "days_until_goal_deadline": days_until_goal_deadline,
        "goal_source": goal_source,
        "estimated_monthly_goal_reserve": monthly_reserve,
        "goal_horizon_months": goal_horizon_months,
        "safe_daily_limit_until_payday": safe_daily_limit,
    }


def factual_answer(question: str, analytics: dict) -> str:
    q = question.lower()
    totals = analytics.get("totals", {})
    expenses = float(totals.get("expense") or 0)
    income = float(totals.get("income") or 0)
    net = float(totals.get("net") or 0)

    if "баланс" in q or "итог" in q or "остат" in q:
        return (
            "**Сводка**\n"
            f"- Итог сейчас: {money(net)}\n"
            f"- Доходы: {money(income)}\n"
            f"- Расходы без переводов: {money(expenses)}\n\n"
            "**Где смотреть**\n"
            "- Главная → «Сводка»\n"
            "- Аналитика"
        )

    if "доход" in q:
        top_income = _top_item(analytics.get("by_base_income"))
        detail = f"\n- Основной источник: {top_income['name']} на {money(top_income['amount'])}" if top_income else ""
        return (
            "**Доходы**\n"
            f"- Всего: {money(income)}"
            f"{detail}\n\n"
            "**Где смотреть**\n"
            "- Аналитика → Доходы"
        )

    if "перевод" in q:
        transfer_items = analytics.get("transfers") or []
        transfer_total = sum(abs(float(item.get("amount") or 0)) for item in transfer_items if isinstance(item, dict))
        top_transfer = _top_item(transfer_items)
        if not transfer_total:
            return "Переводы вынесены отдельно и не входят в расходы сводки. Сейчас данных по переводам нет."
        detail = (
            f"\n- Крупнейший тип: «{top_transfer['name']}» на {money(abs(float(top_transfer['amount'])))}"
            if top_transfer
            else ""
        )
        return (
            "**Переводы**\n"
            "- Переводы не входят в расходы сводки\n"
            f"- Отдельное движение по переводам: {money(transfer_total)}"
            f"{detail}\n\n"
            "**Где смотреть**\n"
            "- Главная → «Переводы»\n"
            "- Аналитика → Переводы"
        )

    top_expense = _top_item(analytics.get("by_base_expense"))
    if top_expense:
        share = abs(float(top_expense["amount"])) / expenses * 100 if expenses else 0
        return (
            "**Главная категория расходов**\n"
            f"- Категория: «{top_expense['name']}»\n"
            f"- Сумма: {money(abs(float(top_expense['amount'])))}\n"
            f"- Доля: {share:.1f}% расходов\n\n"
            "**Где смотреть**\n"
            "- Аналитика → Расходы"
        )
    return "Расходов по категориям пока нет. Детальнее смотри в «Аналитика → Расходы»."


def analytical_fallback_answer(question: str, profile: dict, analytics: dict) -> str:
    question_goal = extract_goal_amount(question)
    insights = profile_insights(profile, analytics, goal_amount_override=question_goal)
    goals = (profile.get("goals") or "").strip()
    priority = profile.get("priority") or "Снизить расходы"
    mode = profile.get("mode") or "Коплю"

    if insights["safe_daily_limit_until_payday"] is not None:
        goal_amount = float(insights["goal_amount_detected"] or 0)
        goal_title = insights.get("goal_title") or "цель"
        if question_goal:
            goal_part = f"При цели накопить {money(question_goal)}"
        elif insights.get("goal_source") == "profile" and goal_amount:
            goal_part = f"При цели «{goal_title}» на {money(goal_amount)}"
        elif goals:
            goal_part = f"При цели «{goals}»"
        else:
            goal_part = ""
        reserve = float(insights["estimated_monthly_goal_reserve"] or 0)
        reserve_bits = []
        if insights.get("goal_saved"):
            reserve_bits.append(f"уже накоплено {money(float(insights['goal_saved']))}")
        if insights.get("goal_remaining") is not None:
            reserve_bits.append(f"осталось {money(float(insights['goal_remaining']))}")
        if reserve:
            if insights.get("goal_deadline"):
                reserve_bits.append(
                    f"резерв под цель {money(reserve)} в месяц до {format_iso_date(insights['goal_deadline'])}"
                )
            else:
                reserve_bits.append(
                    f"резерв под цель {money(reserve)} в месяц"
                    f" (без срока распределяю на {insights['goal_horizon_months']} месяцев)"
                )
        reserve_part = f"\n- По цели: {', '.join(reserve_bits)}" if reserve_bits else ""
        goal_prefix = f"{goal_part} " if goal_part else ""
        return (
            "**Дневной лимит**\n"
            f"- {goal_prefix}безопасный дневной лимит до зарплаты: {money(insights['safe_daily_limit_until_payday'])}\n"
            f"- До зарплаты: {insights['days_until_payday']} дн.\n\n"
            "**Расчёт**\n"
            f"- Доход из профиля: {money(insights['configured_monthly_income'])}\n"
            f"- Расходы текущего месяца без переводов: {money(insights['current_month_expense'])}"
            f"{reserve_part}\n\n"
            "**Настройки профиля**\n"
            f"- Режим: {mode}\n"
            f"- Приоритет: {priority}"
        )

    if not profile.get("income") or not profile.get("payday"):
        return (
            "Для персонального расчёта не хватает дохода/мес и дня зарплаты в финансовом профиле. "
            "Заполни их, и я смогу посчитать дневной лимит, запас до зарплаты и план под цель."
        )

    return (
        "Запрос аналитический, но LLM сейчас недоступна. Я могу локально отвечать на фактические вопросы "
        "по расходам, доходам, балансу, категориям, подпискам, целям и лимиту до зарплаты; "
        "для свободного анализа нужен активный LLM-ключ."
    )


def subscriptions_answer(question: str, profile: dict, analytics: dict) -> str:
    q = question.lower()
    subscriptions = [item for item in (analytics.get("subscriptions") or []) if isinstance(item, dict)]
    if not subscriptions:
        return (
            "Регулярные подписки пока не найдены. Смотри «Аналитика → Подписки»: там появятся компании, "
            "когда в истории будет несколько похожих регулярных списаний."
        )

    subscriptions = sorted(subscriptions, key=lambda item: float(item.get("amount") or 0), reverse=True)
    total = sum(float(item.get("amount") or 0) for item in subscriptions)
    top = subscriptions[:3]
    top_text = "; ".join(f"{item.get('name') or item.get('key')} — {money(float(item.get('amount') or 0))}/мес" for item in top)
    income = _float_or_none(profile.get("income")) or 0
    share = f" · {total / income * 100:.1f}% дохода из профиля" if income else ""

    if "отмен" in q or "сократ" in q or "эконом" in q:
        biggest = top[0]
        goal_bits = []
        insights = profile_insights(profile, analytics)
        if insights.get("goal_remaining") is not None:
            monthly_amount = float(biggest.get("amount") or 0)
            remaining = float(insights["goal_remaining"])
            covered = monthly_amount / remaining * 100 if remaining else 0
            goal_bits.append(
                f"Отмена крупнейшей подписки высвободит {money(monthly_amount)}/мес, "
                f"это {covered:.1f}% от оставшейся цели."
            )
        goal_part = f" {' '.join(goal_bits)}" if goal_bits else ""
        return (
            "**Подписки**\n"
            f"- Всего: {money(total)} в месяц{share}\n"
            f"- Самые заметные: {top_text}\n"
            f"- Первый кандидат на проверку: «{biggest.get('name') or biggest.get('key')}»{goal_part}\n\n"
            "**Где смотреть**\n"
            "- Аналитика → Подписки"
        )

    next_bits = []
    for item in top:
        if item.get("next_estimated_date"):
            next_bits.append(f"{item.get('name') or item.get('key')}: около {format_iso_date(item['next_estimated_date'])}")
    next_part = f" Ближайшие ожидаемые списания: {'; '.join(next_bits)}." if next_bits else ""
    return (
        "**Подписки**\n"
        f"- Всего: {money(total)} в месяц{share}\n"
        f"- Самые крупные: {top_text}"
        f"{next_part}\n\n"
        "**Где смотреть**\n"
        "- Аналитика → Подписки"
    )


def goal_plan_answer(question: str, profile: dict, analytics: dict) -> str:
    question_goal = extract_goal_amount(question)
    insights = profile_insights(profile, analytics, goal_amount_override=question_goal)
    goal_amount = insights.get("goal_amount_detected")
    if not goal_amount:
        return (
            "Для плана по цели не хватает суммы цели. Заполни в профиле «Сумма цели» "
            "или задай вопрос с суммой, например: «как накопить 100000 рублей?»."
        )

    goal_title = insights.get("goal_title") or "цель"
    remaining = float(insights.get("goal_remaining") or 0)
    if remaining <= 0:
        return f"Цель «{goal_title}» уже закрыта: сумма {money(float(goal_amount))}, накоплено {money(float(insights.get('goal_saved') or 0))}."

    income = float(insights.get("configured_monthly_income") or 0)
    current_expense = float(insights.get("current_month_expense") or 0)
    reserve = float(insights.get("estimated_monthly_goal_reserve") or 0)
    deadline = insights.get("goal_deadline")
    deadline_part = (
        f"до {format_iso_date(deadline)} осталось {insights['days_until_goal_deadline']} дн"
        if deadline
        else f"срок не задан, черновой план считаю на {insights['goal_horizon_months']} месяцев"
    )
    basis = (
        f"Доход из профиля {money(income)}, расходы текущего месяца без переводов {money(current_expense)}."
        if income
        else f"Расходы текущего месяца без переводов {money(current_expense)}; доход в профиле не задан."
    )

    if income:
        monthly_gap = income - current_expense - reserve
        if monthly_gap >= 0:
            status = f"По текущему темпу план выглядит достижимым: после резерва под цель остаётся около {money(monthly_gap)}."
        else:
            status = (
                f"Есть риск не уложиться: при текущих расходах не хватает около {money(abs(monthly_gap))} "
                "в месяц к нужному резерву."
            )
    else:
        status = "Без дохода в профиле я не могу честно сравнить цель с бюджетом."

    return (
        f"**Цель «{goal_title}»**\n"
        f"- Нужно: {money(float(goal_amount))}\n"
        f"- Уже накоплено: {money(float(insights.get('goal_saved') or 0))}\n"
        f"- Осталось: {money(remaining)}\n"
        f"- Срок: {deadline_part}\n"
        f"- Нужно откладывать: около {money(reserve)} в месяц\n\n"
        "**Оценка**\n"
        f"- {basis}\n"
        f"- {status}"
    )


def forecast_answer(profile: dict, analytics: dict) -> str:
    insights = profile_insights(profile, analytics)
    income = float(insights.get("configured_monthly_income") or 0)
    days_left = insights.get("days_until_payday")
    if not income or days_left is None:
        return (
            "Для прогноза до зарплаты не хватает дохода/мес или дня зарплаты в профиле. "
            "Заполни их, и я посчитаю запас и дневной ориентир."
        )

    current_expense = float(insights.get("current_month_expense") or 0)
    reserve = float(insights.get("estimated_monthly_goal_reserve") or 0)
    projected_free = income - current_expense - reserve
    safe_daily = projected_free / days_left if days_left else projected_free
    subs = analytics.get("subscriptions") or []
    subs_total = sum(float(item.get("amount") or 0) for item in subs if isinstance(item, dict))
    subs_part = f"\n- Подписки дают регулярную нагрузку около {money(subs_total)}/мес" if subs_total else ""
    status = (
        f"Ориентир положительный: после расходов и резерва под цель остаётся около {money(projected_free)}."
        if projected_free >= 0
        else f"Ориентир отрицательный: не хватает около {money(abs(projected_free))}."
    )
    daily_part = (
        f"До зарплаты {days_left} дн., безопасный дневной ориентир: {money(max(safe_daily, 0))}."
        if days_left
        else "Зарплата сегодня; дневной лимит уже не распределяю."
    )
    return (
        "**Прогноз до зарплаты**\n"
        f"- {status}\n"
        f"- {daily_part}"
        f"{subs_part}\n\n"
        "**Ограничение расчёта**\n"
        "- Точного прогноза по реальному остатку нет: приложение не хранит отдельный свободный остаток по счетам\n"
        "- Считаю от дохода профиля и расходов текущего месяца"
    )


def anomalies_answer(analytics: dict, profile: dict) -> str:
    totals = analytics.get("totals") or {}
    expense_total = float(totals.get("expense") or 0)
    if not expense_total:
        return "Явных аномалий не вижу: расходов без переводов пока нет."

    signals = []
    top_expense = _top_item(analytics.get("by_base_expense"))
    if top_expense:
        top_amount = abs(float(top_expense.get("amount") or 0))
        share = top_amount / expense_total * 100 if expense_total else 0
        if share >= 35:
            signals.append(
                f"категория «{top_expense.get('name')}» занимает {share:.1f}% расходов ({money(top_amount)})"
            )

    monthly = [item for item in (analytics.get("trend_monthly") or []) if isinstance(item, dict)]
    if len(monthly) >= 3:
        current = float(monthly[-1].get("expense") or 0)
        previous = [float(item.get("expense") or 0) for item in monthly[-4:-1]]
        previous = [value for value in previous if value > 0]
        if previous:
            avg_previous = sum(previous) / len(previous)
            if current > avg_previous * 1.3 and current - avg_previous >= 1000:
                signals.append(
                    f"последний месяц выше среднего предыдущих месяцев на {money(current - avg_previous)}"
                )

    income = _float_or_none(profile.get("income")) or 0
    subs_total = sum(float(item.get("amount") or 0) for item in analytics.get("subscriptions") or [] if isinstance(item, dict))
    if income and subs_total and subs_total / income >= 0.1:
        signals.append(f"подписки съедают {subs_total / income * 100:.1f}% месячного дохода ({money(subs_total)})")

    if not signals:
        return (
            "Явных аномалий по агрегатам не вижу: нет категории с чрезмерной долей и нет резкого скачка месячных расходов. "
            "Проверка идёт без переводов; переводы смотри отдельно в «Аналитика → Переводы»."
        )
    return (
        "**Аномалии**\n"
        "- Нашёл сигналы, которые стоит проверить\n"
        + "\n".join(f"- {signal}" for signal in signals[:3])
        + "\n\n**Важно**\n"
        "- Переводы не считаю расходами, поэтому выводы относятся к реальным тратам"
    )


def analytical_llm_answer(question: str, profile: dict, analytics: dict, llm_client: AgentLLMClient) -> Optional[str]:
    if not llm_client.is_ready():
        return None

    compact_context = {
        "profile": profile,
        "profile_insights": profile_insights(profile, analytics),
        "data_period": analytics.get("data_period"),
        "totals": analytics.get("totals"),
        "current_month_totals": analytics.get("current_month_totals"),
        "transfer_totals": analytics.get("transfer_totals"),
        "top_expense_categories": _compact_items(analytics.get("by_base_expense"), limit=10, abs_amount=True),
        "top_income_categories": _compact_items(analytics.get("by_base_income"), limit=5),
        "transfer_categories": _compact_items(analytics.get("transfers"), limit=10, abs_amount=True),
        "subscriptions": (analytics.get("subscriptions") or [])[:10],
        "monthly_trend": (analytics.get("trend_monthly") or [])[-6:],
        "weekly_trend": (analytics.get("trend_weekly") or [])[-8:],
        "daily_trend": (analytics.get("trend_daily") or [])[-30:],
    }

    tone = profile.get("tone") or "Прямой"
    messages = [
        {
            "role": "system",
            "content": (
                "Ты финансовый ИИ-агент MoneyMap. Отвечай на русском. "
                "Используй только переданные агрегированные данные, не выдумывай операции и точные факты. "
                "Если данных не хватает, явно скажи, чего не хватает. "
                "Поле totals и категории расходов уже очищены от переводов; переводы лежат отдельно в transfer_* и не считаются расходами. "
                "Не называй отрицательный итог долгом или задолженностью: это только разница доходов и расходов в импортированной истории. "
                "totals относится ко всей импортированной истории за data_period, а не к году или месяцу; не пересчитывай эти суммы в годовые без явного периода. "
                "Если current_month_has_operations=false, говори, что в текущем календарном месяце нет импортированных операций, а не что месяц не начался. "
                "Форматируй ответ Markdown-структурой: короткие блоки с жирными заголовками, списки через '-', без длинной простыни текста. "
                "Давай короткие практичные рекомендации и 1-3 расчёта. "
                f"Стиль общения: {tone}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "context": compact_context,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]
    return llm_client.complete(messages)


def answer_agent_question(question: str, profile: dict, analytics: dict, llm_client: AgentLLMClient) -> AgentResult:
    intent = detect_intent(question)
    if intent == "conversation":
        return AgentResult(answer=conversation_answer(question), tier="conversation", source="local")
    if intent == "factual":
        return AgentResult(answer=factual_answer(question, analytics), tier="factual", source="local")

    if intent == "daily_limit":
        return AgentResult(
            answer=analytical_fallback_answer(question, profile, analytics),
            tier="analytical",
            source="local_calculation",
        )
    if intent == "subscriptions":
        return AgentResult(answer=subscriptions_answer(question, profile, analytics), tier="analytical", source="local_calculation")
    if intent == "goal_plan":
        return AgentResult(answer=goal_plan_answer(question, profile, analytics), tier="analytical", source="local_calculation")
    if intent == "forecast":
        return AgentResult(answer=forecast_answer(profile, analytics), tier="analytical", source="local_calculation")
    if intent == "anomalies":
        return AgentResult(answer=anomalies_answer(analytics, profile), tier="analytical", source="local_calculation")

    llm_answer = analytical_llm_answer(question, profile, analytics, llm_client)
    if llm_answer:
        return AgentResult(answer=llm_answer, tier="analytical", source="llm", model=llm_client.model)
    return AgentResult(answer=analytical_fallback_answer(question, profile, analytics), tier="analytical", source="local_fallback")


def days_until_payday(today: date, payday: Optional[int]) -> Optional[int]:
    if not payday:
        return None
    day = min(payday, _days_in_month(today.year, today.month))
    target = date(today.year, today.month, day)
    if target < today:
        year = today.year + 1 if today.month == 12 else today.year
        month = 1 if today.month == 12 else today.month + 1
        target = date(year, month, min(payday, _days_in_month(year, month)))
    return max((target - today).days, 0)


def extract_goal_amount(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"(\d[\d\s]{2,})", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(" ", ""))
    except Exception:
        return None


def money(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


def format_iso_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return value


def _top_item(items: object) -> Optional[dict]:
    if not isinstance(items, list) or not items:
        return None
    return sorted(items, key=lambda item: abs(float(item.get("amount") or 0)), reverse=True)[0]


def _compact_items(items: object, limit: int, abs_amount: bool = False) -> list[dict]:
    if not isinstance(items, list):
        return []
    compact = []
    for item in items[:limit]:
        amount = float(item.get("amount") or 0)
        compact.append({"name": item.get("name"), "amount": abs(amount) if abs_amount else amount})
    return compact


def _float_or_none(value: object) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def _int_or_none(value: object) -> Optional[int]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except Exception:
        return None


def _date_or_none(value: object) -> Optional[date]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _normalized_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().strip(".,!?:;\"'«»()[]{}")).strip()


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days
