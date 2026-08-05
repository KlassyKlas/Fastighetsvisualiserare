import logging

from services.base_datasource import DataSource

logger = logging.getLogger(__name__)


class LantmaterietDataSource(DataSource):
    """Data source for Lantmateriet's property and map APIs.

    TODO: Implement when Lantmateriet API access is available.
    Relevant APIs:
        - Direktaccess Fastigheter (property data)
        - Direktaccess Adresser (address data)
        - Kartbilder (map tiles)
    """

    @property
    def source_name(self) -> str:
        return "lantmateriet"

    async def fetch_infrastructure_projects(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[dict]:
        """Lantmateriet does not provide infrastructure project data."""
        # TODO: Implement if relevant Lantmateriet datasets become available
        return []

    async def fetch_properties(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[dict]:
        """Fetch property data from Lantmateriet.

        TODO: Implement using Lantmateriet Direktaccess Fastigheter API.
        Requires an API key and approved access agreement with Lantmateriet.

        Expected flow:
        1. Query the Direktaccess API for properties within bbox
        2. Transform the response to match our Property model fields
        3. Return list of property dicts
        """
        # TODO: Implement Lantmateriet property data fetching
        logger.info("Lantmateriet data source not yet implemented")
        return []
