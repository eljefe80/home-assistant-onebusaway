"""Sensor platform for onebusaway."""
from __future__ import annotations
from datetime import datetime, timezone
from time import time

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.const import CONF_ID
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import ATTRIBUTION, DOMAIN, NAME, VERSION

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="onebusaway",
        name="OneBusAway Sensor",
        icon="mdi:bus-clock",
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        OneBusAwaySensor(
            coordinator=coordinator,
            entity_description=entity_description,
            stop=entry.data[CONF_ID],
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class OneBusAwaySensor(CoordinatorEntity, SensorEntity):
    """onebusaway Sensor class."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        stop: str,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_attribution = ATTRIBUTION
        self._attr_unique_id = stop
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop)},
            name=NAME,
            model=VERSION,
            manufacturer=NAME,
        )

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    unsub = None
    next_arrival = None

    def compute_next(self) -> datetime | None:
        """Compute the next arrival time from the coordinator data."""
        data = self.coordinator.data
        if data is None:
            return None
        # Timestamps are in milliseconds
        current = time() * 1000
        departures = [
            d["predictedDepartureTime"]
            for d in data.get("data")["entry"]["arrivalsAndDepartures"]
            if d["predictedDepartureTime"] > current
        ]
        if not departures:
            return None
        departure = min(departures) / 1000
        return datetime.fromtimestamp(departure, timezone.utc)

    def refresh(self, _timestamp) -> None:
        """Request a coordinator refresh when the arrival time is reached."""
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @property
    def native_value(self) -> datetime | None:
        """Return the native value of the sensor."""
        return self.next_arrival

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        soonest = self.compute_next()
        if soonest is None:
            self.async_write_ha_state()
            return

        if soonest != self.next_arrival:
            self.next_arrival = soonest
            if self.unsub is not None:
                self.unsub()
                self.unsub = None
            self.unsub = async_track_point_in_time(
                self.hass, self.refresh, self.next_arrival
            )

        self.async_write_ha_state()
