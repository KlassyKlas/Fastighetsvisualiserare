"""DeSO-områden: listning, punktuppslag och upsert från datakällor.

Ytan (och därmed befolkningstätheten) beräknas per rad med
ST_Area över geography — meterriktigt oavsett latitud.
"""

from geoalchemy2 import Geography
from sqlalchemy import ColumnElement, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.datasources import Bbox, DesoAreaIngest
from app.models import DesoArea
from app.schemas import DesoAreaCollection, DesoAreaFeature
from app.services.geo import WGS84_SRID, intersects_bbox
from app.services.infrastructure import GEOJSON_DECIMALER
from app.services.serializers import deso_area_feature
from app.services.upsert import SyncCounts, upsert_rows

# DeSO-polygonerna är detaljerade — förenkla för kartlagret (~10 m
# tolerans). Gränserna är statistikytor, inte juridiska gränser.
DESO_FORENKLING_GRADER = 0.0001

_area_m2 = func.ST_Area(cast(DesoArea.geometry, Geography(srid=WGS84_SRID)))
_geojson = func.ST_AsGeoJSON(
    func.ST_SimplifyPreserveTopology(DesoArea.geometry, DESO_FORENKLING_GRADER),
    GEOJSON_DECIMALER,
)


def _filter_conditions(
    *,
    municipality_codes: list[str] | None,
    bbox: Bbox | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if municipality_codes:
        conditions.append(DesoArea.municipality_code.in_(municipality_codes))
    if bbox is not None:
        conditions.append(intersects_bbox(DesoArea.geometry, bbox))
    return conditions


async def list_deso_areas(
    session: AsyncSession,
    *,
    municipality_codes: list[str] | None = None,
    bbox: Bbox | None = None,
    limit: int = 2000,
    offset: int = 0,
) -> DesoAreaCollection:
    conditions = _filter_conditions(municipality_codes=municipality_codes, bbox=bbox)

    total = await session.scalar(select(func.count()).select_from(DesoArea).where(*conditions))

    rows = await session.execute(
        select(DesoArea, _geojson, _area_m2)
        .where(*conditions)
        .order_by(DesoArea.id)
        .limit(limit)
        .offset(offset)
    )
    features = [deso_area_feature(area, geojson, area_m2) for area, geojson, area_m2 in rows.all()]

    return DesoAreaCollection(
        features=features,
        numberMatched=total or 0,
        numberReturned=len(features),
    )


async def lookup_deso_area(
    session: AsyncSession, *, longitude: float, latitude: float
) -> DesoAreaFeature | None:
    """DeSO-området som innehåller punkten (ST_Covers hanterar gränsfall).

    Geometrin utelämnas i svaret — uppslaget driver statistikvisning i
    detaljpanelen, inte kartritning.
    """
    row = (
        await session.execute(
            select(DesoArea, _area_m2).where(
                func.ST_Covers(
                    DesoArea.geometry,
                    func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), WGS84_SRID),
                )
            )
        )
    ).first()
    if row is None:
        return None
    area, area_m2 = row
    return deso_area_feature(area, None, area_m2)


async def upsert_deso_areas(session: AsyncSession, items: list[DesoAreaIngest]) -> SyncCounts:
    """Skriv in DeSO-områden från en datakälla (konflikt på deso_code) — se services.upsert."""
    return await upsert_rows(
        session,
        DesoArea,
        items,
        conflict_key="deso_code",
        label="DeSO",
        allowed_geometry_types=("MultiPolygon",),
    )
