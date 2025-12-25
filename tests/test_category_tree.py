from finance_app.category_tree import CATEGORY_INDEX, BASE_CATEGORY_IDS, SYS_CATEGORY_IDS, find_parent_sys, iter_leaf_categories


def test_find_parent_sys_for_leaf():
    assert find_parent_sys("base_food_coffee") == "sys_food_out"
    assert find_parent_sys("sys_income") == "sys_income"
    assert find_parent_sys("non_existing") is None


def test_iter_leaf_categories_returns_only_base():
    leaf_ids = {cat.id for cat in iter_leaf_categories()}
    assert leaf_ids.issubset(set(BASE_CATEGORY_IDS))
    assert "sys_income" not in leaf_ids
    assert "base_income_salary" in leaf_ids


def test_category_index_contains_bases_and_sys():
    assert "base_unknown" in CATEGORY_INDEX
    assert "sys_unknown" in CATEGORY_INDEX
    assert set(SYS_CATEGORY_IDS)
