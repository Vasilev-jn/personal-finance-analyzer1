# MoneyMap

MoneyMap is a privacy-first Flask application for local expense analysis. It imports bank CSV statements, categorizes transactions with rules plus optional ML/LLM helpers, and serves analytics in a local web UI.

## Privacy-First Approach

- The app is designed to run on your machine.
- Uploaded CSV files, saved state, and the local auth password stay in local storage.
- LLM-based categorization is optional and only becomes active when API credentials are provided through environment variables.

## What Is Implemented Now

- CSV import for Alfa and Tinkoff statements
- Domain model for accounts, operations, categories, and the in-memory `Vault`
- Categorization pipeline with rules, bank-category mapping, ML model, optional LLM client, and fallback logic
- Analytics endpoints for totals, category breakdowns, merchant breakdowns, trends, quick answers, and operations history
- Local password-based access control for the UI
- State persistence and model save/load helpers
- Pytest coverage for categorization, analytics, import, storage, utilities, and service behavior

## Architecture

- `app.py` - Flask entrypoint and HTTP API routes
- `finance_app/domain.py` - core entities such as `Operation`, `Account`, and `Vault`
- `finance_app/adapters/` - CSV parsers for supported banks
- `finance_app/services/import_service.py` - import pipeline into the domain model
- `finance_app/services/categorization.py` - categorization orchestration
- `finance_app/services/analytics_service.py` - analytics and quick-answer logic
- `finance_app/services/storage.py` - local state and password persistence
- `finance_app/services/ml_model.py` - lightweight ML categorizer
- `finance_app/services/llm_categorizer.py` - optional OpenAI-compatible categorizer client
- `finance_app/templates/` and `finance_app/static/` - local UI
- `tests/` - automated tests

## How To Run Locally

```bash
git clone https://github.com/Vasilev-jn/personal-finance-analyzer1.git
cd personal-finance-analyzer1
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

The Flask app starts on `http://localhost:5000`.

Optional environment variables for LLM categorization:

- `LLM_API_KEY` or `OPENAI_API_KEY`
- `LLM_MODEL` or `OPENAI_MODEL`
- `LLM_API_URL` or `OPENAI_BASE_URL`

## Tests

```bash
pytest
```

## Screenshots

![Main view and quick answers](docs/screenshots/main.png)
![Analytics](docs/screenshots/analitics.png)
![Operations history](docs/screenshots/history.png)
![Profile and settings](docs/screenshots/profile.png)

## Planned Improvements

- add export options for filtered analytics
- improve bank adapter coverage for more statement formats
- separate Flask routes into smaller modules if the API grows
- add more scenario-based tests for import edge cases

## License

MIT. See `LICENSE`.
