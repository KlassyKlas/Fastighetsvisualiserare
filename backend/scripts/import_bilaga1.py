"""Generera attributtabellen för nationell plan ur Bilaga 1-arbetsboken.

Läser den publicerade Bilaga 1 till fastställd nationell plan för
transportinfrastrukturen 2026–2037 (XLSX) och skriver
``app/datasources/nationell_plan_bilaga1.json`` — objekt-id →
namn, fas, trafikslag, län och total objektkostnad. Filen är
genererad och redigeras aldrig för hand (samma princip som
``sampleData.json``); kör om skriptet vid ny planrevidering.

Arbetsboken hämtas från Trafikverket:
https://bransch.trafikverket.se/contentassets/2fca968f05c545d59749ce9d442e117a/bilaga1_nationell_plan_for_transportinfrastrukturen_2026-2037-webb.xlsx

    uv run python -m scripts.import_bilaga1 /sökväg/till/bilaga1.xlsx
"""

import argparse
import json
from pathlib import Path

import openpyxl

OUTPUT_PATH = Path(__file__).parents[1] / "app" / "datasources" / "nationell_plan_bilaga1.json"

# Kolumnindex (0-baserade) i arket "Bilaga 1". VARJE använd kolumn
# verifieras mot sin rubrik innan läsning så att en ändrad kolumnlayout
# ger ett tydligt fel i stället för tyst fel data — särskilt viktigt för
# kostnaden, som har flera snarlika grannkolumner.
KOL_FAS = 0
KOL_TRAFIKSLAG = 2
KOL_LAN = 3
KOL_OBJEKT_ID = 5
KOL_OBJEKT = 6
# "Total objektkostnad inklusive tillkommande finansieringar" — kolumnen
# "Total" (mnkr). Det är hela objektets kostnad, inte bara planperiodens.
KOL_KOSTNAD_TOTAL = 10

RUBRIKRAD = 5  # 1-baserat radnummer där kolumnrubrikerna står; data börjar under
# (rad, kolumn, förväntat rubrikprefix). Kostnadskolumnens rubrik är
# delad: grupprubriken står på rad 3 (över kolumn 9–10) och delrubriken
# "Total" på rad 6.
FORVANTADE_RUBRIKER = [
    (RUBRIKRAD, KOL_FAS, "Fasindelning"),
    (RUBRIKRAD, KOL_TRAFIKSLAG, "Trafik-slag"),
    (RUBRIKRAD, KOL_LAN, "Län"),
    (RUBRIKRAD, KOL_OBJEKT_ID, "Objekt ID"),
    (RUBRIKRAD, KOL_OBJEKT, "Objekt"),
    (3, KOL_KOSTNAD_TOTAL - 1, "Total objektkostnad"),
    (6, KOL_KOSTNAD_TOTAL, "Total"),
]


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_objects(workbook_path: Path) -> dict[str, dict[str, str | int | None]]:
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        sheet = workbook["Bilaga 1"]
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()

    for rad, kolumn, prefix in FORVANTADE_RUBRIKER:
        faktisk = _text(rows[rad - 1][kolumn])
        if faktisk is None or not faktisk.startswith(prefix):
            raise SystemExit(
                f"Oväntad kolumnlayout: rad {rad} kolumn {kolumn} har rubriken "
                f"{faktisk!r}, förväntade prefix {prefix!r}. "
                "Kontrollera arbetsboken och kolumnindexen."
            )

    objekt: dict[str, dict[str, str | int | None]] = {}
    for row in rows[RUBRIKRAD:]:
        objekt_id = _text(row[KOL_OBJEKT_ID])
        namn = _text(row[KOL_OBJEKT])
        if not objekt_id or not namn:
            continue
        kostnad = row[KOL_KOSTNAD_TOTAL]
        kostnad_mnkr = round(float(kostnad)) if isinstance(kostnad, int | float) else None
        objekt[objekt_id] = {
            "namn": namn,
            "fas": _text(row[KOL_FAS]),
            "trafikslag": _text(row[KOL_TRAFIKSLAG]),
            "lan": _text(row[KOL_LAN]),
            # 0 betyder "ingen kostnadsram angiven" i arbetsboken
            "kostnad_mnkr": kostnad_mnkr or None,
        }
    return objekt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="Sökväg till nedladdad Bilaga 1-arbetsbok")
    args = parser.parse_args()

    objekt = extract_objects(args.xlsx)
    if len(objekt) < 100:
        raise SystemExit(
            f"Bara {len(objekt)} objekt hittades — förväntade minst 100. "
            "Kontrollera att rätt arbetsbok angavs."
        )

    payload = json.dumps(objekt, ensure_ascii=False, indent=1, sort_keys=True)
    OUTPUT_PATH.write_text(payload + "\n", encoding="utf-8")
    print(f"Skrev {len(objekt)} objekt till {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
