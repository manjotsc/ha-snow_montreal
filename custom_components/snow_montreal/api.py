"""API client for Montreal Planif-Neige snow removal service."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from zeep import AsyncClient
from zeep.exceptions import Fault, TransportError
from zeep.transports import AsyncTransport

from .const import WSDL_URL, WSDL_URL_SIM

_LOGGER = logging.getLogger(__name__)


class PlanifNeigeError(Exception):
    """Base exception for Planif-Neige API errors."""


class PlanifNeigeAuthError(PlanifNeigeError):
    """Authentication error."""


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
        return self.status_code in (1, 2, 5, 6)

    @property
    def state(self) -> str:
        """Return a simple state string."""
        state_map = {
            0: "unknown",
            1: "scheduled",
            2: "in_progress",
            3: "completed",
            4: "cancelled",
            5: "pending",
            6: "replanned",
        }
        return state_map.get(self.status_code, "unknown")


class PlanifNeigeClient:
    """Client for the Montreal Planif-Neige API."""

    def __init__(
        self,
        api_token: str,
        use_simulation: bool = False,
    ) -> None:
        """Initialize the API client.

        Args:
            api_token: API token obtained from Montreal Open Data.
            use_simulation: Use simulation/test endpoint instead of production.
        """
        self._api_token = api_token
        self._use_simulation = use_simulation
        self._client: AsyncClient | None = None
        self._wsdl_url = WSDL_URL_SIM if use_simulation else WSDL_URL

    async def _get_client(self) -> AsyncClient:
        """Get or create the SOAP client."""
        if self._client is None:
            transport = AsyncTransport()
            self._client = AsyncClient(self._wsdl_url, transport=transport)
        return self._client

    async def async_validate_token(self) -> bool:
        """Validate the API token by making a test request.

        Returns:
            True if the token is valid.

        Raises:
            PlanifNeigeAuthError: If the token is invalid.
            PlanifNeigeConnectionError: If connection fails.
        """
        try:
            client = await self._get_client()
            # Make a request for today's date to validate the token
            today = datetime.now().strftime("%Y-%m-%d")

            result = await client.service.GetPlanificationInfosForDate(
                fromDate=today,
                tokenString=self._api_token,
            )

            # Check response status
            if hasattr(result, "responseStatus"):
                if result.responseStatus == 0:
                    return True
                if result.responseStatus in (-1, -2):
                    raise PlanifNeigeAuthError(
                        f"Invalid API token: {getattr(result, 'responseDesc', 'Unknown error')}"
                    )
            return True

        except Fault as err:
            _LOGGER.error("SOAP Fault during token validation: %s", err)
            raise PlanifNeigeAuthError(f"API authentication failed: {err}") from err
        except TransportError as err:
            _LOGGER.error("Transport error during token validation: %s", err)
            raise PlanifNeigeConnectionError(
                f"Failed to connect to Planif-Neige API: {err}"
            ) from err
        except Exception as err:
            _LOGGER.error("Unexpected error during token validation: %s", err)
            raise PlanifNeigeConnectionError(
                f"Connection error: {err}"
            ) from err

    async def async_get_planifications(
        self,
        from_date: datetime | None = None,
    ) -> dict[int, StreetSnowStatus]:
        """Get snow removal planifications for all streets.

        Args:
            from_date: Start date for planification query. Defaults to today.

        Returns:
            Dictionary mapping street_id to StreetSnowStatus.

        Raises:
            PlanifNeigeError: If the API request fails.
        """
        if from_date is None:
            from_date = datetime.now()

        date_str = from_date.strftime("%Y-%m-%d")

        try:
            client = await self._get_client()
            result = await client.service.GetPlanificationsForDate(
                fromDate=date_str,
                tokenString=self._api_token,
            )

            return self._parse_planifications(result)

        except Fault as err:
            _LOGGER.error("SOAP Fault getting planifications: %s", err)
            raise PlanifNeigeError(f"API error: {err}") from err
        except TransportError as err:
            _LOGGER.error("Transport error getting planifications: %s", err)
            raise PlanifNeigeConnectionError(
                f"Connection error: {err}"
            ) from err

    async def async_get_street_status(
        self,
        street_ids: list[int],
        from_date: datetime | None = None,
    ) -> dict[int, StreetSnowStatus]:
        """Get snow removal status for specific streets.

        Args:
            street_ids: List of street IDs (coteRueId) to query.
            from_date: Start date for query. Defaults to today.

        Returns:
            Dictionary mapping street_id to StreetSnowStatus.
        """
        all_planifications = await self.async_get_planifications(from_date)

        return {
            street_id: status
            for street_id, status in all_planifications.items()
            if street_id in street_ids
        }

    async def async_get_planification_infos(
        self,
        from_date: datetime | None = None,
    ) -> dict[int, StreetSnowStatus]:
        """Get planification info (simplified status) for all streets.

        Args:
            from_date: Start date for query. Defaults to today.

        Returns:
            Dictionary mapping street_id to StreetSnowStatus.
        """
        if from_date is None:
            from_date = datetime.now()

        date_str = from_date.strftime("%Y-%m-%d")

        try:
            client = await self._get_client()
            result = await client.service.GetPlanificationInfosForDate(
                fromDate=date_str,
                tokenString=self._api_token,
            )

            return self._parse_planification_infos(result)

        except Fault as err:
            _LOGGER.error("SOAP Fault getting planification infos: %s", err)
            raise PlanifNeigeError(f"API error: {err}") from err
        except TransportError as err:
            _LOGGER.error("Transport error getting planification infos: %s", err)
            raise PlanifNeigeConnectionError(
                f"Connection error: {err}"
            ) from err

    def _parse_planifications(
        self, response: Any
    ) -> dict[int, StreetSnowStatus]:
        """Parse the GetPlanificationsForDate response."""
        result: dict[int, StreetSnowStatus] = {}

        if not hasattr(response, "planifications"):
            _LOGGER.debug("No planifications in response")
            return result

        planifications = response.planifications
        if not hasattr(planifications, "planification"):
            _LOGGER.debug("No planification entries")
            return result

        for p in planifications.planification:
            try:
                street_id = int(getattr(p, "coteRueId", 0))
                if street_id == 0:
                    continue

                status = StreetSnowStatus(
                    street_id=street_id,
                    municipality_id=getattr(p, "munid", None),
                    status_code=int(getattr(p, "etatDeneig", 0)),
                    status_label_fr="",
                    status_label_en="",
                    planned_start=self._parse_datetime(
                        getattr(p, "dateDebutPlanif", None)
                    ),
                    planned_end=self._parse_datetime(
                        getattr(p, "dateFinPlanif", None)
                    ),
                    replanned_start=self._parse_datetime(
                        getattr(p, "dateDebutReplanif", None)
                    ),
                    replanned_end=self._parse_datetime(
                        getattr(p, "dateFinReplanif", None)
                    ),
                    last_updated=self._parse_datetime(
                        getattr(p, "dateMaj", None)
                    ),
                )
                result[street_id] = status
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing planification: %s", err)
                continue

        return result

    def _parse_planification_infos(
        self, response: Any
    ) -> dict[int, StreetSnowStatus]:
        """Parse the GetPlanificationInfosForDate response."""
        result: dict[int, StreetSnowStatus] = {}

        if not hasattr(response, "planificationInfos"):
            _LOGGER.debug("No planificationInfos in response")
            return result

        infos = response.planificationInfos
        if not hasattr(infos, "planificationInfo"):
            _LOGGER.debug("No planificationInfo entries")
            return result

        for info in infos.planificationInfo:
            try:
                street_id = int(getattr(info, "coteRueId", 0))
                if street_id == 0:
                    continue

                status = StreetSnowStatus(
                    street_id=street_id,
                    municipality_id=None,
                    status_code=int(getattr(info, "codeStatus", 0)),
                    status_label_fr=getattr(info, "etatStatutLibelleFrancais", ""),
                    status_label_en=getattr(info, "etatStatutLibelleAnglais", ""),
                    planned_start=None,
                    planned_end=None,
                    replanned_start=None,
                    replanned_end=None,
                    last_updated=self._parse_datetime(
                        getattr(info, "dateMaj", None)
                    ),
                )
                result[street_id] = status
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing planification info: %s", err)
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
            # Try parsing ISO format
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        return None

    async def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            transport = self._client.transport
            if hasattr(transport, "session") and transport.session:
                await transport.session.close()
            self._client = None
