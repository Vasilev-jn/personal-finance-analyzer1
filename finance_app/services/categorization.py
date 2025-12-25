from collections import Counter
from typing import Dict, Optional, Tuple

from finance_app import rules
from finance_app import category_mapping
from finance_app.category_tree import CATEGORY_INDEX
from finance_app.domain import Operation, OperationType
from finance_app.utils import Features, build_features, normalize_text
from finance_app.services.ml_model import SimpleMLModel
from finance_app.services.llm_categorizer import LLMCategorizer


class CategorizationPipeline:
    def __init__(
        self,
        unknown_tracker: Optional[Dict[str, int]] = None,
        ml_model: Optional[SimpleMLModel] = None,
        llm_categorizer: Optional[LLMCategorizer] = None,
    ):
        self.unknown_tracker = unknown_tracker if unknown_tracker is not None else {}
        self.unmapped_counter: Counter[Tuple[str, str]] = Counter()
        self.ml_model = ml_model
        self.llm_categorizer = llm_categorizer

    def categorize(self, operation: Operation) -> Optional[str]:
        features = build_features(operation)

        rule_result = rules.apply_rules(operation, features)
        if rule_result:
            operation.category_id, operation.categorization_source = rule_result[0], rule_result[1]
            return operation.category_id

        mapped = category_mapping.lookup_base_category_norm(operation.bank, features.bank_category_norm)
        if mapped:
            operation.category_id = mapped
            operation.categorization_source = "mapping"
            return mapped
        if features.bank_category_norm:
            self._track_unmapped(operation.bank, features.bank_category_norm)

        ml_guess = self._ml_model_predict(operation) if self.ml_model and self.ml_model.is_ready() else self._ml_stub(operation, features)
        if ml_guess:
            operation.category_id = ml_guess
            operation.categorization_source = "ml_model" if self.ml_model and self.ml_model.is_ready() else "ml_stub"
            return ml_guess

        llm_guess = self._llm_predict(operation)
        if llm_guess:
            operation.category_id = llm_guess
            operation.categorization_source = "llm"
            return llm_guess

        fallback_guess = self._fallback_stub(operation)
        if fallback_guess:
            operation.category_id = fallback_guess
            operation.categorization_source = "fallback_stub"
            return fallback_guess

        operation.category_id = None
        operation.categorization_source = "unknown"
        self._track_unknown(operation)
        return None

    def _ml_stub(self, operation: Operation, features: Features) -> Optional[str]:
        text = features.text
        if features.mcc:
            mcc_map = {
                "5411": "base_shopping_groceries",
                "5814": "base_food_fastfood",
                "5812": "base_food_restaurants",
                "4111": "base_transport_public",
                "4121": "base_transport_taxi",
                "4789": "base_travel_dutyfree",
                "4511": "base_travel_flights",
                "4112": "base_travel_trains",
                "7011": "base_travel_hotels",
                "5541": "base_transport_fuel",
                "5542": "base_transport_fuel",
                "5977": "base_health_fitness",
            }
            if features.mcc in mcc_map:
                return mcc_map[features.mcc]

        keyword_map = {
        "ашан": "base_shopping_groceries",
        "перекрест": "base_shopping_groceries",
        "perekrest": "base_shopping_groceries",
        "lenta": "base_shopping_groceries",
        "pyateroch": "base_shopping_groceries",
        "pyatero": "base_shopping_groceries",
        "magnit": "base_shopping_groceries",
        "da!": "base_shopping_groceries",
        "chesnok": "base_shopping_groceries",
        "malishev": "base_shopping_groceries",
        "yandex market": "base_shopping_marketplace",
        "market yandex": "base_shopping_marketplace",
        "ozon": "base_shopping_marketplace",
        "wildberries": "base_shopping_marketplace",
        "wb ru": "base_shopping_marketplace",
            "avito": "base_shopping_marketplace",
            "vkusnoitochka": "base_food_fastfood",
            "kfc": "base_food_fastfood",
            "burger": "base_food_fastfood",
            "coffee": "base_food_coffee",
            "starbucks": "base_food_coffee",
            "taxi": "base_transport_taxi",
            "yandex go": "base_transport_taxi",
            "yandex.taxi": "base_transport_taxi",
            "uber": "base_transport_taxi",
            "aero": "base_travel_flights",
            "airlines": "base_travel_flights",
            "rjd": "base_travel_trains",
            "cinema": "base_entertainment_cinema",
            "кин": "base_entertainment_cinema",
            "apteka": "base_shopping_pharmacy",
            "аптека": "base_shopping_pharmacy",
        }
        for key, base_id in keyword_map.items():
            if key in text:
                return base_id
        return None

    def _fallback_stub(self, operation: Operation) -> Optional[str]:
        # Fallback to a safe default leaf category when nothing matched.
        if operation.type == OperationType.EXPENSE:
            return "base_unknown"
        return "base_income_other"

    def _track_unknown(self, operation: Operation) -> None:
        key = normalize_text(operation.bank_category or "unknown")
        self.unknown_tracker[key] = self.unknown_tracker.get(key, 0) + 1

    def _track_unmapped(self, bank: str, bank_category_norm: str) -> None:
        self.unmapped_counter[(normalize_text(bank), bank_category_norm)] += 1

    def unmapped_summary(self, limit: int = 20):
        items = []
        for (bank, cat), cnt in self.unmapped_counter.most_common(limit):
            items.append({"bank": bank, "bank_category": cat, "count": cnt})
        return items

    def _ml_model_predict(self, operation: Operation) -> Optional[str]:
        if not self.ml_model or not self.ml_model.is_ready():
            return None
        return self.ml_model.predict(operation)

    def _llm_predict(self, operation: Operation) -> Optional[str]:
        if not self.llm_categorizer or not self.llm_categorizer.is_ready():
            return None
        return self.llm_categorizer.predict(operation)


def categorize_vault(vault, pipeline: CategorizationPipeline) -> None:
    for op in vault.operations:
        pipeline.categorize(op)


def reclassify_unknown(vault, pipeline: CategorizationPipeline) -> None:
    """
    Переклассифицировать только операции с category_id == None или base_unknown.
    Используется после обучения ML или обновления маппинга.
    """
    for op in vault.operations:
        if op.category_id is None or op.category_id == "base_unknown":
            op.category_id = None
            pipeline.categorize(op)
