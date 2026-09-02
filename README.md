# Fastighetsvisualiserare

Kartverktyg för fastighetsinvestering i Sverige: visualiserar fastigheter
och infrastrukturprojekt (Trafikverket) på en 3D-karta och analyserar
vilka fastigheter som berörs av kommande projekt — direkt i PostGIS.

**Stack:** React 19 + Vite + Tailwind 4 + Mapbox GL (react-map-gl v8) +
TanStack Query · FastAPI (async) + SQLAlchemy 2 + PostGIS + Alembic · uv

```
frontend/  React-SPA. API-typer genereras från backendens OpenAPI-schema.
backend/   FastAPI + PostGIS. Datakällor registreras i app/datasources/.
```

## Kom igång (utveckling)

Krav: Docker (för databasen), [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
# 1. Databas
docker compose up -d

# 2. Backend
cd backend
cp .env.example .env                 # fyll i TRAFIKVERKET_API_KEY
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed        # exempeldata (idempotent)
uv run uvicorn app.main:app --reload # http://localhost:8000/docs

# 3. Frontend (nytt terminalfönster)
cd frontend
cp .env.example .env                 # fyll i VITE_MAPBOX_TOKEN
npm install
npm run dev                          # http://localhost:5173
```

Utan backend startar frontenden i ett **synligt demo-läge** med
exempeldata. Utan Mapbox-token visas en instruktionsruta.

## Hela stacken i Docker

```bash
cp .env.example .env   # TRAFIKVERKET_API_KEY + VITE_MAPBOX_TOKEN
docker compose --profile full up --build
# Frontend: http://localhost:8080 — API: http://localhost:8000/docs
```

> Har du en gammal databasvolym från postgis 16? Kör `docker compose down -v`
> en gång — imagen är uppgraderad till postgis/postgis:17-3.5.

## Arkitekturen i korthet

- **Kontraktet har en enda källa.** Pydantic-scheman + domänenums i
  backend genererar `backend/openapi.json`, som i sin tur genererar
  frontendens TypeScript-typer (`npm run typegen`). CI failar om något
  av leden glider isär.
- **Geoanalysen bor i databasen.** Påverkanszoner buffras med
  `ST_Buffer` över geography (meter) för punkter, linjer och ytor;
  berörda fastigheter och närliggande projekt beräknas med `ST_DWithin`.
  Klienten renderar bara.
- **Datakällor är pluggbara.** En källa implementerar `DataSource`,
  returnerar typade ingest-modeller och registreras med `@register` —
  då finns den automatiskt på `POST /api/v1/infrastructure/sync/{namn}`
  och i lagerpanelens synkknappar. Implementerade: `trafikverket`
  (Situation 1.6, kräver API-nyckel) och `nationell_plan`
  (investeringsprojekt: korridorer från riksintressetjänsten +
  kostnad/fas ur Bilaga 1, ingen nyckel); Lantmäteriet är stubbad.
  Bilaga 1-tabellen regenereras med `scripts/import_bilaga1.py` vid
  ny planrevidering.
- **Demo-läget kan inte ljuga.** Exempeldatat genereras från backendens
  seed-fixturer och har API:ts exakta form; när det används visas det
  tydligt i gränssnittet.

## Vanliga kommandon

| Var | Kommando | Gör |
|---|---|---|
| backend/ | `uv run pytest` | Tester (integrationsdelen kräver `INTEGRATION_TESTS=1` + databas) |
| backend/ | `uv run ruff check . && uv run ruff format .` | Lint + format |
| backend/ | `uv run alembic revision --autogenerate -m "..."` | Ny migration |
| backend/ | `uv run python -m scripts.export_openapi` | Uppdatera `openapi.json` |
| backend/ | `uv run python -m scripts.export_sample_data` | Uppdatera demodatat |
| frontend/ | `npm run typegen` | Regenerera API-typer från `openapi.json` |
| frontend/ | `npm test` / `npm run lint` / `npx tsc -b` | Tester / lint / typkontroll |

Ändrar du API:t: kör `export_openapi` + `typegen` och committa båda —
annars säger CI ifrån.

## API-nycklar

| Nyckel | Var | Källa |
|---|---|---|
| Trafikverket | `backend/.env` (exponeras aldrig mot klienten) | <https://data.trafikverket.se> |
| Mapbox | `frontend/.env` | <https://account.mapbox.com/access-tokens/> |

## Färdplan (idéer i prioritetsordning)

1. ~~Riktiga investeringsprojekt från Trafikverket (nationell plan)~~ — byggt: datakällan
   `nationell_plan` hämtar korridorer från riksintressetjänsten och berikar med kostnad/fas
   ur Bilaga 1 (synka via lagerpanelen)
2. ~~Närhetspoäng~~ — byggd: Analys-fliken rankar fastigheter med transparent poängmodell
3. ~~Tidsreglage~~ — byggt: dra i årsreglaget under filterraden
4. ~~Isokroner (restid) via Mapbox Isochrone API~~ — byggt: restidsanalys i Analys-fliken
   (gång/cykel/bil, upp till fyra restider à ≤60 min; startpunkt via kartklick eller
   "Restider härifrån" i detaljpanelerna; fungerar även i demo-läge)
5. ~~Detaljplaner via Lantmäteriets NGP · SCB-demografi per DeSO-område~~ — byggt: två nya
   datakällor med egna kartlager (hämtas per kartvy). Detaljplaner färgas efter Boverkets
   planstatus och är klickbara; DeSO-choroplethen växlar mellan befolkning/täthet/inkomst/
   utbildning och fastighetspanelen visar områdesstatistik via PostGIS-uppslag. Utan
   Lantmäteriet-nycklar används den publika sökproxyn (sätt LANTMATERIET_CONSUMER_KEY/SECRET
   för riktiga API:t); SCB-källan är helt öppen
6. ~~Bevakade områden med notiser · exporterbara objektsrapporter~~ — byggt: rita ett
   område i Bevakning-fliken och få notisbadge när projekt/detaljplaner tillkommer eller
   ändras där (ST_Intersects + last_seen_at i PostGIS; localStorage-bevakningar i
   demo-läge). Objektsrapport skapas från fastighetens detaljpanel och exporteras via
   Skriv ut → Spara som PDF
7. ~~"Nytt sedan senast"~~ — byggt: överst i Bevakning-fliken listas projekt och detaljplaner
   som tillkommit eller ändrats i hela datamängden sedan ditt senaste besök (markör i
   webbläsaren), de senaste 7/30 dagarna eller senaste synken; notisbadgen räknar med dem och
   ett klick zoomar kartan till objektet. Synkkörningarna loggas i tabellen `sync_runs`
   (`GET /api/v1/infrastructure/sync/runs`); lagerpanelen visar senaste lyckade synk per
   källa och erbjuder "Visa vad som ändrades" direkt efter en synk. Demodatat har
   illustrativa tidsstämplar så att panelen fungerar även i demo-läge
8. ~~Delbara länkar~~ — byggt: filter, år, ägare, poängläge, lager, kartstil, flik, valt
   objekt och restidsanalys ligger i query-strängen (`?status=planerad&ar=2030&fastighet=12`),
   kartvyn i hashen (`#karta=zoom/lat/lng/bearing/pitch`, Mapbox). "Dela" i filterraden
   kopierar länken; en öppnad länk hämtar objektet med full geometri och öppnar exakt den
   delade kartvyn (saknar länken kartvy zoomas kartan till objektet). Standardvärden
   utelämnas så en orörd vy ger en ren adress; trasiga parametrar ignoreras
9. ~~Ägarvy~~ — byggt: Sök-flikens tomvy listar ägare med antal fastigheter, taxeringsvärde
   och kommuner (GROUP BY + ST_Extent i PostGIS via `GET /api/v1/properties/owners`); klick
   filtrerar kartan på ägaren och zoomar till innehavet, fastighetspanelen har "Visa allt
   ägaren äger" och filterraden visar det aktiva ägarfiltret. I demo-läge speglas
   aggregeringen klientsidigt
10. Förberäknade påverkanszoner: zon-kolumn som sätts vid synk i stället för
    ST_Buffer per anrop — korridorgeometrierna gör zonfrågan tung (~1,4 s)
