"""API client for Montreal Planif-Neige snow removal service (Public API)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import aiohttp

from .const import (
    PUBLIC_API_DATA_URL,
    PUBLIC_API_METADATA_URL,
    SNOW_STATE_MAP,
    STATE_LABELS,
)

_LOGGER = logging.getLogger(__name__)

# Request timeout in seconds
REQUEST_TIMEOUT = 30


class PlanifNeigeError(Exception):
    """Base exception for Planif-Neige API errors."""


class PlanifNeigeConnectionError(PlanifNeigeError):
    """Connection error."""


@dataclass
class StreetSnowStatus:
    """Snow removal status for a street segment."""

    street_id: int
    municipality_id: int | None
    status_code: int
    status_label_fr: str
    status_label_en: str
    planned_start: datetime | None
    planned_end: datetime | None
    replanned_start: datetime | None
    replanned_end: datetime | None
    last_updated: datetime | None

    @property
    def is_active(self) -> bool:
        """Return True if snow removal is currently active or planned."""
        # Active states: scheduled (2), rescheduled (3), or in_progress (5)
        return self.status_code in (2, 3, 5)

    @property
    def is_parking_restricted(self) -> bool:
        """Return True if parking is restricted (snow removal scheduled or in progress)."""
        # Parking restricted: scheduled (2), rescheduled (3), or in_progress (5)
        return self.status_code in (2, 3, 5)

    @property
    def state(self) -> str:
        """Return a simple state string."""
        return SNOW_STATE_MAP.get(self.status_code, "unknown")


@dataclass
class ApiMetadata:
    """Metadata about the API data."""

    last_update: datetime | None
    from_date: datetime | None
    record_count: int
    status: str


class PlanifNeigeClient:
    """Client for the Montreal Planif-Neige Public API."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the API client.

        Args:
            session: Optional aiohttp session. If not provided, one will be created.
        """
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def async_get_metadata(self) -> ApiMetadata:
        """Get metadata about the API data.

        Returns:
            ApiMetadata with last update time and record count.

        Raises:
            PlanifNeigeConnectionError: If connection fails.
        """
        try:
            session = await self._get_session()
            async with session.get(
                PUBLIC_API_METADATA_URL,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                response.raise_for_status()
                # GitHub raw returns text/plain, so disable content-type check
                data = await response.json(content_type=None)

                return ApiMetadata(
                    last_update=self._parse_datetime(data.get("last_update")),
                    from_date=self._parse_datetime(data.get("from_date")),
                    record_count=data.get("record_count", 0),
                    status=data.get("status", "unknown"),
                )

        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error getting metadata: %s", err)
            raise PlanifNeigeConnectionError(f"Connection error: {err}") from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout getting metadata")
            raise PlanifNeigeConnectionError("Request timed out") from err

    async def async_get_planifications(self) -> dict[int, StreetSnowStatus]:
        """Get snow removal planifications for all streets.

        Returns:
            Dictionary mapping street_id to StreetSnowStatus.

        Raises:
            PlanifNeigeError: If the API request fails.
        """
        try:
            session = await self._get_session()
            async with session.get(
                PUBLIC_API_DATA_URL,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                response.raise_for_status()
                # GitHub raw returns text/plain, so disable content-type check
                data = await response.json(content_type=None)

                # API returns {"planifications": [...]} wrapper
                if isinstance(data, dict) and "planifications" in data:
                    data = data["planifications"]

                return self._parse_planifications(data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error getting planifications: %s", err)
            raise PlanifNeigeConnectionError(f"Connection error: {err}") from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout getting planifications")
            raise PlanifNeigeConnectionError("Request timed out") from err

    async def async_get_street_status(
        self,
        street_ids: list[int],
    ) -> dict[int, StreetSnowStatus]:
        """Get snow removal status for specific streets.

        Args:
            street_ids: List of street IDs (coteRueId) to query.

        Returns:
            Dictionary mapping street_id to StreetSnowStatus.
        """
        all_planifications = await self.async_get_planifications()

        return {
            street_id: status
            for street_id, status in all_planifications.items()
            if street_id in street_ids
        }

    def _parse_planifications(self, data: list[dict[str, Any]]) -> dict[int, StreetSnowStatus]:
        """Parse the JSON response into StreetSnowStatus objects."""
        result: dict[int, StreetSnowStatus] = {}

        if not isinstance(data, list):
            _LOGGER.debug("Expected list, got %s", type(data))
            return result

        for entry in data:
            try:
                # Public API field: cote_rue_id
                street_id = entry.get("cote_rue_id") or entry.get("coteRueId") or 0
                street_id = int(street_id)
                if street_id == 0:
                    continue

                # Public API field: etat_deneig
                status_code = int(entry.get("etat_deneig") or entry.get("etatDeneig") or 0)

                status = StreetSnowStatus(
                    street_id=street_id,
                    # Public API field: mun_id
                    municipality_id=entry.get("mun_id") or entry.get("munid"),
                    status_code=status_code,
                    status_label_fr=STATE_LABELS["fr"].get(status_code, "Inconnu"),
                    status_label_en=STATE_LABELS["en"].get(status_code, "Unknown"),
                    # Public API field: date_deb_planif (not date_debut_planif)
                    planned_start=self._parse_datetime(
                        entry.get("date_deb_planif") or entry.get("dateDebutPlanif")
                    ),
                    # Public API field: date_fin_planif
                    planned_end=self._parse_datetime(
                        entry.get("date_fin_planif") or entry.get("dateFinPlanif")
                    ),
                    # Public API field: date_deb_replanif (not date_debut_replanif)
                    replanned_start=self._parse_datetime(
                        entry.get("date_deb_replanif") or entry.get("dateDebutReplanif")
                    ),
                    # Public API field: date_fin_replanif
                    replanned_end=self._parse_datetime(
                        entry.get("date_fin_replanif") or entry.get("dateFinReplanif")
                    ),
                    # Public API field: date_maj
                    last_updated=self._parse_datetime(
                        entry.get("date_maj") or entry.get("dateMaj")
                    ),
                )
                result[street_id] = status
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing entry: %s", err)
                continue

        return result

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse a datetime value from the API response."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            # Try parsing various ISO formats
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        return None

    async def close(self) -> None:
        """Close the client connection."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
