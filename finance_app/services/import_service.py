from pathlib import Path
from typing import Iterable

from finance_app.adapters.alfa_adapter import import_alfa_csv
from finance_app.adapters.tinkoff_adapter import import_tinkoff_csv
from finance_app.services.categorization import CategorizationPipeline
from finance_app.domain import Vault, OperationType


def import_alfa_file_into_vault(vault: Vault, pipeline: CategorizationPipeline, path: str, file_id: str) -> int:
    operations = import_alfa_csv(vault, path, file_id)
    for op in operations:
        if op.type == OperationType.TRANSFER:
            op.category_id = op.category_id or "base_topup"
            op.categorization_source = op.categorization_source or "import"
            continue
        pipeline.categorize(op)
    return len(operations)


def import_tinkoff_file_into_vault(
    vault: Vault, pipeline: CategorizationPipeline, path: str, file_id: str
) -> int:
    operations = import_tinkoff_csv(vault, path, file_id)
    for op in operations:
        if op.type == OperationType.TRANSFER:
            op.category_id = op.category_id or "base_topup"
            op.categorization_source = op.categorization_source or "import"
            continue
        pipeline.categorize(op)
    return len(operations)
