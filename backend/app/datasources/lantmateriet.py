"""Datakälla: Lantmäteriet (ej implementerad ännu).

Klassen är avsiktligt INTE registrerad i källregistret — den blir
synlig för synkronisering först när den faktiskt kan leverera data.

Relevanta API:er när åtkomst finns:
    - Direktåtkomst Fastighet (fastighetsindelning och taxeringsuppgifter)
    - Nationella geodataplattformen (NGP): detaljplaner — öppen datamängd,
      kräver konto och API-nyckel via Lantmäteriets API-portal
    - Höjddata och ortofoto (öppna data)

Observera koordinatsystem: Lantmäteriet levererar i regel SWEREF99 TM
(EPSG:3006) — transformation till WGS84 behövs vid implementation
(t.ex. via pyproj).
"""

from app.datasources.base import Bbox, DataSource, PropertyIngest


class LantmaterietDataSource(DataSource):
    name = "lantmateriet"
    display_name = "Lantmäteriet"

    async def fetch_properties(self, bbox: Bbox | None = None) -> list[PropertyIngest]:
        raise NotImplementedError(
            "Lantmäteriet-källan är inte implementerad ännu. "
            "Kräver API-nyckel och avtal med Lantmäteriet."
        )
