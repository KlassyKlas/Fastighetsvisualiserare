from abc import ABC, abstractmethod


class DataSource(ABC):
    """Abstract base class for external data sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for this data source."""
        ...

    @abstractmethod
    async def fetch_infrastructure_projects(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[dict]:
        """Fetch infrastructure projects, optionally filtered by bounding box.

        Args:
            bbox: Optional (west, south, east, north) bounding box in WGS84.

        Returns:
            List of dicts with keys matching InfrastructureProject fields.
        """
        ...

    @abstractmethod
    async def fetch_properties(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[dict]:
        """Fetch properties, optionally filtered by bounding box.

        Args:
            bbox: Optional (west, south, east, north) bounding box in WGS84.

        Returns:
            List of dicts with keys matching Property fields.
        """
        ...
