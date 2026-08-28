# Fastighetsvisualiserare

Svensk kartapp för fastighetsinvestering. All UI-text är på **svenska**
(med korrekta å/ä/ö); kodkommentarer och docstrings likaså.

## Kommandon

Backend (från `backend/`, kräver `uv`):
- `uv run pytest` — enhetstester; `INTEGRATION_TESTS=1 uv run pytest` kör även API-testerna (kräver PostGIS via `docker compose up -d` + `uv run alembic upgrade head`)
- `uv run ruff check . && uv run ruff format .` — lint + format (rader ≤100)
- `uv run uvicorn app.main:app --reload` — dev-server

Frontend (från `frontend/`):
- `npm test` / `npm run lint` / `npx tsc -b` / `npm run build`
- `npx prettier --check .` — CI kör denna utöver eslint; glöm inte lokalt
- `npm run typegen` — regenerera `src/api/schema.d.ts` från `../backend/openapi.json`

## Järnregler

1. **Kontraktet:** ändras API-ytan → kör `uv run python -m scripts.export_openapi`
   (backend) och `npm run typegen` (frontend) och committa `openapi.json` +
   `schema.d.ts` ihop med ändringen. CI diffar båda.
2. **Schemat ägs av Alembic.** Aldrig `create_all` i appkod. Modelländring →
   `uv run alembic revision --autogenerate -m "..."` (kräver databas; env.py
   har GeoAlchemy2:s alembic_helpers så spatiala index hanteras rätt).
   **Undantag:** på miljöer utan PostGIS-databas handskrivs migrationen
   (följ mönstret i 0002/0003) — CI kör `alembic upgrade head` + `alembic
   check` mot riktig PostGIS och fångar både trasiga migrationer och
   modell–schemadrift.
3. **Geometrier skrivs alltid via `app/services/geo.py`** (`from_shape` med
   SRID 4326). Rena WKT-strängar utan SRID avvisas av PostGIS.
4. **Spatial analys görs i PostGIS** (geography-cast för meter), inte i Python
   eller i klienten. Klientsidig filtrering finns bara för demo-läget
   (`frontend/src/lib/filters.ts`) och ska spegla backendens semantik.
5. **Demodata redigeras aldrig för hand** — `sampleData.json` genereras av
   `scripts/export_sample_data.py` från `app/seed_data.py`.
6. **Nya datakällor:** implementera `DataSource` i `backend/app/datasources/`,
   returnera typade ingest-modeller, registrera med `@register`. Fel ska
   kastas som `DataSourceError` — aldrig sväljas till tomma listor.

## Versionsval som inte är misstag

- TypeScript är pinnad till 5.9 (inte 6/7): `openapi-typescript` kräver ^5
  och typescript-eslint stöder <6.1.
- `sqlalchemy <2.1`-pin: 2.1 låg i beta vid bygget — höj medvetet.
- react-map-gl v8: importera från `'react-map-gl/mapbox'`, aldrig paketroten.
- Trafikverket: Situation **1.6** med `namespace="Road.TrafficInfo"` —
  äldre schemaversioner är nedsläckta av Trafikverket (mars 2026).
- ruff har explicit `select` i pyproject — 0.16 ändrade default-reglerna kraftigt.

## Struktur

- `backend/app/` — `api/routes` (tunna) → `services` (logik + PostGIS-frågor) →
  `models`/`schemas`; `datasources/` (externa källor + registry);
  `domain.py` (enums = enda sanningskälla, exponeras via OpenAPI)
- `frontend/src/` — `api/` (genererade typer + openapi-fetch + TanStack
  Query-fabriker), `components/Map/layers/`, `components/Sidebar/`,
  `store/uiStore.ts` (endast UI-state), `lib/` (rena hjälpfunktioner)
