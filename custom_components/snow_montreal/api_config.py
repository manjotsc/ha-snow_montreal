"""Shared API configuration storage for Montreal Snow Removal."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.api_config"


class ApiConfigStore:
    """Store for shared API configuration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API config store."""
        self._hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {}

    @property
    def api_token(self) -> str | None:
        """Return the stored API token."""
        return self._data.get("api_token")

    @property
    def use_simulation(self) -> bool:
        """Return whether to use simulation endpoint."""
        return self._data.get("use_simulation", False)

    @property
    def has_api_token(self) -> bool:
        """Return True if an API token is configured."""
        return bool(self._data.get("api_token"))

    async def async_load(self) -> None:
        """Load the stored configuration."""
        data = await self._store.async_load()
        if data is not None:
            self._data = data
        _LOGGER.debug("Loaded API config: has_token=%s", self.has_api_token)

    async def async_save(
        self,
        api_token: str | None = None,
        use_simulation: bool | None = None,
    ) -> None:
        """Save the API configuration."""
        if api_token is not None:
            self._data["api_token"] = api_token
        if use_simulation is not None:
            self._data["use_simulation"] = use_simulation

        await self._store.async_save(self._data)
        _LOGGER.debug("Saved API config")

    async def async_clear(self) -> None:
        """Clear the stored API configuration."""
        self._data = {}
        await self._store.async_remove()


async def get_api_config_store(hass: HomeAssistant) -> ApiConfigStore:
    """Get or create the API config store."""
    if "api_config_store" not in hass.data.get(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})
        store = ApiConfigStore(hass)
        await store.async_load()
        hass.data[DOMAIN]["api_config_store"] = store

    return hass.data[DOMAIN]["api_config_store"]
