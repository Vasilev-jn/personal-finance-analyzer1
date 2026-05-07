from finance_app.category_mapping import lookup_base_category, lookup_base_category_norm


def test_lookup_base_category_exact_and_fallback():
    # exact match (alfa ozon is resolved via wildcard)
    assert lookup_base_category("alfa", "ozon") == "base_shopping_marketplace"
    # normalized values should also work
    assert lookup_base_category_norm("TINKOFF", "ozon") == "base_shopping_marketplace"
    # missing values are ignored
    assert lookup_base_category("alfa", None) is None


def test_lookup_tinkoff_extra_statement_categories():
    assert lookup_base_category("tinkoff", "Проценты") == "base_income_other"
    assert lookup_base_category("tinkoff", "Транспорт") == "base_transport_public"
    assert lookup_base_category("tinkoff", "Фото и копицентры") == "base_shopping_stationery"
    assert lookup_base_category("tinkoff", "Экосистема Сбер") == "base_shopping_groceries"
