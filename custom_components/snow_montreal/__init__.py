"""Montreal Snow Removal integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import SnowMontrealCoordinator
from .street_lookup import get_street_lookup

_LOGGER = logging.getLogger(__name__)

# Config entry only, no YAML configuration
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_SEARCH_STREET = "search_street"
SERVICE_REFRESH_GEOBASE = "refresh_geobase"

ATTR_STREET_NAME = "street_name"
ATTR_CIVIC_NUMBER = "civic_number"

SERVICE_SEARCH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_STREET_NAME): cv.string,
        vol.Optional(ATTR_CIVIC_NUMBER): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Montreal Snow Removal component."""
    hass.data.setdefault(DOMAIN, {})

    # Register services
    async def handle_search_street(call: ServiceCall) -> ServiceResponse:
        """Handle the search_street service call."""
        street_name = call.data[ATTR_STREET_NAME]
        civic_number = call.data.get(ATTR_CIVIC_NUMBER)

        cache_dir = Path(hass.config.config_dir) / ".storage" / DOMAIN
        lookup = await get_street_lookup(cache_dir)

        if not lookup.is_loaded:
            await lookup.async_load()

        if civic_number:
            results = lookup.search_by_address(
                civic_number=civic_number,
                street_name=street_name,
                limit=20,
            )
        else:
            results = lookup.search(query=street_name, limit=20)

        return {
            "results": [
                {
                    "street_id": r.cote_rue_id,
                    "street_name": r.street_name,
                    "address_start": r.address_start,
                    "address_end": r.address_end,
                    "side": r.side,
                    "borough": r.borough,
                    "display_name": r.display_name,
                    "full_description": r.full_description,
                }
                for r in results
            ],
            "count": len(results),
        }

    async def handle_refresh_geobase(call: ServiceCall) -> None:
        """Handle the refresh_geobase service call."""
        cache_dir = Path(hass.config.config_dir) / ".storage" / DOMAIN
        lookup = await get_street_lookup(cache_dir)
        await lookup.async_load(force_refresh=True)
        _LOGGER.info("Geobase data refreshed successfully")

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_STREET,
        handle_search_street,
        schema=SERVICE_SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_GEOBASE,
        handle_refresh_geobase,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Montreal Snow Removal from a config entry."""
    coordinator = SnowMontrealCoordinator(hass, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: SnowMontrealCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
