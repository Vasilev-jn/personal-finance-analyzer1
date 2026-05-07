from typing import Dict, Tuple

from finance_app.adapters.alfa_adapter import import_alfa_csv
from finance_app.adapters.sber_adapter import import_sber_xlsx
from finance_app.adapters.tinkoff_adapter import import_tinkoff_csv
from finance_app.adapters.vtb_adapter import import_vtb_pdf
from finance_app.services.categorization import CategorizationPipeline
from finance_app.domain import Vault, OperationType


def _categorize_operations(vault: Vault, pipeline: CategorizationPipeline, operations) -> Tuple[int, int]:
    categorized = 0
    transfers = 0
    for op in operations:
        if op.type == OperationType.TRANSFER:
            op.category_id = op.category_id or "base_topup"
            op.categorization_source = op.categorization_source or "import"
            transfers += 1
            continue
        pipeline.categorize(op)
        categorized += 1
    return categorized, transfers


def import_alfa_file_into_vault(
    vault: Vault,
    pipeline: CategorizationPipeline,
    path: str,
    file_id: str,
    include_report: bool = False,
) -> int | tuple[int, Dict[str, object]]:
    report: Dict[str, object] = {}
    operations = import_alfa_csv(vault, path, file_id, report=report)
    categorized, transfers = _categorize_operations(vault, pipeline, operations)
    report["categorized"] = categorized
    report["transfers"] = transfers
    if include_report:
        return len(operations), report
    return len(operations)


def import_tinkoff_file_into_vault(
    vault: Vault,
    pipeline: CategorizationPipeline,
    path: str,
    file_id: str,
    include_report: bool = False,
) -> int | tuple[int, Dict[str, object]]:
    report: Dict[str, object] = {}
    operations = import_tinkoff_csv(vault, path, file_id, report=report)
    categorized, transfers = _categorize_operations(vault, pipeline, operations)
    report["categorized"] = categorized
    report["transfers"] = transfers
    if include_report:
        return len(operations), report
    return len(operations)


def import_sber_file_into_vault(
    vault: Vault,
    pipeline: CategorizationPipeline,
    path: str,
    file_id: str,
    include_report: bool = False,
) -> int | tuple[int, Dict[str, object]]:
    report: Dict[str, object] = {}
    operations = import_sber_xlsx(vault, path, file_id, report=report)
    categorized, transfers = _categorize_operations(vault, pipeline, operations)
    report["categorized"] = categorized
    report["transfers"] = transfers
    if include_report:
        return len(operations), report
    return len(operations)


def import_vtb_file_into_vault(
    vault: Vault,
    pipeline: CategorizationPipeline,
    path: str,
    file_id: str,
    include_report: bool = False,
) -> int | tuple[int, Dict[str, object]]:
    report: Dict[str, object] = {}
    operations = import_vtb_pdf(vault, path, file_id, report=report)
    categorized, transfers = _categorize_operations(vault, pipeline, operations)
    report["categorized"] = categorized
    report["transfers"] = transfers
    if include_report:
        return len(operations), report
    return len(operations)
