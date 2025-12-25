#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Dict, Optional, Tuple

from finance_app.utils import normalize_text

# (bank, bank_category_norm) -> base_id
BANK_CATEGORY_TO_BASE: Dict[Tuple[str, str], str] = {
    # Альфа-Банк
    ("alfa", "пополнения"): "base_topup",
    ("alfa", "внесение наличных"): "base_topup",
    ("alfa", "снятия"): "base_cashout",
    ("alfa", "финансовые операции"): "base_internal_transfer",
    ("alfa", "переводы"): "base_transfer_out",
    # оставляем "прочие расходы" без жёсткого маппинга, чтобы их ловили правила/ML
    ("alfa", "фастфуд"): "base_food_fastfood",
    ("alfa", "кафе и рестораны"): "base_food_restaurants",
    ("alfa", "супермаркеты"): "base_shopping_groceries",
    ("alfa", "продукты"): "base_shopping_groceries",
    ("alfa", "алкоголь"): "base_shopping_alcohol",
    ("alfa", "цифровые товары"): "base_entertainment_digital",
    ("alfa", "активный отдых"): "base_entertainment_activity",
    ("alfa", "развлечения"): "base_entertainment_other",
    ("alfa", "культура и искусство"): "base_entertainment_culture",
    ("alfa", "азс"): "base_transport_fuel",
    ("alfa", "авто"): "base_transport_car_service",
    ("alfa", "автозапчасти"): "base_transport_parts",
    ("alfa", "автоуслуги"): "base_transport_car_service",
    ("alfa", "платные дороги"): "base_transport_toll",
    ("alfa", "дом и ремонт"): "base_home_repair",
    ("alfa", "ремонт и мебель"): "base_home_repair",
    ("alfa", "животные"): "base_home_pets",
    ("alfa", "коммунальные услуги"): "base_home_utilities",
    ("alfa", "интернет"): "base_home_internet",
    ("alfa", "связь интернет и тв"): "base_home_internet",
    ("alfa", "образование"): "base_education_general",
    ("alfa", "книги"): "base_shopping_books",
    ("alfa", "канцтовары"): "base_shopping_stationery",
    ("alfa", "тревел"): "base_travel_other",
    ("alfa", "спортивные товары"): "base_shopping_sport",
    ("alfa", "аренда авто"): "base_transport_car_rental",
    ("alfa", "такси"): "base_transport_taxi",
    ("alfa", "общественный транспорт"): "base_transport_public",
    ("alfa", "проезд"): "base_transport_public",
    ("alfa", "детские товары"): "base_shopping_children",
    ("alfa", "маркетплейсы"): "base_shopping_marketplace",
    ("alfa", "одежда и обувь"): "base_shopping_clothes",
    ("alfa", "электроника"): "base_shopping_electronics",
    ("alfa", "цветы"): "base_shopping_flowers",
    ("alfa", "украшения"): "base_shopping_jewelry",
    ("alfa", "подарки"): "base_shopping_gifts",
    ("alfa", "красота"): "base_beauty_services",
    ("alfa", "медицина"): "base_health_medicine",
    ("alfa", "здоровье"): "base_health_medicine",
    ("alfa", "аптеки"): "base_shopping_pharmacy",
    ("alfa", "транспорт"): "base_transport_public",
    ("alfa", "медицинские услуги"): "base_health_medicine",
    ("alfa", "техника"): "base_shopping_electronics",

    # Тинькофф
    ("tinkoff", "супермаркеты"): "base_shopping_groceries",
    ("tinkoff", "кафе и рестораны"): "base_food_restaurants",
    ("tinkoff", "фастфуд"): "base_food_fastfood",
    ("tinkoff", "кофе"): "base_food_coffee",
    ("tinkoff", "авиабилеты"): "base_travel_flights",
    ("tinkoff", "ж/д билеты"): "base_travel_trains",
    ("tinkoff", "duty free"): "base_travel_dutyfree",
    ("tinkoff", "тревел"): "base_travel_other",
    ("tinkoff", "каршеринг"): "base_transport_carsharing",
    ("tinkoff", "доставка"): "base_transport_delivery",
    ("tinkoff", "самокаты"): "base_transport_scooter",
    ("tinkoff", "общественный транспорт"): "base_transport_public",
    ("tinkoff", "такси"): "base_transport_taxi",
    ("tinkoff", "проезд"): "base_transport_public",
    ("tinkoff", "автоуслуги"): "base_transport_car_service",
    ("tinkoff", "платные дороги"): "base_transport_toll",
    ("tinkoff", "заправки"): "base_transport_fuel",
    ("tinkoff", "мебель"): "base_shopping_furniture",
    ("tinkoff", "животные"): "base_home_pets",
    ("tinkoff", "налоги"): "base_taxes_state",
    ("tinkoff", "штрафы"): "base_taxes_fines",
    ("tinkoff", "развлечения"): "base_entertainment_other",
    ("tinkoff", "кино"): "base_entertainment_cinema",
    ("tinkoff", "онлайн кинотеатр"): "base_entertainment_online_video",
    ("tinkoff", "цифровые товары"): "base_entertainment_digital",
    ("tinkoff", "музыка"): "base_entertainment_music",
    ("tinkoff", "культура и искусство"): "base_entertainment_culture",
    ("tinkoff", "косметика"): "base_beauty_cosmetics",
    ("tinkoff", "красота"): "base_beauty_services",
    ("tinkoff", "аптеки"): "base_shopping_pharmacy",
    ("tinkoff", "магазины электроники"): "base_shopping_electronics",
    ("tinkoff", "детские товары"): "base_shopping_children",
    ("tinkoff", "маркетплейсы"): "base_shopping_marketplace",
    ("tinkoff", "одежда и обувь"): "base_shopping_clothes",
    ("tinkoff", "подарки"): "base_shopping_gifts",
    ("tinkoff", "цветы"): "base_shopping_flowers",
    ("tinkoff", "спорттовары"): "base_shopping_sport",
    ("tinkoff", "фитнес"): "base_health_fitness",
    ("tinkoff", "образование"): "base_education_general",
    ("tinkoff", "книги"): "base_shopping_books",
    ("tinkoff", "донаты"): "base_donations",
    ("tinkoff", "прочие доходы"): "base_income_other",
    ("tinkoff", "услуги"): "base_home_services",
    ("tinkoff", "между своими счетами"): "base_internal_transfer",
    ("tinkoff", "внутренний перевод"): "base_internal_transfer",
    ("tinkoff", "цифровой контент"): "base_entertainment_digital",
    ("tinkoff", "жкх/ремонт"): "base_home_services",
    ("tinkoff", "жкх/электронные товары"): "base_entertainment_digital",
    ("tinkoff", "маркетплейс товар"): "base_shopping_marketplace",
    ("tinkoff", "маркетплейс подписка"): "base_shopping_marketplace",
    ("tinkoff", "пополнения"): "base_topup",
    ("tinkoff", "снятия"): "base_cashout",
    ("tinkoff", "переводы"): "base_transfer_out",
    ("tinkoff", "внутренние переводы"): "base_internal_transfer",
    ("tinkoff", "канцтовары"): "base_shopping_stationery",
    ("tinkoff", "госуслуги"): "base_taxes_state",
    ("tinkoff", "местный транспорт"): "base_transport_public",
    ("tinkoff", "сервис"): "base_home_services",
    ("tinkoff", "различные товары"): "base_shopping_marketplace",
    ("tinkoff", "рестораны"): "base_food_restaurants",
    ("tinkoff", "бонусы"): "base_income_cashback",
    ("tinkoff", "экосистема яндекс"): "base_shopping_marketplace",
    ("tinkoff", "ремонт и мебель"): "base_shopping_furniture",
    ("tinkoff", "услуги банка"): "base_income_other",
    ("tinkoff", "книги и канцтовары"): "base_shopping_books",

    # Общие фолбеки
    ("*", "налоги"): "base_taxes_state",
    ("*", "штрафы"): "base_taxes_fines",
    ("*", "переводы"): "base_transfer_out",
    ("*", "пополнение"): "base_topup",
    ("*", "пополнения"): "base_topup",
    ("*", "снятия"): "base_cashout",
    ("*", "каршеринг"): "base_transport_carsharing",
    ("*", "самокаты"): "base_transport_scooter",
    ("*", "маркетплейсы"): "base_shopping_marketplace",
    ("*", "yandex market"): "base_shopping_marketplace",
    ("*", "market yandex"): "base_shopping_marketplace",
    ("*", "ozon"): "base_shopping_marketplace",
    ("*", "avito"): "base_shopping_marketplace",
    ("*", "wildberries"): "base_shopping_marketplace",
    ("*", "заправки"): "base_transport_fuel",
    ("*", "кино"): "base_entertainment_cinema",
    ("*", "цифровые товары"): "base_entertainment_digital",
    ("*", "музыка"): "base_entertainment_music",
    ("*", "образование"): "base_education_general",
    ("*", "прочие расходы"): "base_transfer_out",
    ("*", "кредиты"): "base_transfer_out",
    ("*", "штрафы и налоги"): "base_taxes_state",
    ("*", "табак"): "base_shopping_alcohol",
}


def lookup_base_category(bank: str, bank_category: Optional[str]) -> Optional[str]:
    if not bank_category:
        return None
    bank_norm = normalize_text(bank)
    cat_norm = normalize_text(bank_category)
    exact_key = (bank_norm, cat_norm)
    if exact_key in BANK_CATEGORY_TO_BASE:
        return BANK_CATEGORY_TO_BASE[exact_key]
    fallback_key = ("*", cat_norm)
    return BANK_CATEGORY_TO_BASE.get(fallback_key)


def lookup_base_category_norm(bank: str, bank_category_norm: str) -> Optional[str]:
    bank_norm = normalize_text(bank)
    cat_norm = bank_category_norm
    exact_key = (bank_norm, cat_norm)
    if exact_key in BANK_CATEGORY_TO_BASE:
        return BANK_CATEGORY_TO_BASE[exact_key]
    fallback_key = ("*", cat_norm)
    return BANK_CATEGORY_TO_BASE.get(fallback_key)
