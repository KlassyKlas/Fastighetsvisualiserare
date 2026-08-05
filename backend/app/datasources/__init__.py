# Importeras för sina @register-sidoeffekter
from app.datasources import (
    detaljplaner,  # noqa: F401  (registrerar DetaljplanerDataSource)
    nationell_plan,  # noqa: F401  (registrerar NationellPlanDataSource)
    scb_deso,  # noqa: F401  (registrerar ScbDesoDataSource)
    trafikverket,  # noqa: F401  (registrerar TrafikverketDataSource)
)
from app.datasources.base import (
    Bbox,
    DataSource,
    DataSourceError,
    DesoAreaIngest,
    DetailPlanIngest,
    InfrastructureProjectIngest,
    PropertyIngest,
    UnknownDataSourceError,
    available_sources,
    get_datasource,
    register,
)

__all__ = [
    "Bbox",
    "DataSource",
    "DataSourceError",
    "DesoAreaIngest",
    "DetailPlanIngest",
    "InfrastructureProjectIngest",
    "PropertyIngest",
    "UnknownDataSourceError",
    "available_sources",
    "get_datasource",
    "register",
]
