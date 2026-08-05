# Fastighetsvisualiserare — backend

FastAPI-backend med PostGIS för svenska fastigheter och infrastrukturprojekt.
Se [repots huvud-README](../README.md) för helheten.

## Snabbstart

```bash
docker compose up -d db          # från repots rot: starta PostGIS
uv sync                          # installera beroenden
uv run alembic upgrade head      # kör migrationerna
uv run python -m scripts.seed    # ladda exempeldata
uv run uvicorn app.main:app --reload
```

API-dokumentation: <http://localhost:8000/docs>

## Vanliga kommandon

| Kommando | Gör |
|---|---|
| `uv run pytest` | Kör testerna (integrationstester hoppar över sig själva utan databas) |
| `uv run ruff check . && uv run ruff format --check .` | Lint + formatkontroll |
| `uv run python -m scripts.export_openapi` | Exportera `openapi.json` (frontendens typkälla) |
| `uv run python -m scripts.export_sample_data` | Exportera demodata till frontenden |
| `uv run alembic revision --autogenerate -m "..."` | Ny migration efter modelländring |
