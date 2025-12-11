"""Binary sensor platform for Montreal Snow Removal."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_STREET_ID, CONF_STREET_NAME, DOMAIN
from .coordinator import SnowMontrealCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: SnowMontrealCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [
        SnowRemovalActiveSensor(coordinator, entry),
        SnowRemovalParkingRestrictionSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class SnowMontrealBinarySensorBase(
    CoordinatorEntity[SnowMontrealCoordinator], BinarySensorEntity
):
    """Base class for Montreal Snow Removal binary sensors."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._street_id = entry.data[CONF_STREET_ID]
        self._street_name = entry.data.get(CONF_STREET_NAME, f"Street {self._street_id}")

        self._attr_unique_id = f"{DOMAIN}_{self._street_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._street_id))},
            "name": self._street_name,
            "manufacturer": "City of Montreal",
            "model": "Planif-Neige",
            "entry_type": "service",
        }

    @property
    def street_status(self):
        """Get the current street status."""
        return self.coordinator.get_street_status()

    @property
    def has_api_token(self) -> bool:
        """Return True if API token is configured."""
        return self.coordinator.has_api_token


class SnowRemovalActiveSensor(SnowMontrealBinarySensorBase):
    """Binary sensor indicating if snow removal is active or scheduled."""

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the active sensor."""
        super().__init__(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="active",
                name="Snow Removal Active",
                icon="mdi:snowplow",
                translation_key="snow_removal_active",
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if snow removal is active or scheduled."""
        if not self.has_api_token:
            return None

        status = self.street_status
        if status is None:
            return None
        return status.is_active

    @property
    def icon(self) -> str:
        """Return the icon based on state."""
        if not self.has_api_token:
            return "mdi:key-alert"
        if self.is_on:
            return "mdi:snowplow"
        return "mdi:check-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {"api_configured": self.has_api_token}

        if not self.has_api_token:
            attrs["setup_hint"] = "Configure API token in integration options"
            return attrs

        status = self.street_status
        if status is None:
            return attrs

        attrs.update({
            "status": status.state,
            "status_code": status.status_code,
        })
        return attrs


class SnowRemovalParkingRestrictionSensor(SnowMontrealBinarySensorBase):
    """Binary sensor indicating if parking is restricted due to snow removal."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the parking restriction sensor."""
        super().__init__(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="parking_restricted",
                name="Parking Restricted",
                icon="mdi:car-off",
                translation_key="parking_restricted",
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if parking is restricted (snow removal scheduled/in progress)."""
        if not self.has_api_token:
            return None

        status = self.street_status
        if status is None:
            return None

        # Parking is restricted when status is scheduled (1), in_progress (2), or replanned (6)
        return status.status_code in (1, 2, 6)

    @property
    def icon(self) -> str:
        """Return the icon based on state."""
        if not self.has_api_token:
            return "mdi:key-alert"
        if self.is_on:
            return "mdi:car-off"
        return "mdi:car"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {"api_configured": self.has_api_token}

        if not self.has_api_token:
            attrs["setup_hint"] = "Configure API token in integration options"
            return attrs

        status = self.street_status
        if status is None:
            return attrs

        attrs["status"] = status.state

        if status.planned_start:
            attrs["restriction_starts"] = status.planned_start.isoformat()

        if status.planned_end:
            attrs["restriction_ends"] = status.planned_end.isoformat()

        return attrs
