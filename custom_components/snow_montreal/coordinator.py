"""DataUpdateCoordinator for Montreal Snow Removal."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PlanifNeigeClient,
    PlanifNeigeConnectionError,
    PlanifNeigeError,
    StreetSnowStatus,
)
from .const import CONF_STREET_ID, CONF_STREET_NAME, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SnowMontrealCoordinator(DataUpdateCoordinator[dict[int, StreetSnowStatus] | None]):
    """Coordinator to manage fetching snow removal data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.street_id = config_entry.data[CONF_STREET_ID]
        self.street_name = config_entry.data.get(CONF_STREET_NAME, f"Street {self.street_id}")

        # Use Home Assistant's shared aiohttp session
        session = async_get_clientsession(hass)
        self.client = PlanifNeigeClient(session=session)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.street_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[int, StreetSnowStatus] | None:
        """Fetch data from the API."""
        try:
            # Get all planifications from the public API
            data = await self.client.async_get_planifications()
            return data

        except PlanifNeigeConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except PlanifNeigeError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    def get_street_status(self) -> StreetSnowStatus | None:
        """Get the status for the configured street."""
        if self.data is None:
            return None
        return self.data.get(self.street_id)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and close connections."""
        # Note: We don't close the client here because we're using
        # Home Assistant's shared session which should not be closed
        pass
