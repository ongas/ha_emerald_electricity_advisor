"""Emerald Electricity Advisor sensors."""
import logging
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .api_client import EmeraldAPIError

_LOGGER = logging.getLogger(__name__)


def _get_latest_10min_block(daily_consumptions: list) -> dict | None:
    """Get the most recent non-zero 10-minute consumption block."""
    if not daily_consumptions:
        return None
    today = daily_consumptions[0]
    ten_min = today.get("ten_minute_consumptions", [])
    # Walk backwards to find the latest block with data
    for block in reversed(ten_min):
        if block.get("number_of_flashes", 0) > 0:
            return block
    return None


def _get_current_hour_block(daily_consumptions: list) -> dict | None:
    """Get the current hour's consumption block."""
    if not daily_consumptions:
        return None
    today = daily_consumptions[0]
    now_hour = datetime.now().strftime("%H:00")
    for block in today.get("hourly_consumptions", []):
        if block.get("hour_string") == now_hour:
            return block
    return None


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
                # Extract tariff info
                tariff = {}
                tariff_list = prop.get("tariff_structure", [])
                if tariff_list:
                    tariff = tariff_list[0]

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

                    common = {
                        "device_id": device_id,
                        "device_name": device_name,
                        "device_info": device_info,
                        "client": client,
                    }

                    # Device status
                    entities.append(EmeraldStatusSensor(
                        **common, device_status=device.get("device_status", "unknown"),
                    ))

                    # Live power (W) — from latest 10-min block
                    entities.append(EmeraldLivePowerSensor(**common))

                    # Daily energy (kWh)
                    entities.append(EmeraldDailyEnergySensor(**common))

                    # Daily cost ($)
                    entities.append(EmeraldDailyCostSensor(**common))

                    # Current hour energy (kWh)
                    entities.append(EmeraldCurrentHourEnergySensor(**common))

                    # Current hour cost ($)
                    entities.append(EmeraldCurrentHourCostSensor(**common))

                    # Average daily spend ($)
                    entities.append(EmeraldAvgDailySpendSensor(**common))

                    # Daily trend (%)
                    entities.append(EmeraldTrendSensor(**common, trend_type="daily"))

                    # Monthly trend (%)
                    entities.append(EmeraldTrendSensor(**common, trend_type="monthly"))

                    # Last synced timestamp
                    entities.append(EmeraldLastSyncedSensor(**common))

                    # Tariff sensors (if available)
                    supply_charge = tariff.get("calculated_supply_charge") or tariff.get("supply_charge")
                    unit_charge = tariff.get("calculated_unit_charge") or tariff.get("unit_charge")
                    if supply_charge is not None:
                        entities.append(EmeraldTariffSensor(
                            **common, tariff_type="supply_charge", value=supply_charge,
                        ))
                    if unit_charge is not None:
                        entities.append(EmeraldTariffSensor(
                            **common, tariff_type="unit_charge", value=unit_charge,
                        ))

        except EmeraldAPIError as err:
            _LOGGER.error("Error setting up sensors: %s", err)

        if entities:
            async_add_entities(entities, update_before_add=True)
        else:
            _LOGGER.warning("No sensors created for Emerald Electricity Advisor")

    except Exception as err:
        _LOGGER.exception("Unexpected error in sensor setup: %s", err)


class EmeraldSensorBase(SensorEntity):
    """Base class for Emerald sensors."""

    def __init__(self, device_id: str, device_name: str, device_info: dict,
                 client, sensor_type: str, **kwargs):
        """Initialize sensor."""
        self._device_id = device_id
        self._device_name = device_name
        self._device_info_data = device_info
        self._client = client
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"

    @property
    def device_info(self):
        """Return device info."""
        return self._device_info_data

    async def _fetch_device_data(self) -> dict | None:
        """Fetch device data, return None on error."""
        try:
            return await self._client.get_device_data(self._device_id)
        except EmeraldAPIError as err:
            _LOGGER.debug("Error fetching data for %s: %s", self._device_id, err)
            return None


class EmeraldStatusSensor(EmeraldSensorBase):
    """Emerald device status sensor."""

    def __init__(self, device_status: str, **kwargs):
        """Initialize status sensor."""
        super().__init__(sensor_type="status", **kwargs)
        self._attr_name = f"{self._device_name} Status"
        self._status = device_status

    @property
    def native_value(self) -> StateType:
        return self._status

    @property
    def icon(self) -> str:
        return "mdi:power-plug" if self._status == "Active" else "mdi:power-plug-off"


class EmeraldLivePowerSensor(EmeraldSensorBase):
    """Live power usage calculated from latest 10-min block."""

    def __init__(self, **kwargs):
        """Initialize live power sensor."""
        super().__init__(sensor_type="live_power", **kwargs)
        self._attr_name = f"{self._device_name} Live Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        block = _get_latest_10min_block(data.get("daily_consumptions", []))
        if block and block.get("kwh") is not None:
            # 10-min block kWh → Watts: kwh × 6 (blocks/hour) × 1000 (kW→W)
            self._attr_native_value = round(block["kwh"] * 6 * 1000)


class EmeraldDailyEnergySensor(EmeraldSensorBase):
    """Emerald daily energy consumption sensor."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="daily_energy", **kwargs)
        self._attr_name = f"{self._device_name} Daily Energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        daily = data.get("daily_consumptions", [])
        if daily:
            self._attr_native_value = daily[0].get("total_kwh_of_day")


class EmeraldDailyCostSensor(EmeraldSensorBase):
    """Emerald daily cost sensor."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="daily_cost", **kwargs)
        self._attr_name = f"{self._device_name} Daily Cost"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:currency-usd"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        daily = data.get("daily_consumptions", [])
        if daily:
            value = daily[0].get("total_cost_of_day")
            if value is not None:
                self._attr_native_value = round(value, 2)


class EmeraldCurrentHourEnergySensor(EmeraldSensorBase):
    """Current hour energy consumption."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="current_hour_energy", **kwargs)
        self._attr_name = f"{self._device_name} Current Hour Energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:clock-outline"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        block = _get_current_hour_block(data.get("daily_consumptions", []))
        if block:
            self._attr_native_value = block.get("kwh")


class EmeraldCurrentHourCostSensor(EmeraldSensorBase):
    """Current hour cost."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="current_hour_cost", **kwargs)
        self._attr_name = f"{self._device_name} Current Hour Cost"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:cash-clock"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        block = _get_current_hour_block(data.get("daily_consumptions", []))
        if block and block.get("cost") is not None:
            self._attr_native_value = round(block["cost"], 2)


class EmeraldAvgDailySpendSensor(EmeraldSensorBase):
    """Average daily spend."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="avg_daily_spend", **kwargs)
        self._attr_name = f"{self._device_name} Avg Daily Spend"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:chart-line"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        value = data.get("average_daily_spend")
        if value is not None:
            self._attr_native_value = round(value, 2)


class EmeraldTrendSensor(EmeraldSensorBase):
    """Emerald usage trend sensor."""

    def __init__(self, trend_type: str, **kwargs):
        super().__init__(sensor_type=f"{trend_type}_trend", **kwargs)
        self._trend_type = trend_type
        label = trend_type.replace("_", " ").title()
        self._attr_name = f"{self._device_name} {label} Trend"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:trending-up"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        self._attr_native_value = data.get(f"{self._trend_type}_trend")


class EmeraldLastSyncedSensor(EmeraldSensorBase):
    """Last time the device synced data."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="last_synced", **kwargs)
        self._attr_name = f"{self._device_name} Last Synced"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:sync"
        self._attr_native_value = None

    async def async_update(self) -> None:
        data = await self._fetch_device_data()
        if not data:
            return
        ts = data.get("synced_timestamp")
        if ts:
            self._attr_native_value = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


class EmeraldTariffSensor(EmeraldSensorBase):
    """Tariff rate sensor (supply charge or unit charge)."""

    def __init__(self, tariff_type: str, value: float, **kwargs):
        super().__init__(sensor_type=f"tariff_{tariff_type}", **kwargs)
        label = tariff_type.replace("_", " ").title()
        self._attr_name = f"{self._device_name} {label}"
        unit = "$/day" if "supply" in tariff_type else "$/kWh"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:cash-multiple"
        self._attr_native_value = round(value, 4)
