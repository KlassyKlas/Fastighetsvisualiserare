from fastapi import APIRouter

from app.api.routes import analysis, demographics, health, infrastructure, planning, properties

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(infrastructure.router, prefix="/infrastructure", tags=["infrastructure"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(planning.router, prefix="/planning", tags=["planning"])
api_router.include_router(demographics.router, prefix="/demographics", tags=["demographics"])
