"""Emerald Electricity Advisor sensors."""
import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .api_client import EmeraldAPIError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Emerald sensors."""
    try:
        data = hass.data[DOMAIN][entry.entry_id]
        client = data["client"]

        entities = []

        try:
            properties = await client.get_properties()

            if not properties:
                _LOGGER.warning("No properties found for Emerald account")
                async_add_entities(entities)
                return

            for prop in properties:
                devices = prop.get("devices", [])
                if not devices:
                    continue

                for device in devices:
                    device_id = device.get("id")
                    if not device_id:
                        continue

                    device_name = device.get("device_name", f"Device {device_id}")
                    serial = device.get("serial_number", "")
                    model = device.get("model", "Electricity Advisor")
                    firmware = device.get("firmware_version", "")

                    device_info = {
                        "identifiers": {(DOMAIN, device_id)},
                        "name": device_name,
                        "manufacturer": "Emerald",
                        "model": model,
                        "sw_version": firmware,
                    }
                    if serial:
                        device_info["serial_number"] = serial

                    # Device status sensor
                    entities.append(
                        EmeraldStatusSensor(
                            device_id=device_id,
                            device_name=device_name,
                            device_info=device_info,
                            device_status=device.get("device_status", "unknown"),
                        )
                    )

                    # Fetch today's energy data
                    try:
                        device_data = await client.get_device_data(device_id)
                        daily = None
                        daily_consumptions = device_data.get("daily_consumptions", [])
                        if daily_consumptions:
                            daily = daily_consumptions[0]

                        # Daily energy (kWh)
                        entities.append(
                            EmeraldDailyEnergySensor(
                                device_id=device_id,
                                device_name=device_name,
                                device_info=device_info,
                                client=client,
                            )
                        )

                        # Daily cost ($)
                        entities.append(
                            EmeraldDailyCostSensor(
                                device_id=device_id,
                                device_name=device_name,
                                device_info=device_info,
                                client=client,
                            )
                        )

                        # Daily trend
                        if device_data.get("daily_trend") is not None:
                            entities.append(
                                EmeraldTrendSensor(
                                    device_id=device_id,
                                    device_name=device_name,
                                    device_info=device_info,
                                    client=client,
                                    trend_type="daily",
                                )
                            )

                        # Monthly trend
                        if device_data.get("monthly_trend") is not None:
                            entities.append(
                                EmeraldTrendSensor(
                                    device_id=device_id,
                                    device_name=device_name,
                                    device_info=device_info,
                                    client=client,
                                    trend_type="monthly",
                                )
                            )

                    except EmeraldAPIError as err:
                        _LOGGER.debug("Could not fetch device data for %s: %s", device_id, err)

        except EmeraldAPIError as err:
            _LOGGER.error("Error setting up sensors: %s", err)

        if entities:
            async_add_entities(entities)
        else:
            _LOGGER.warning("No sensors created for Emerald Electricity Advisor")

    except Exception as err:
        _LOGGER.exception("Unexpected error in sensor setup: %s", err)


class EmeraldSensorBase(SensorEntity):
    """Base class for Emerald sensors."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        device_info: dict,
        sensor_type: str,
    ):
        """Initialize sensor."""
        self._device_id = device_id
        self._device_name = device_name
        self._device_info_data = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"

    @property
    def device_info(self):
        """Return device info."""
        return self._device_info_data


class EmeraldStatusSensor(EmeraldSensorBase):
    """Emerald device status sensor."""

    def __init__(self, device_id: str, device_name: str, device_info: dict, device_status: str):
        """Initialize status sensor."""
        super().__init__(device_id, device_name, device_info, "status")
        self._attr_name = f"{device_name} Status"
        self._status = device_status

    @property
    def native_value(self) -> StateType:
        """Return device status."""
        return self._status

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:power-plug" if self._status == "Active" else "mdi:power-plug-off"


class EmeraldDailyEnergySensor(EmeraldSensorBase):
    """Emerald daily energy consumption sensor."""

    def __init__(self, device_id: str, device_name: str, device_info: dict, client):
        """Initialize daily energy sensor."""
        super().__init__(device_id, device_name, device_info, "daily_energy")
        self._attr_name = f"{device_name} Daily Energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:lightning-bolt"
        self._client = client
        self._attr_native_value = None

    async def async_update(self) -> None:
        """Fetch latest daily energy."""
        try:
            data = await self._client.get_device_data(self._device_id)
            daily_consumptions = data.get("daily_consumptions", [])
            if daily_consumptions:
                self._attr_native_value = daily_consumptions[0].get("total_kwh_of_day")
        except EmeraldAPIError as err:
            _LOGGER.debug("Error updating daily energy for %s: %s", self._device_id, err)


class EmeraldDailyCostSensor(EmeraldSensorBase):
    """Emerald daily cost sensor."""

    def __init__(self, device_id: str, device_name: str, device_info: dict, client):
        """Initialize daily cost sensor."""
        super().__init__(device_id, device_name, device_info, "daily_cost")
        self._attr_name = f"{device_name} Daily Cost"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:currency-usd"
        self._client = client
        self._attr_native_value = None

    async def async_update(self) -> None:
        """Fetch latest daily cost."""
        try:
            data = await self._client.get_device_data(self._device_id)
            daily_consumptions = data.get("daily_consumptions", [])
            if daily_consumptions:
                value = daily_consumptions[0].get("total_cost_of_day")
                if value is not None:
                    self._attr_native_value = round(value, 2)
        except EmeraldAPIError as err:
            _LOGGER.debug("Error updating daily cost for %s: %s", self._device_id, err)


class EmeraldTrendSensor(EmeraldSensorBase):
    """Emerald usage trend sensor."""

    def __init__(self, device_id: str, device_name: str, device_info: dict, client, trend_type: str):
        """Initialize trend sensor."""
        super().__init__(device_id, device_name, device_info, f"{trend_type}_trend")
        self._trend_type = trend_type
        label = trend_type.replace("_", " ").title()
        self._attr_name = f"{device_name} {label} Trend"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:trending-up"
        self._client = client
        self._attr_native_value = None

    async def async_update(self) -> None:
        """Fetch latest trend."""
        try:
            data = await self._client.get_device_data(self._device_id)
            self._attr_native_value = data.get(f"{self._trend_type}_trend")
        except EmeraldAPIError as err:
            _LOGGER.debug("Error updating %s trend for %s: %s", self._trend_type, self._device_id, err)
