"""Sensor platform for Montreal Snow Removal."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_STREET_ID, CONF_STREET_NAME, DOMAIN
from .coordinator import SnowMontrealCoordinator

# Special state when no API token is configured
STATE_AWAITING_API_KEY = "awaiting_api_key"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: SnowMontrealCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        SnowRemovalStatusSensor(coordinator, entry),
        SnowRemovalPlannedStartSensor(coordinator, entry),
        SnowRemovalPlannedEndSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class SnowMontrealSensorBase(CoordinatorEntity[SnowMontrealCoordinator], SensorEntity):
    """Base class for Montreal Snow Removal sensors."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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


class SnowRemovalStatusSensor(SnowMontrealSensorBase):
    """Sensor for snow removal status."""

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="status",
                name="Snow Removal Status",
                icon="mdi:snowflake-alert",
                translation_key="snow_removal_status",
            ),
        )

    @property
    def native_value(self) -> str | None:
        """Return the current status."""
        # Show special state if no API token
        if not self.has_api_token:
            return STATE_AWAITING_API_KEY

        status = self.street_status
        if status is None:
            return None
        return status.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {
            "street_id": self._street_id,
            "api_configured": self.has_api_token,
        }

        if not self.has_api_token:
            attrs["setup_hint"] = "Configure API token in integration options"
            return attrs

        status = self.street_status
        if status is None:
            return attrs

        attrs.update({
            "status_code": status.status_code,
            "status_french": status.status_label_fr,
            "status_english": status.status_label_en,
            "is_active": status.is_active,
        })

        if status.municipality_id:
            attrs["municipality_id"] = status.municipality_id

        if status.last_updated:
            attrs["last_updated"] = status.last_updated.isoformat()

        if status.planned_start:
            attrs["planned_start"] = status.planned_start.isoformat()

        if status.planned_end:
            attrs["planned_end"] = status.planned_end.isoformat()

        if status.replanned_start:
            attrs["replanned_start"] = status.replanned_start.isoformat()

        if status.replanned_end:
            attrs["replanned_end"] = status.replanned_end.isoformat()

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon based on status."""
        if not self.has_api_token:
            return "mdi:key-alert"

        status = self.street_status
        if status is None:
            return "mdi:snowflake-alert"

        icons = {
            "unknown": "mdi:help-circle",
            "scheduled": "mdi:calendar-clock",
            "in_progress": "mdi:snowplow",
            "completed": "mdi:check-circle",
            "cancelled": "mdi:cancel",
            "pending": "mdi:clock-outline",
            "replanned": "mdi:calendar-refresh",
        }
        return icons.get(status.state, "mdi:snowflake-alert")


class SnowRemovalPlannedStartSensor(SnowMontrealSensorBase):
    """Sensor for planned snow removal start time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the planned start sensor."""
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="planned_start",
                name="Snow Removal Planned Start",
                icon="mdi:clock-start",
                translation_key="planned_start",
            ),
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the planned start time."""
        if not self.has_api_token:
            return None

        status = self.street_status
        if status is None:
            return None

        # Return replanned start if available, otherwise planned start
        return status.replanned_start or status.planned_start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.has_api_token:
            return {"api_configured": False}
        return {"api_configured": True}


class SnowRemovalPlannedEndSensor(SnowMontrealSensorBase):
    """Sensor for planned snow removal end time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: SnowMontrealCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the planned end sensor."""
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="planned_end",
                name="Snow Removal Planned End",
                icon="mdi:clock-end",
                translation_key="planned_end",
            ),
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the planned end time."""
        if not self.has_api_token:
            return None

        status = self.street_status
        if status is None:
            return None

        # Return replanned end if available, otherwise planned end
        return status.replanned_end or status.planned_end

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.has_api_token:
            return {"api_configured": False}
        return {"api_configured": True}
