from typing import Dict, Iterable, List, Optional, Tuple

from finance_app.domain import Category


def _raw_categories() -> List[Tuple[str, str, Optional[str]]]:
    return [
        ("sys_transfers", "Сервисные движения", None),
        ("base_transfer_in", "Перевод входящий", "sys_transfers"),
        ("base_transfer_out", "Перевод исходящий", "sys_transfers"),
        ("base_topup", "Пополнение", "sys_transfers"),
        ("base_cashout", "Снятие наличных", "sys_transfers"),
        ("base_internal_transfer", "Межсчетный перевод", "sys_transfers"),
        ("sys_food_out", "Еда вне дома", None),
        ("base_food_fastfood", "Фастфуд", "sys_food_out"),
        ("base_food_coffee", "Кофе/чай", "sys_food_out"),
        ("base_food_restaurants", "Рестораны", "sys_food_out"),
        ("sys_shopping", "Покупки/дом", None),
        ("base_shopping_groceries", "Супермаркеты", "sys_shopping"),
        ("base_shopping_pharmacy", "Аптеки", "sys_shopping"),
        ("base_shopping_electronics", "Техника/гаджеты", "sys_shopping"),
        ("base_shopping_clothes", "Одежда/обувь", "sys_shopping"),
        ("base_shopping_alcohol", "Алкоголь", "sys_shopping"),
        ("base_shopping_books", "Книги", "sys_shopping"),
        ("base_shopping_stationery", "Канцтовары", "sys_shopping"),
        ("base_shopping_children", "Детские товары", "sys_shopping"),
        ("base_shopping_marketplace", "Маркетплейсы", "sys_shopping"),
        ("base_shopping_flowers", "Цветы/подарки", "sys_shopping"),
        ("base_shopping_gifts", "Подарки/творчество", "sys_shopping"),
        ("base_shopping_jewelry", "Ювелирные изделия", "sys_shopping"),
        ("base_shopping_sport", "Спорттовары", "sys_shopping"),
        ("base_shopping_furniture", "Мебель/ремонт", "sys_shopping"),
        ("sys_transport", "Транспорт", None),
        ("base_transport_taxi", "Такси", "sys_transport"),
        ("base_transport_public", "Общественный транспорт", "sys_transport"),
        ("base_transport_fuel", "Топливо/АЗС", "sys_transport"),
        ("base_transport_parking", "Парковка/штрафы", "sys_transport"),
        ("base_transport_carsharing", "Каршеринг", "sys_transport"),
        ("base_transport_scooter", "Самокаты/микромобилити", "sys_transport"),
        ("base_transport_car_rental", "Аренда авто", "sys_transport"),
        ("base_transport_car_service", "Автоуслуги/сервис", "sys_transport"),
        ("base_transport_parts", "Автозапчасти", "sys_transport"),
        ("base_transport_toll", "Платные дороги", "sys_transport"),
        ("base_transport_delivery", "Курьеринг/доставка", "sys_transport"),
        ("sys_travel", "Путешествия", None),
        ("base_travel_flights", "Авиабилеты", "sys_travel"),
        ("base_travel_hotels", "Отели", "sys_travel"),
        ("base_travel_trains", "Поезда/автобусы", "sys_travel"),
        ("base_travel_dutyfree", "Duty free/аэропорт", "sys_travel"),
        ("base_travel_other", "Другое путешествия", "sys_travel"),
        ("sys_entertainment", "Развлечения", None),
        ("base_entertainment_cinema", "Кино/концерты", "sys_entertainment"),
        ("base_entertainment_games", "Подписки/игры", "sys_entertainment"),
        ("base_entertainment_online_video", "Онлайн-кинотеатры", "sys_entertainment"),
        ("base_entertainment_music", "Музыка/подписки", "sys_entertainment"),
        ("base_entertainment_culture", "Культура/искусство", "sys_entertainment"),
        ("base_entertainment_activity", "Активный отдых", "sys_entertainment"),
        ("base_entertainment_other", "Прочие развлечения", "sys_entertainment"),
        ("base_entertainment_digital", "Цифровые товары", "sys_entertainment"),
        ("sys_health", "Здоровье", None),
        ("base_health_medicine", "Медицина/клиники", "sys_health"),
        ("base_health_fitness", "Фитнес", "sys_health"),
        ("sys_home_bills", "Дом и счета", None),
        ("base_home_rent", "Аренда/ипотека", "sys_home_bills"),
        ("base_home_utilities", "Коммунальные услуги", "sys_home_bills"),
        ("base_home_services", "Домашние сервисы", "sys_home_bills"),
        ("base_home_pets", "Животные", "sys_home_bills"),
        ("base_home_internet", "Связь/интернет/ТВ", "sys_home_bills"),
        ("base_home_repair", "Дом/ремонт/мебель", "sys_home_bills"),
        ("sys_taxes_fines", "Налоги/штрафы", None),
        ("base_taxes_state", "Налоги/пошлины", "sys_taxes_fines"),
        ("base_taxes_fines", "Штрафы ГИБДД", "sys_taxes_fines"),
        ("sys_income", "Доходы", None),
        ("base_income_salary", "Зарплата/регулярные", "sys_income"),
        ("base_income_cashback", "Кэшбэк/бонусы", "sys_income"),
        ("base_income_other", "Прочие доходы", "sys_income"),
        ("sys_beauty", "Красота", None),
        ("base_beauty_services", "Салоны/услуги", "sys_beauty"),
        ("base_beauty_cosmetics", "Косметика", "sys_beauty"),
        ("sys_education", "Образование", None),
        ("base_education_general", "Образование", "sys_education"),
        ("sys_unknown", "Неразмечено", None),
        ("base_unknown", "Требует разметки", "sys_unknown"),
        ("base_donations", "Пожертвования/НКО", "sys_unknown"),
    ]


def build_category_index() -> Dict[str, Category]:
    return {cid: Category(id=cid, name=name, parent_id=parent) for cid, name, parent in _raw_categories()}


CATEGORY_INDEX: Dict[str, Category] = build_category_index()
BASE_CATEGORY_IDS: List[str] = [cid for cid, cat in CATEGORY_INDEX.items() if cid.startswith("base_")]
SYS_CATEGORY_IDS: List[str] = [cid for cid, cat in CATEGORY_INDEX.items() if cid.startswith("sys_")]

TRAVEL_BASE_IDS = {
    "base_travel_flights",
    "base_travel_hotels",
    "base_travel_trains",
    "base_travel_dutyfree",
    "base_travel_other",
}

SERVICE_BASE_IDS = {
    "base_transfer_in",
    "base_transfer_out",
    "base_topup",
    "base_cashout",
    "base_internal_transfer",
}


def find_parent_sys(category_id: Optional[str]) -> Optional[str]:
    if not category_id:
        return None
    visited = set()
    current = category_id
    while current and current not in visited:
        visited.add(current)
        category = CATEGORY_INDEX.get(current)
        if not category:
            return None
        if category.id.startswith("sys_"):
            return category.id
        current = category.parent_id
    return None


def iter_leaf_categories() -> Iterable[Category]:
    for cid in BASE_CATEGORY_IDS:
        yield CATEGORY_INDEX[cid]
