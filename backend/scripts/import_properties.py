"""Importera egna fastigheter från CSV eller GeoJSON till databasen.

    uv run python -m scripts.import_properties FIL [--srid 3006] [--point-buffer-m 25]
        [--dry-run] [--strict] [--no-extra-metadata]

Filen tolkas av ``app.services.property_import`` (kolumnalias, svenska
talformat, WKT/GeoJSON eller lng/lat) och skrivs med ``upsert_properties``
— samma väg som ``scripts/seed.py``. Omkörning är säker: upserten nycklar
på fastighetsbeteckning och skriver bara faktiska ändringar.

Exitkod 1 om filen inte kan läsas, om inga rader är giltiga, eller om
``--strict`` är satt och någon rad har problem.
"""

import argparse
import asyncio
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn

import asyncpg
from sqlalchemy.exc import SQLAlchemyError

from app.schemas import PropertyCreate
from app.services.property_import import (
    ImportFormatError,
    ImportResult,
    RowProblem,
    parse_rows,
    read_file,
)
from app.services.upsert import SyncCounts

MAX_LISTED_PROBLEMS = 20
MAX_LISTED_ITEMS = 20

# Fel som betyder "kom inte åt / kunde inte skriva till databasen": nätverk och
# DNS (OSError), SQLAlchemy, samt asyncpg:s egna — de ärver varken OSError
# eller SQLAlchemyError, och fel lösenord eller okänd databas vid anslutning
# kommer just som asyncpg.PostgresError.
DATABASE_ERRORS = (OSError, SQLAlchemyError, asyncpg.PostgresError, asyncpg.InterfaceError)

# argparse:s egna feltexter som användaren faktiskt kan stöta på.
_ARGPARSE_MESSAGES = (
    ("the following arguments are required: ", "följande argument saknas: "),
    ("unrecognized arguments: ", "okända argument: "),
    ("expected one argument", "kräver ett värde"),
)


class _SwedishHelpFormatter(argparse.HelpFormatter):
    """Skriver "användning:" i stället för "usage:" före användningsraden."""

    def add_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: str | None = None,
    ) -> None:
        super().add_usage(usage, actions, groups, prefix or "användning: ")


class _SwedishArgumentParser(argparse.ArgumentParser):
    """argparse på svenska: hjälpen byggs i egna grupper (så att de engelska
    standardrubrikerna inte skrivs ut) och de vanligaste felen översätts."""

    def error(self, message: str) -> NoReturn:
        for english, swedish in _ARGPARSE_MESSAGES:
            message = message.replace(english, swedish)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: fel: {message}\n")


def _positive_float(text: str) -> float:
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' är inte ett tal") from None
    if value <= 0:
        raise argparse.ArgumentTypeError("måste vara större än 0")
    return value


def _epsg_code(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' är inte en EPSG-kod (heltal)") from None


def build_parser() -> argparse.ArgumentParser:
    parser = _SwedishArgumentParser(
        prog="python -m scripts.import_properties",
        description=(
            "Importera fastigheter från en CSV (rubrikrad; ; , eller tab) eller en "
            "GeoJSON FeatureCollection. Kolumner känns igen på svenska rubriker "
            "(Beteckning, Kommun, Ägare, Org.nr, Taxeringsvärde, Typ, Geometri, Lng/Lat …)."
        ),
        formatter_class=_SwedishHelpFormatter,
        add_help=False,
    )
    arguments = parser.add_argument_group("argument")
    arguments.add_argument("file", type=Path, metavar="FIL", help="CSV- eller GeoJSON-fil")
    options = parser.add_argument_group("flaggor")
    options.add_argument("-h", "--help", action="help", help="Visa den här hjälpen och avsluta")
    options.add_argument(
        "--srid",
        type=_epsg_code,
        default=4326,
        help="Koordinatsystem i filen (EPSG-kod), t.ex. 3006 för SWEREF99 TM. Standard: 4326",
    )
    options.add_argument(
        "--point-buffer-m",
        type=_positive_float,
        metavar="METER",
        help=(
            "Gör en kvadrat ±METER runt rader som bara har en punkt (lng/lat). "
            "Utan detta importeras punktrader utan geometri och syns inte på kartan"
        ),
    )
    options.add_argument(
        "--dry-run", action="store_true", help="Tolka och rapportera, men skriv inget"
    )
    options.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Avbryt före skrivningen (exitkod 1) om någon rad har problem, i stället "
            "för att hoppa över den"
        ),
    )
    options.add_argument(
        "--no-extra-metadata",
        action="store_true",
        help="Spara inte okända kolumner i metadata_json",
    )
    return parser


def _rader(count: int) -> str:
    return f"{count} rad" if count == 1 else f"{count} rader"


def _format_problem(problem: RowProblem) -> str:
    where = f"rad {problem.line}"
    if problem.designation:
        where += f" ({problem.designation})"
    return f"{where}: {problem.message}"


def _print_summary(result: ImportResult, path: Path) -> None:
    print(
        f"Läste {_rader(result.rows_read)} ur {path}: {len(result.items)} giltiga, "
        f"{result.failed_lines} med fel"
    )
    if result.column_mapping:
        mapped = ", ".join(f"{header} → {field}" for header, field in result.column_mapping.items())
        print(f"Kolumner: {mapped}")
    if result.extra_columns:
        print(f"Övriga kolumner sparas som metadata: {', '.join(result.extra_columns)}")

    if result.problems:
        print("Problem:")
        for problem in result.problems[:MAX_LISTED_PROBLEMS]:
            print(f"  {_format_problem(problem)}")
        remaining = len(result.problems) - MAX_LISTED_PROBLEMS
        if remaining > 0:
            print(f"  … och {remaining} till")

    if result.without_geometry:
        hint = ""
        if result.points_without_buffer:
            hint = (
                f" (varav {result.points_without_buffer} bara har en punkt: "
                "--point-buffer-m ger dem en yta)"
            )
        print(f"{_rader(result.without_geometry)} saknar polygon — visas inte på kartan{hint}")


def _print_items(items: list[PropertyCreate]) -> None:
    for item in items[:MAX_LISTED_ITEMS]:
        parts = [item.designation]
        if item.owner_name:
            parts.append(item.owner_name)
        if item.property_type:
            parts.append(item.property_type.value)
        parts.append("polygon" if item.geometry else "ingen geometri")
        print(f"  {' — '.join(parts)}")
    if len(items) > MAX_LISTED_ITEMS:
        print(f"  … och {len(items) - MAX_LISTED_ITEMS} till")


async def _write(items: list[PropertyCreate]) -> SyncCounts:
    """Skriv in raderna med samma upsert som seed.py.

    app.db importeras först här: modulen skapar motorn vid import och
    läser DATABASE_URL — --dry-run ska fungera helt utan databas. Skriptet
    skapar en egen motor i stället för att låna app.db.engine, så att det
    kan köras i en egen event-loop (t.ex. i en tråd från integrationstestet)
    utan att dela anslutningar med en annan loop.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db import create_engine
    from app.services.properties import upsert_properties

    engine = create_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            counts = await upsert_properties(session, items)
            await session.commit()
    finally:
        await engine.dispose()
    return counts


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path: Path = args.file

    try:
        # Läsarna numrerar raderna: fysisk rad i CSV:n, feature-nummer i GeoJSON.
        result = parse_rows(
            read_file(path),
            srid=args.srid,
            point_buffer_m=args.point_buffer_m,
            extra_to_metadata=not args.no_extra_metadata,
        )
    except (ImportFormatError, OSError) as exc:
        print(f"Fel: {exc}", file=sys.stderr)
        return 1

    _print_summary(result, path)

    if args.strict and result.problems:
        print("Avbryter (--strict): filen har problem — inget skrivs.")
        return 1
    if not result.items:
        print("Inga giltiga rader — inget skrivs.")
        return 1
    if args.dry_run:
        print(f"Torrkörning — inget skrivs. {len(result.items)} fastigheter skulle importeras:")
        _print_items(result.items)
        return 0

    try:
        counts = asyncio.run(_write(result.items))
    except DATABASE_ERRORS as exc:
        print(
            f"Fel: kunde inte skriva till databasen ({type(exc).__name__}): {exc}", file=sys.stderr
        )
        return 1
    print(
        f"Fastigheter: {counts.upserted} inskrivna, {counts.unchanged} oförändrade, "
        f"{counts.skipped} överhoppade"
    )
    if args.strict and counts.skipped:
        # Skrivningen är redan committad — det som gick in ligger kvar.
        print(
            f"Fel (--strict): databasen hoppade över {_rader(counts.skipped)} (se loggen) — "
            "övriga rader är inskrivna.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
