"""DataUpdateCoordinator for Montreal Snow Removal."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PlanifNeigeClient,
    PlanifNeigeConnectionError,
    PlanifNeigeError,
    StreetSnowStatus,
)
from .const import CONF_STREET_ID, CONF_STREET_NAME, DOMAIN, UPDATE_INTERVAL

if TYPE_CHECKING:
    from .api_config import ApiConfigStore

_LOGGER = logging.getLogger(__name__)


class SnowMontrealCoordinator(DataUpdateCoordinator[dict[int, StreetSnowStatus] | None]):
    """Coordinator to manage fetching snow removal data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_config: ApiConfigStore,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.street_id = config_entry.data[CONF_STREET_ID]
        self.street_name = config_entry.data.get(CONF_STREET_NAME, f"Street {self.street_id}")
        self._api_config = api_config

        # Get API token from shared storage
        self._has_api_token = api_config.has_api_token

        if self._has_api_token:
            self.client = PlanifNeigeClient(
                api_token=api_config.api_token,
                use_simulation=api_config.use_simulation,
            )
        else:
            self.client = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.street_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL) if self._has_api_token else None,
        )

    @property
    def has_api_token(self) -> bool:
        """Return True if an API token is configured."""
        return self._has_api_token

    async def _async_update_data(self) -> dict[int, StreetSnowStatus] | None:
        """Fetch data from the API."""
        # If no API token, return None (sensors will show appropriate state)
        if not self._has_api_token or self.client is None:
            _LOGGER.debug("No API token configured, skipping data fetch")
            return None

        try:
            # Get all planifications - the API returns all streets at once
            # We filter to our specific street for efficiency
            data = await self.client.async_get_planifications()

            # If our street is not in the data, try the info endpoint
            if self.street_id not in data:
                info_data = await self.client.async_get_planification_infos()
                if self.street_id in info_data:
                    data[self.street_id] = info_data[self.street_id]

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
        if self.client is not None:
            await self.client.close()

    async def async_update_api_config(self) -> None:
        """Update client after API config changes and refresh data."""
        if self.client is not None:
            await self.client.close()

        self._has_api_token = self._api_config.has_api_token

        if self._has_api_token:
            self.client = PlanifNeigeClient(
                api_token=self._api_config.api_token,
                use_simulation=self._api_config.use_simulation,
            )
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL)
            # Trigger an immediate refresh
            await self.async_refresh()
        else:
            self.client = None
            self.update_interval = None
