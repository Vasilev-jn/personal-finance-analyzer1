import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from finance_app.category_tree import iter_leaf_categories
from finance_app.domain import Operation
from finance_app.utils import build_features


ALLOWED_CATEGORY_IDS: List[str] = [cat.id for cat in iter_leaf_categories()]


@dataclass
class LLMStatus:
    ready: bool
    model: Optional[str]
    cache_size: int


class LLMCategorizer:
    """
    Thin client around a chat-completions style API (OpenAI-compatible).
    It asks the model to return a single base_* category id.
    """

    def __init__(
        self,
        api_key: Optional[str],
        model: Optional[str],
        api_url: str = "https://api.openai.com/v1/chat/completions",
        timeout: int = 12,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.timeout = timeout
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[Tuple[str, str, str, str, str], Tuple[float, str]] = {}

    def is_ready(self) -> bool:
        return bool(self.api_key and self.model and self.api_url)

    def status(self) -> LLMStatus:
        return LLMStatus(ready=self.is_ready(), model=self.model, cache_size=len(self._cache))

    def predict(self, operation: Operation) -> Optional[str]:
        if not self.is_ready():
            return None

        feats = build_features(operation)
        cache_key = (
            feats.merchant_norm,
            feats.bank_category_norm,
            feats.mcc or "",
            feats.text,
            feats.bank,
        )
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        payload = self._build_payload(operation, feats)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
        except Exception:
            return None

        if response.status_code != 200:
            return None

        guess = self._parse_response(response.json())
        if guess:
            self._write_cache(cache_key, guess)
        return guess

    def _build_payload(self, operation: Operation, feats) -> Dict[str, object]:
        user_payload = {
            "description": operation.description or "",
            "merchant": operation.merchant or "",
            "bank_category": operation.bank_category or "",
            "mcc": operation.mcc or "",
            "amount": float(operation.amount),
            "bank": operation.bank,
            "normalized_text": feats.text,
            "allowed_category_ids": ALLOWED_CATEGORY_IDS,
        }

        few_shots = [
            (
                {
                    "description": "Lenta supermarket purchase",
                    "merchant": "Lenta",
                    "bank_category": "supermarket",
                    "mcc": "5411",
                    "amount": -1543.2,
                    "bank": "tinkoff",
                },
                "base_shopping_groceries",
            ),
            (
                {
                    "description": "Yandex Go taxi ride",
                    "merchant": "Yandex Taxi",
                    "bank_category": "taxi",
                    "mcc": "4121",
                    "amount": -480,
                    "bank": "alfa",
                },
                "base_transport_taxi",
            ),
            (
                {
                    "description": "Apteka Izhevsk",
                    "merchant": "Apteka 36-6",
                    "bank_category": "pharmacy",
                    "mcc": "5122",
                    "amount": -920.5,
                    "bank": "tinkoff",
                },
                "base_shopping_pharmacy",
            ),
        ]

        messages = [
            {
                "role": "system",
                "content": (
                    "You classify bank operations into one category id. "
                    "Respond ONLY with JSON like {\"category_id\": \"base_transport_taxi\"}. "
                    "Use one of the allowed category ids provided by the user."
                ),
            }
        ]

        for shot_user, shot_label in few_shots:
            messages.append({"role": "user", "content": json.dumps(shot_user, ensure_ascii=True)})
            messages.append({"role": "assistant", "content": json.dumps({"category_id": shot_label})})

        messages.append({"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)})

        return {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 20,
            "messages": messages,
        }

    def _parse_response(self, data: Dict[str, object]) -> Optional[str]:
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not message:
            return None
        content = message.get("content")

        if isinstance(content, dict):
            candidate = content.get("category_id") or content.get("category")
            if self._is_allowed(candidate):
                return candidate  # type: ignore[arg-type]

        if isinstance(content, str):
            candidate = self._extract_from_text(content)
            if candidate:
                return candidate

        return None

    def _extract_from_text(self, content: str) -> Optional[str]:
        try:
            parsed = json.loads(content)
            candidate = parsed.get("category_id") or parsed.get("category")
            if self._is_allowed(candidate):
                return candidate  # type: ignore[arg-type]
        except Exception:
            pass

        for cid in ALLOWED_CATEGORY_IDS:
            if cid in content:
                return cid
        return None

    def _is_allowed(self, candidate: Optional[str]) -> bool:
        return bool(candidate) and candidate in ALLOWED_CATEGORY_IDS

    def _read_cache(self, key: Tuple[str, str, str, str, str]) -> Optional[str]:
        cached = self._cache.get(key)
        if not cached:
            return None
        ts, value = cached
        if time.time() - ts > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def _write_cache(self, key: Tuple[str, str, str, str, str], value: str) -> None:
        self._cache[key] = (time.time(), value)
