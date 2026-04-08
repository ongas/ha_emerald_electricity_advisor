"""Emerald Electricity Advisor sensors."""
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
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
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    devices = data["devices"]

    entities = []

    try:
        # Fetch properties to get device information
        properties = await client.get_properties()

        for prop in properties:
            for device in prop.get("device", []):
                device_id = device.get("id")
                device_name = device.get("name", f"Device {device_id}")
                device_info = {
                    "identifiers": {(DOMAIN, device_id)},
                    "name": device_name,
                    "manufacturer": "Emerald Energy",
                }

                # Fetch device data
                try:
                    device_data = await client.get_device_data(device_id)

                    # Create sensors for each data point
                    # Status sensors
                    entities.append(
                        EmeraldStatusSensor(
                            device_id=device_id,
                            device_name=device_name,
                            device_info=device_info,
                            device_data=device_data,
                        )
                    )

                    # Portal URL sensor
                    entities.append(
                        EmeraldPortalSensor(
                            device_id=device_id,
                            device_name=device_name,
                            device_info=device_info,
                        )
                    )

                    # Energy consumption sensors
                    for data_type in ["consumption", "generation", "grid_import", "grid_export"]:
                        if data_type in device_data:
                            entities.append(
                                EmeraldEnergySensor(
                                    device_id=device_id,
                                    device_name=device_name,
                                    device_info=device_info,
                                    data_type=data_type,
                                    device_data=device_data,
                                )
                            )

                    # Power sensors
                    for data_type in ["power_consumption", "power_generation"]:
                        if data_type in device_data:
                            entities.append(
                                EmeraldPowerSensor(
                                    device_id=device_id,
                                    device_name=device_name,
                                    device_info=device_info,
                                    data_type=data_type,
                                    device_data=device_data,
                                )
                            )

                    # Temperature sensors
                    for data_type in ["temperature", "ambient_temperature"]:
                        if data_type in device_data:
                            entities.append(
                                EmeraldTemperatureSensor(
                                    device_id=device_id,
                                    device_name=device_name,
                                    device_info=device_info,
                                    data_type=data_type,
                                    device_data=device_data,
                                )
                            )

                except EmeraldAPIError as err:
                    _LOGGER.error("Error fetching device data for %s: %s", device_id, err)

        if entities:
            async_add_entities(entities)

    except EmeraldAPIError as err:
        _LOGGER.error("Error setting up sensors: %s", err)


class EmeraldSensorBase(SensorEntity):
    """Base class for Emerald sensors."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        device_info: dict,
        sensor_type: str,
        data_type: str | None = None,
    ):
        """Initialize sensor."""
        self.device_id = device_id
        self.device_name = device_name
        self._device_info = device_info
        self.sensor_type = sensor_type
        self.data_type = data_type

        # Unique identifier and entity properties
        if data_type:
            self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}_{data_type}"
            name_suffix = data_type.replace("_", " ").title()
            self._attr_name = f"{device_name} {name_suffix}"
        else:
            self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"
            self._attr_name = f"{device_name} {sensor_type.replace('_', ' ').title()}"

    @property
    def device_info(self):
        """Return device info."""
        return self._device_info


class EmeraldStatusSensor(EmeraldSensorBase):
    """Emerald device status sensor."""

    def __init__(self, device_id: str, device_name: str, device_info: dict, device_data: dict):
        """Initialize status sensor."""
        super().__init__(device_id, device_name, device_info, "status")
        self._device_data = device_data
        self._attr_native_value = device_data.get("status", "unknown")

    @property
    def native_value(self) -> StateType:
        """Return status."""
        return self._device_data.get("status", "unknown")


class EmeraldPortalSensor(EmeraldSensorBase):
    """Emerald portal link sensor."""

    def __init__(self, device_id: str, device_name: str, device_info: dict):
        """Initialize portal sensor."""
        super().__init__(device_id, device_name, device_info, "portal_url")
        self._attr_native_value = f"https://www.emeraldenergy.com.au/device/{device_id}"

    @property
    def native_value(self) -> StateType:
        """Return portal URL."""
        return f"https://www.emeraldenergy.com.au/device/{self.device_id}"


class EmeraldEnergySensor(EmeraldSensorBase):
    """Emerald energy consumption/generation sensor."""

    def __init__(
        self, device_id: str, device_name: str, device_info: dict, data_type: str, device_data: dict
    ):
        """Initialize energy sensor."""
        super().__init__(device_id, device_name, device_info, "energy", data_type)
        self._device_data = device_data
        self._data_type = data_type

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> StateType:
        """Return energy value."""
        value = self._device_data.get(self._data_type)
        return float(value) if value is not None else None


class EmeraldPowerSensor(EmeraldSensorBase):
    """Emerald power consumption/generation sensor."""

    def __init__(
        self, device_id: str, device_name: str, device_info: dict, data_type: str, device_data: dict
    ):
        """Initialize power sensor."""
        super().__init__(device_id, device_name, device_info, "power", data_type)
        self._device_data = device_data
        self._data_type = data_type

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self) -> StateType:
        """Return power value."""
        value = self._device_data.get(self._data_type)
        return float(value) if value is not None else None


class EmeraldTemperatureSensor(EmeraldSensorBase):
    """Emerald temperature sensor."""

    def __init__(
        self, device_id: str, device_name: str, device_info: dict, data_type: str, device_data: dict
    ):
        """Initialize temperature sensor."""
        super().__init__(device_id, device_name, device_info, "temperature", data_type)
        self._device_data = device_data
        self._data_type = data_type

        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> StateType:
        """Return temperature value."""
        value = self._device_data.get(self._data_type)
        return float(value) if value is not None else None
