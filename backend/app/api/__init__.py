from fastapi import APIRouter

from app.api.routes import analysis, health, infrastructure, properties

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(infrastructure.router, prefix="/infrastructure", tags=["infrastructure"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
