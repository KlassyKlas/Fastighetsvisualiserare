"""Domänvärden som delas av modeller, scheman och datakällor.

Dessa enums är den enda sanningskällan för status- och typvärden.
De exponeras via OpenAPI-schemat och genereras därifrån till
frontendens TypeScript-typer.
"""

from enum import StrEnum


class ProjectStatus(StrEnum):
    PLANERAD = "planerad"
    PAGAENDE = "pågående"
    AVSLUTAD = "avslutad"


class ProjectType(StrEnum):
    VAG = "väg"
    JARNVAG = "järnväg"
    KOLLEKTIVTRAFIK = "kollektivtrafik"
    BRO = "bro"
    TUNNEL = "tunnel"
    CYKELVAG = "cykelväg"
    OVRIGT = "övrigt"


class WatchEventKind(StrEnum):
    """Händelsetyp i ett bevakat område sedan användaren senast tittade."""

    NYTT = "nytt"
    ANDRAT = "ändrat"


class PropertyType(StrEnum):
    BOSTAD = "bostad"
    KONTOR = "kontor"
    HANDEL = "handel"
    INDUSTRI = "industri"
    UTBILDNING = "utbildning"
    VILLA = "villa"
