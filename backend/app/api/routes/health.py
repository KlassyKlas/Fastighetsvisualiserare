from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.api.deps import SessionDep
from app.schemas import HealthStatus

router = APIRouter()

API_VERSION = "1.0.0"


@router.get("/health", response_model=HealthStatus)
async def health_check(session: SessionDep) -> HealthStatus:
    """Hälsokontroll som även verifierar databasanslutningen."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Databasen är inte tillgänglig") from exc
    return HealthStatus(database="ok", version=API_VERSION)
