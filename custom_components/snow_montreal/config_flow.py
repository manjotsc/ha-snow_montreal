"""Config flow for Montreal Snow Removal integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_STREET_ID,
    CONF_STREET_NAME,
    DOMAIN,
)
from .street_lookup import StreetLookup, StreetSegment

_LOGGER = logging.getLogger(__name__)

CONF_CIVIC_NUMBER = "civic_number"
CONF_STREET_SEARCH = "street_search"
CONF_SELECTED_STREET = "selected_street"
CONF_SETUP_METHOD = "setup_method"

METHOD_SEARCH = "search"
METHOD_MANUAL = "manual"

GEOBASE_URL = "https://donnees.montreal.ca/dataset/geobase-double"


class SnowMontrealConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Montreal Snow Removal."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._street_lookup: StreetLookup | None = None
        self._search_results: list[StreetSegment] = []
        self._last_civic: int | None = None
        self._last_street: str = ""

    async def _init_lookup(self) -> None:
        """Initialize and load street lookup data."""
        if self._street_lookup is None:
            cache_dir = Path(self.hass.config.config_dir) / ".storage" / DOMAIN
            self._street_lookup = StreetLookup(cache_dir)

        if not self._street_lookup.is_loaded:
            await self._street_lookup.async_load()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose setup method."""
        if user_input is not None:
            if user_input.get(CONF_SETUP_METHOD) == METHOD_MANUAL:
                return await self.async_step_manual()
            return await self.async_step_search()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SETUP_METHOD, default=METHOD_SEARCH): vol.In(
                        {
                            METHOD_SEARCH: "Search by address",
                            METHOD_MANUAL: "Enter street ID manually",
                        }
                    ),
                }
            ),
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address search step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            civic_number = user_input.get(CONF_CIVIC_NUMBER)
            street_search = user_input.get(CONF_STREET_SEARCH, "").strip()

            # Save for back navigation
            self._last_civic = civic_number
            self._last_street = street_search

            if not street_search:
                errors[CONF_STREET_SEARCH] = "street_required"
            else:
                await self._init_lookup()

                # Search for streets
                if civic_number:
                    self._search_results = self._street_lookup.search_by_address(
                        civic_number=civic_number,
                        street_name=street_search,
                        limit=20,
                    )
                else:
                    self._search_results = self._street_lookup.search(
                        query=street_search,
                        limit=20,
                    )

                if not self._search_results:
                    errors["base"] = "no_results"
                else:
                    return await self.async_step_select()

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CIVIC_NUMBER, default=self._last_civic): vol.Any(None, int),
                    vol.Required(CONF_STREET_SEARCH, default=self._last_street): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle street selection from search results."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_id = user_input.get(CONF_SELECTED_STREET)

            if selected_id == "_back":
                return await self.async_step_search()

            if selected_id:
                # Find the selected street
                for street in self._search_results:
                    if str(street.cote_rue_id) == selected_id:
                        # Check if already configured
                        await self.async_set_unique_id(f"{DOMAIN}_{street.cote_rue_id}")
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=street.display_name,
                            data={
                                CONF_STREET_ID: street.cote_rue_id,
                                CONF_STREET_NAME: street.display_name,
                            },
                        )

            errors["base"] = "invalid_selection"

        # Build selection options
        options = {
            str(street.cote_rue_id): street.full_description
            for street in self._search_results
        }
        options["_back"] = "< Back to search"

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SELECTED_STREET): vol.In(options),
                }
            ),
            errors=errors,
            description_placeholders={
                "count": str(len(self._search_results))
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual street ID entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            street_id = user_input.get(CONF_STREET_ID)
            street_name = user_input.get(CONF_STREET_NAME, "").strip()

            if not street_id:
                errors[CONF_STREET_ID] = "invalid_street_id"
            elif not street_name:
                errors[CONF_STREET_NAME] = "street_name_required"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{street_id}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=street_name,
                    data={
                        CONF_STREET_ID: int(street_id),
                        CONF_STREET_NAME: street_name,
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREET_ID): int,
                    vol.Required(CONF_STREET_NAME): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "geobase_url": GEOBASE_URL,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration - allows changing street name."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            street_name = user_input.get(CONF_STREET_NAME, "").strip()

            if street_name:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_STREET_NAME: street_name},
                    title=street_name,
                )
                return self.async_abort(reason="reconfigure_successful")
            else:
                errors[CONF_STREET_NAME] = "street_name_required"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STREET_NAME,
                        default=entry.data.get(CONF_STREET_NAME, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "street_id": str(entry.data.get(CONF_STREET_ID, "Unknown")),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return SnowMontrealOptionsFlow()


class SnowMontrealOptionsFlow(OptionsFlow):
    """Handle options flow - allows renaming street."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            street_name = user_input.get(CONF_STREET_NAME, "").strip()

            if street_name:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=street_name,
                    data={**self.config_entry.data, CONF_STREET_NAME: street_name},
                )
                return self.async_create_entry(title="", data={})
            else:
                errors[CONF_STREET_NAME] = "street_name_required"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STREET_NAME,
                        default=self.config_entry.data.get(CONF_STREET_NAME, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "street_id": str(self.config_entry.data.get(CONF_STREET_ID, "Unknown")),
            },
        )
