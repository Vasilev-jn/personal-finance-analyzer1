from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from finance_app.domain import OperationType, Vault
from finance_app.services import analytics_service, import_service
from finance_app.services.categorization import CategorizationPipeline
from finance_app.services.llm_categorizer import LLMCategorizer
from finance_app.services.ml_model import SimpleMLModel


def detect_bank(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="ignore") as fp:
        header = fp.readline().lower()
    is_alfa = "operationdate" in header and ";" not in header
    return "alfa" if is_alfa else "tinkoff"


def build_pipeline(model_path: Path) -> CategorizationPipeline:
    ml_model = SimpleMLModel()
    if model_path.exists():
        ml_model.load(model_path)
    llm = LLMCategorizer(api_key=None, model=None)
    return CategorizationPipeline(ml_model=ml_model, llm_categorizer=llm)


def run_dataset(folder: Path, model_path: Path) -> int:
    files = sorted([p for p in folder.iterdir() if p.is_file()])
    if not files:
        print(f"No files found in {folder}")
        return 1

    vault = Vault()
    pipeline = build_pipeline(model_path)
    per_file: list[tuple[str, str, int, int, int]] = []

    for idx, path in enumerate(files, start=1):
        bank = detect_bank(path)
        file_id = f"ops-{idx:03d}"
        if bank == "alfa":
            imported, report = import_service.import_alfa_file_into_vault(
                vault, pipeline, str(path), file_id, include_report=True
            )
        else:
            imported, report = import_service.import_tinkoff_file_into_vault(
                vault, pipeline, str(path), file_id, include_report=True
            )
        per_file.append(
            (
                path.name,
                bank,
                imported,
                int(report.get("rows_total", 0)),
                int(report.get("skipped", 0)),
            )
        )

    totals = analytics_service.compute_totals(vault)
    unknown_count = len(analytics_service.unknown_operations(vault))
    top_expense = analytics_service.breakdown_by_base(vault, limit=10, op_type=OperationType.EXPENSE)
    top_income = analytics_service.breakdown_by_base(vault, limit=10, op_type=OperationType.INCOME)

    print("FILES SUMMARY:")
    for name, bank, imported, rows_total, skipped in per_file:
        print(
            f"{name}\tbank={bank}\timported={imported}\trows={rows_total}\tskipped={skipped}"
        )

    print("\nTOTALS:")
    print(f"operations={len(vault.operations)} unknown={unknown_count}")
    print(
        f"income={totals.get('income', 0)} "
        f"expense={totals.get('expense', 0)} "
        f"net={totals.get('net', 0)}"
    )

    print("\nTOP EXPENSE BASE:")
    for item in top_expense:
        print(f"{item['id']}\t{item['name']}\t{item['amount']}")

    print("\nTOP INCOME BASE:")
    for item in top_income:
        print(f"{item['id']}\t{item['name']}\t{item['amount']}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch import and analytics dry-run for operations folder."
    )
    parser.add_argument(
        "--folder",
        default="operations",
        help="Folder with CSV statements (default: operations)",
    )
    parser.add_argument(
        "--model-path",
        default="models/expense_clf.pkl",
        help="Path to optional trained ML model (default: models/expense_clf.pkl)",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        print(f"Folder does not exist: {folder}")
        return 1

    return run_dataset(folder=folder, model_path=Path(args.model_path))


if __name__ == "__main__":
    raise SystemExit(main())
