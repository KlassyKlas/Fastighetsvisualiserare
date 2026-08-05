import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.connection import Base, engine

# Import all models so Base.metadata knows about them
import models  # noqa: F401

from api.routes import health, infrastructure, properties

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="Fastighetsvisualiserare API",
    description="API for Swedish real estate and infrastructure visualization",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(infrastructure.router, prefix="/api/infrastructure")
app.include_router(properties.router, prefix="/api/properties")


@app.on_event("startup")
async def startup_event():
    """Create database tables on startup."""
    logging.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables created successfully")
