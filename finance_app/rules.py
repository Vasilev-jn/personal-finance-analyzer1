#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Optional, Tuple

from finance_app.category_tree import SERVICE_BASE_IDS
from finance_app.domain import Operation, OperationType
from finance_app.utils import Features

RuleResult = Tuple[str, str]


def apply_rules(operation: Operation, features: Features) -> Optional[RuleResult]:
    feature_text = features.text
    merchant_text = features.merchant_norm

    if operation.type == OperationType.EXPENSE and "озон банк" in merchant_text:
        return "base_transfer_out", "rule: ozon bank transfer"

    if operation.type == OperationType.EXPENSE and "парковки россии" in merchant_text:
        return "base_transport_car_service", "rule: parking topup"

    if operation.type == OperationType.EXPENSE and any(
        key in merchant_text
        for key in ("yandex 5399 market", "yandex market", "market yandex", "ozon", "avito", "wildberries", "wb ru", "wb.")
    ):
        return "base_shopping_marketplace", "rule: marketplace merchant"
    mcc = features.mcc or ""

    if "кэшбэк" in feature_text:
        return "base_income_cashback", "rule: cashback"

    if operation.type == OperationType.INCOME and any(
        key in feature_text for key in ("зарплата", "salary", "премия")
    ):
        return "base_income_salary", "rule: salary keyword"

    if "пополнение" in feature_text or "зачисление" in feature_text:
        return "base_topup", "rule: topup keywords"

    if "внесение наличных" in feature_text:
        return "base_topup", "rule: cash deposit"

    if "снятие" in feature_text or mcc in {"6010", "6011"}:
        return "base_cashout", "rule: cash out"

    if "перевод между своими" in feature_text or "внутренний перевод" in feature_text:
        return "base_internal_transfer", "rule: internal transfer keyword"
    if "перевод со счета" in feature_text and "на счет" in feature_text:
        return "base_internal_transfer", "rule: internal transfer keyword"

    if "перевод" in feature_text and operation.type == OperationType.EXPENSE:
        return "base_transfer_out", "rule: outgoing transfer keyword"

    if "перевод" in feature_text and operation.type == OperationType.INCOME:
        return "base_transfer_in", "rule: incoming transfer keyword"

    if "комиссия за обслуживание" in feature_text or "комиссия за перевыпуск" in feature_text:
        return "base_home_services", "rule: bank service fee"

    if "копилка для сдачи" in feature_text:
        return "base_internal_transfer", "rule: savings jar transfer"

    if any(key in feature_text for key in ("погашение од", "погашение кредита", "погашение по кредиту")):
        return "base_transfer_out", "rule: debt repayment keyword"

    if any(key in feature_text for key in ("артемович", "артем михайлович", "кирилл артемович", "васильев артем")):
        if operation.type == OperationType.EXPENSE:
            return "base_transfer_out", "rule: p2p named transfer"

    if "мтс и мгтс" in feature_text:
        return "base_home_internet", "rule: telecom keyword"

    if operation.category_id in SERVICE_BASE_IDS:
        return operation.category_id, "rule: already service"

    return None
