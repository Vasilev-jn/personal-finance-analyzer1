from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
import joblib
from pathlib import Path

from finance_app.category_tree import SERVICE_BASE_IDS
from finance_app.domain import Operation
from finance_app.utils import build_features


@dataclass
class MLStatus:
    trained: bool
    samples: int
    classes: List[str]
    metrics: Optional[Dict[str, float]] = None


class SimpleMLModel:
    """
    Лёгкая модель: TF-IDF по тексту/мерчанту/bank_category/mcc/bank + LogisticRegression.
    Обучается на операциях с уже проставленными категориями (исключая сервисные и unknown).
    """

    def __init__(self) -> None:
        self.pipeline: Optional[Pipeline] = None
        self.label_mapping: List[str] = []
        self.samples_count: int = 0
        self.last_metrics: Optional[Dict[str, float]] = None

    def fit(self, operations: Iterable[Operation]) -> MLStatus:
        texts: List[str] = []
        labels: List[str] = []

        for op in operations:
            if not op.category_id or op.category_id in SERVICE_BASE_IDS or op.category_id == "base_unknown":
                continue
            feats = build_features(op)
            text = " ".join(
                part
                for part in [
                    feats.text,
                    feats.bank_category_norm,
                    feats.merchant_norm,
                    feats.bank,
                    feats.mcc or "",
                ]
                if part
            )
            texts.append(text)
            labels.append(op.category_id)

        self.samples_count = len(texts)
        if len(set(labels)) < 2:
            self.pipeline = None
            self.label_mapping = []
            self.last_metrics = None
            return MLStatus(trained=False, samples=self.samples_count, classes=[], metrics=None)

        X_train, X_test, y_train, y_test = self._train_test_split_safe(texts, labels)

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        clf = LogisticRegression(max_iter=300, n_jobs=1, class_weight="balanced")
        self.pipeline = Pipeline([("tfidf", vectorizer), ("clf", clf)])
        self.pipeline.fit(X_train, y_train)

        metrics = None
        if X_test and y_test:
            y_pred = self.pipeline.predict(X_test)
            metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
            }
        self.last_metrics = metrics
        self.label_mapping = sorted(list(set(labels)))
        return MLStatus(trained=True, samples=self.samples_count, classes=self.label_mapping, metrics=metrics)

    def _train_test_split_safe(self, texts: List[str], labels: List[str]):
        try:
            return train_test_split(texts, labels, test_size=0.2, random_state=42, stratify=labels)
        except Exception:
            # Если не хватает примеров для стратификации, попробуем без неё
            try:
                return train_test_split(texts, labels, test_size=0.2, random_state=42)
            except Exception:
                return texts, [], labels, []

    def is_ready(self) -> bool:
        return self.pipeline is not None

    def predict(self, operation: Operation) -> Optional[str]:
        if not self.pipeline:
            return None
        feats = build_features(operation)
        text = " ".join(
            part
            for part in [
                feats.text,
                feats.bank_category_norm,
                feats.merchant_norm,
                feats.bank,
                feats.mcc or "",
            ]
            if part
        )
        try:
            return self.pipeline.predict([text])[0]
        except Exception:
            return None

    def status(self) -> MLStatus:
        return MLStatus(
            trained=self.is_ready(),
            samples=self.samples_count,
            classes=self.label_mapping,
            metrics=self.last_metrics,
        )

    def save(self, path: Path) -> None:
        if not self.pipeline:
            raise RuntimeError("Model is not trained")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "samples": self.samples_count,
                "classes": self.label_mapping,
                "metrics": self.last_metrics,
            },
            path,
        )

    def load(self, path: Path) -> bool:
        if not path.exists():
            return False
        data = joblib.load(path)
        self.pipeline = data.get("pipeline")
        self.samples_count = data.get("samples", 0)
        self.label_mapping = data.get("classes", [])
        self.last_metrics = data.get("metrics")
        return True
