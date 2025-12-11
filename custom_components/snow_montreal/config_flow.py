"""Config flow for Montreal Snow Removal integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import PlanifNeigeAuthError, PlanifNeigeClient, PlanifNeigeConnectionError
from .api_config import ApiConfigStore, get_api_config_store
from .const import (
    CONF_API_TOKEN,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    CONF_USE_SIMULATION,
    DOMAIN,
)
from .street_lookup import StreetLookup, StreetSegment

_LOGGER = logging.getLogger(__name__)

CONF_SEARCH_TYPE = "search_type"
CONF_CIVIC_NUMBER = "civic_number"
CONF_POSTAL_CODE = "postal_code"
CONF_STREET_SEARCH = "street_search"
CONF_FULL_ADDRESS = "full_address"
CONF_SELECTED_STREET = "selected_street"
CONF_SETUP_MODE = "setup_mode"

SETUP_MODE_WITH_TOKEN = "with_token"
SETUP_MODE_WITHOUT_TOKEN = "without_token"

SEARCH_TYPE_POSTAL_CODE = "postal_code"
SEARCH_TYPE_FULL_ADDRESS = "full_address"
SEARCH_TYPE_STREET_NAME = "street_name"
SEARCH_TYPE_MANUAL = "manual"


class SnowMontrealConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Montreal Snow Removal."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_config: ApiConfigStore | None = None
        self._street_lookup: StreetLookup | None = None
        self._search_results: list[StreetSegment] = []
        # Store previous search data for back navigation
        self._last_search_step: str | None = None
        self._last_search_data: dict[str, Any] = {}

    async def _get_api_config(self) -> ApiConfigStore:
        """Get the API config store."""
        if self._api_config is None:
            self._api_config = await get_api_config_store(self.hass)
        return self._api_config

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - check if API token exists."""
        api_config = await self._get_api_config()

        # If API token already exists, skip to street selection
        if api_config.has_api_token:
            return await self.async_step_search_type()

        # No API token yet, ask user how they want to proceed
        if user_input is not None:
            setup_mode = user_input.get(CONF_SETUP_MODE)
            if setup_mode == SETUP_MODE_WITH_TOKEN:
                return await self.async_step_api_token()
            else:
                # Skip token, go directly to street selection
                return await self.async_step_search_type()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SETUP_MODE, default=SETUP_MODE_WITHOUT_TOKEN): vol.In(
                        {
                            SETUP_MODE_WITHOUT_TOKEN: "Set up street now, add API token later",
                            SETUP_MODE_WITH_TOKEN: "I have an API token",
                        }
                    ),
                }
            ),
            description_placeholders={
                "request_email": "donneesouvertes@montreal.ca"
            },
        )

    async def async_step_api_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle API token entry and validation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_token = user_input.get(CONF_API_TOKEN, "").strip()
            use_simulation = user_input.get(CONF_USE_SIMULATION, False)

            if api_token:
                # Validate the API token
                client = PlanifNeigeClient(api_token, use_simulation=use_simulation)
                try:
                    await client.async_validate_token()
                    # Save to shared storage
                    api_config = await self._get_api_config()
                    await api_config.async_save(
                        api_token=api_token,
                        use_simulation=use_simulation,
                    )
                    return await self.async_step_search_type()
                except PlanifNeigeAuthError:
                    errors["base"] = "invalid_auth"
                except PlanifNeigeConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                finally:
                    await client.close()
            else:
                errors[CONF_API_TOKEN] = "token_required"

        return self.async_show_form(
            step_id="api_token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                    vol.Optional(CONF_USE_SIMULATION, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_search_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask user how they want to find their street."""
        if user_input is not None:
            search_type = user_input.get(CONF_SEARCH_TYPE)
            if search_type == SEARCH_TYPE_POSTAL_CODE:
                return await self.async_step_postal_code()
            elif search_type == SEARCH_TYPE_FULL_ADDRESS:
                return await self.async_step_full_address()
            elif search_type == SEARCH_TYPE_STREET_NAME:
                return await self.async_step_address_search()
            else:
                return await self.async_step_manual()

        return self.async_show_form(
            step_id="search_type",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SEARCH_TYPE, default=SEARCH_TYPE_POSTAL_CODE): vol.In(
                        {
                            SEARCH_TYPE_POSTAL_CODE: "Civic number + Postal code (easiest)",
                            SEARCH_TYPE_FULL_ADDRESS: "Enter full address",
                            SEARCH_TYPE_STREET_NAME: "Search by street name",
                            SEARCH_TYPE_MANUAL: "Enter street ID manually",
                        }
                    ),
                }
            ),
        )

    async def async_step_postal_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle postal code search - the easiest method."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Save the entered data for back navigation
            self._last_search_step = "postal_code"
            self._last_search_data = user_input.copy()

            civic_number = user_input.get(CONF_CIVIC_NUMBER)
            postal_code = user_input.get(CONF_POSTAL_CODE, "").strip()
            street_hint = user_input.get(CONF_STREET_SEARCH, "").strip()

            if not civic_number:
                errors[CONF_CIVIC_NUMBER] = "civic_number_required"
            elif not postal_code:
                errors[CONF_POSTAL_CODE] = "postal_code_required"
            else:
                # Validate postal code format (Canadian: A1A 1A1 or A1A1A1)
                postal_clean = postal_code.upper().replace(" ", "")
                if len(postal_clean) != 6 or not self._is_valid_postal_code(postal_clean):
                    errors[CONF_POSTAL_CODE] = "invalid_postal_code"
                else:
                    # Initialize street lookup if needed
                    if self._street_lookup is None:
                        cache_dir = Path(self.hass.config.config_dir) / ".storage" / DOMAIN
                        self._street_lookup = StreetLookup(cache_dir)

                    # Load geobase data
                    if not self._street_lookup.is_loaded:
                        await self._street_lookup.async_load()

                    # Search using postal code geocoding
                    self._search_results = await self._street_lookup.async_search_by_postal_code(
                        civic_number=civic_number,
                        postal_code=postal_code,
                        street_hint=street_hint if street_hint else None,
                        limit=15,
                    )

                    if not self._search_results:
                        errors["base"] = "no_results_postal"
                    else:
                        return await self.async_step_select_street()

        # Get defaults from previous data or empty
        defaults = self._last_search_data if self._last_search_step == "postal_code" else {}

        return self.async_show_form(
            step_id="postal_code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CIVIC_NUMBER,
                        default=defaults.get(CONF_CIVIC_NUMBER),
                    ): int,
                    vol.Required(
                        CONF_POSTAL_CODE,
                        default=defaults.get(CONF_POSTAL_CODE, ""),
                    ): str,
                    vol.Optional(
                        CONF_STREET_SEARCH,
                        default=defaults.get(CONF_STREET_SEARCH, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "example_postal": "H2X 1Y6"
            },
        )

    @staticmethod
    def _is_valid_postal_code(postal_code: str) -> bool:
        """Validate Canadian postal code format."""
        import re
        # Canadian postal code: letter-digit-letter digit-letter-digit
        pattern = r'^[A-Z]\d[A-Z]\d[A-Z]\d$'
        return bool(re.match(pattern, postal_code))

    async def async_step_full_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle full address search with geocoding."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Save the entered data for back navigation
            self._last_search_step = "full_address"
            self._last_search_data = user_input.copy()

            full_address = user_input.get(CONF_FULL_ADDRESS, "").strip()

            if not full_address:
                errors[CONF_FULL_ADDRESS] = "address_required"
            else:
                # Initialize street lookup if needed
                if self._street_lookup is None:
                    cache_dir = Path(self.hass.config.config_dir) / ".storage" / DOMAIN
                    self._street_lookup = StreetLookup(cache_dir)

                # Load geobase data
                if not self._street_lookup.is_loaded:
                    await self._street_lookup.async_load()

                # Search using geocoding + geobase matching
                self._search_results = await self._street_lookup.async_search_by_full_address(
                    address=full_address,
                    limit=15,
                )

                if not self._search_results:
                    errors["base"] = "no_results"
                else:
                    return await self.async_step_select_street()

        # Get defaults from previous data
        defaults = self._last_search_data if self._last_search_step == "full_address" else {}

        return self.async_show_form(
            step_id="full_address",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FULL_ADDRESS,
                        default=defaults.get(CONF_FULL_ADDRESS, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "example_address": "1234 Saint-Denis, Montreal"
            },
        )

    async def async_step_address_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address search step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Save the entered data for back navigation
            self._last_search_step = "address_search"
            self._last_search_data = user_input.copy()

            civic_number = user_input.get(CONF_CIVIC_NUMBER)
            street_search = user_input.get(CONF_STREET_SEARCH, "").strip()

            if not street_search:
                errors[CONF_STREET_SEARCH] = "street_required"
            else:
                # Initialize street lookup if needed
                if self._street_lookup is None:
                    cache_dir = Path(self.hass.config.config_dir) / ".storage" / DOMAIN
                    self._street_lookup = StreetLookup(cache_dir)

                # Load geobase data (shows loading indicator)
                if not self._street_lookup.is_loaded:
                    await self._street_lookup.async_load()

                # Search for streets
                if civic_number:
                    self._search_results = self._street_lookup.search_by_address(
                        civic_number=civic_number,
                        street_name=street_search,
                        limit=15,
                    )
                else:
                    self._search_results = self._street_lookup.search(
                        query=street_search,
                        limit=15,
                    )

                if not self._search_results:
                    errors["base"] = "no_results"
                else:
                    return await self.async_step_select_street()

        # Get defaults from previous data
        defaults = self._last_search_data if self._last_search_step == "address_search" else {}

        return self.async_show_form(
            step_id="address_search",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CIVIC_NUMBER,
                        default=defaults.get(CONF_CIVIC_NUMBER),
                    ): int,
                    vol.Required(
                        CONF_STREET_SEARCH,
                        default=defaults.get(CONF_STREET_SEARCH, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "download_note": "First search may take a moment to download street data."
            },
        )

    async def async_step_select_street(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle street selection from search results."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_id = user_input.get(CONF_SELECTED_STREET)

            if selected_id == "back":
                # Go back to the previous search step with data retained
                if self._last_search_step == "postal_code":
                    return await self.async_step_postal_code()
                elif self._last_search_step == "full_address":
                    return await self.async_step_full_address()
                elif self._last_search_step == "address_search":
                    return await self.async_step_address_search()
                else:
                    return await self.async_step_search_type()

            if selected_id:
                # Find the selected street
                selected_street = None
                for street in self._search_results:
                    if str(street.cote_rue_id) == selected_id:
                        selected_street = street
                        break

                if selected_street:
                    # Check if already configured
                    await self.async_set_unique_id(f"{DOMAIN}_{selected_street.cote_rue_id}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=selected_street.display_name,
                        data={
                            CONF_STREET_ID: selected_street.cote_rue_id,
                            CONF_STREET_NAME: selected_street.display_name,
                        },
                    )

            errors["base"] = "invalid_selection"

        # Build selection options
        options = {
            str(street.cote_rue_id): street.full_description
            for street in self._search_results
        }
        options["back"] = "← Back (modify search)"

        return self.async_show_form(
            step_id="select_street",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SELECTED_STREET): vol.In(options),
                }
            ),
            errors=errors,
            description_placeholders={
                "result_count": str(len(self._search_results))
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual street ID entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            street_id = user_input.get(CONF_STREET_ID)
            street_name = user_input.get(CONF_STREET_NAME, f"Street {street_id}")

            if not street_id:
                errors[CONF_STREET_ID] = "invalid_street_id"
            else:
                # Check if this street is already configured
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
                "geobase_url": "https://donnees.montreal.ca/dataset/geobase-double"
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
                # Update the config entry
                new_data = {**entry.data}
                new_data[CONF_STREET_NAME] = street_name

                self.hass.config_entries.async_update_entry(
                    entry,
                    data=new_data,
                    title=street_name,
                )
                return self.async_abort(reason="reconfigure_successful")
            else:
                errors[CONF_STREET_NAME] = "street_name_required"

        current_name = entry.data.get(CONF_STREET_NAME, "")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREET_NAME, default=current_name): str,
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
    """Handle options flow for Montreal Snow Removal - manages shared API token."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the shared API configuration."""
        errors: dict[str, str] = {}

        api_config = await get_api_config_store(self.hass)

        if user_input is not None:
            api_token = user_input.get(CONF_API_TOKEN, "").strip() or None
            use_simulation = user_input.get(CONF_USE_SIMULATION, False)

            # If token provided, validate it
            if api_token:
                client = PlanifNeigeClient(api_token, use_simulation=use_simulation)
                try:
                    await client.async_validate_token()
                except PlanifNeigeAuthError:
                    errors[CONF_API_TOKEN] = "invalid_auth"
                except PlanifNeigeConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                finally:
                    await client.close()

            if not errors:
                # Save to shared storage
                await api_config.async_save(
                    api_token=api_token,
                    use_simulation=use_simulation,
                )

                # Update all coordinators to use new config
                for entry_id, coordinator in self.hass.data.get(DOMAIN, {}).items():
                    if entry_id != "api_config_store" and hasattr(coordinator, "async_update_api_config"):
                        await coordinator.async_update_api_config()

                return self.async_create_entry(title="", data={})

        current_token = api_config.api_token or ""
        has_token = api_config.has_api_token

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_TOKEN,
                        default=current_token,
                    ): str,
                    vol.Optional(
                        CONF_USE_SIMULATION,
                        default=api_config.use_simulation,
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "has_token": "configured" if has_token else "not configured",
                "request_email": "donneesouvertes@montreal.ca",
            },
        )
