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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EmeraldCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_latest_10min_block(daily_consumptions: list) -> dict | None:
    """Get the most recent non-zero 10-minute consumption block."""
    if not daily_consumptions:
        return None
    today = daily_consumptions[0]
    ten_min = today.get("ten_minute_consumptions", [])
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
    """Set up Emerald sensors from coordinator data."""
    coordinator: EmeraldCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []

    if not coordinator.data or not coordinator.data.get("devices"):
        _LOGGER.warning("No devices found in Emerald coordinator data")
        return

    for device_id, device_entry in coordinator.data["devices"].items():
        device = device_entry["device"]
        prop = device_entry["property"]

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
            "coordinator": coordinator,
            "device_id": device_id,
            "device_name": device_name,
            "device_info": device_info,
        }

        entities.extend([
            EmeraldLivePowerSensor(**common),
            EmeraldDailyEnergySensor(**common),
            EmeraldDailyCostSensor(**common),
            EmeraldDailyFlashesSensor(**common),
            EmeraldCurrentHourEnergySensor(**common),
            EmeraldCurrentHourCostSensor(**common),
            EmeraldAvgDailySpendSensor(**common),
            EmeraldTrendSensor(**common, trend_type="daily"),
            EmeraldTrendSensor(**common, trend_type="monthly"),
            EmeraldLastSyncedSensor(**common),
            EmeraldStatusSensor(**common, device=device),
        ])

        # Tariff sensors
        tariff_list = prop.get("tariff_structure", [])
        if tariff_list:
            tariff = tariff_list[0]
            supply = tariff.get("calculated_supply_charge") or tariff.get("supply_charge")
            unit = tariff.get("calculated_unit_charge") or tariff.get("unit_charge")
            if supply is not None:
                entities.append(EmeraldTariffSensor(
                    **common, tariff_type="supply_charge", value=supply,
                ))
            if unit is not None:
                entities.append(EmeraldTariffSensor(
                    **common, tariff_type="unit_charge", value=unit,
                ))

    async_add_entities(entities)


class EmeraldSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Emerald sensors — reads from coordinator data."""

    def __init__(self, coordinator: EmeraldCoordinator, device_id: str,
                 device_name: str, device_info: dict, sensor_type: str, **kwargs):
        """Initialize sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._device_info_data = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"

    @property
    def device_info(self):
        return self._device_info_data

    def _get_device_data(self) -> dict:
        """Get this device's data from coordinator."""
        if not self.coordinator.data:
            return {}
        entry = self.coordinator.data.get("devices", {}).get(self._device_id, {})
        return entry.get("data") or {}

    def _get_daily_consumptions(self) -> list:
        return self._get_device_data().get("daily_consumptions", [])


class EmeraldLivePowerSensor(EmeraldSensorBase):
    """Live power from latest 10-min block: kWh × 6 × 1000 = Watts."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="live_power", **kwargs)
        self._attr_name = f"{self._device_name} Live Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self) -> StateType:
        block = _get_latest_10min_block(self._get_daily_consumptions())
        if block and block.get("kwh") is not None:
            return round(block["kwh"] * 6 * 1000)
        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        block = _get_latest_10min_block(self._get_daily_consumptions())
        if not block:
            return None
        return {
            "time_block": block.get("time_string"),
            "kwh": block.get("kwh"),
            "cost": block.get("cost"),
            "flashes": block.get("number_of_flashes"),
        }


class EmeraldDailyEnergySensor(EmeraldSensorBase):
    """Today's total energy consumption."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="daily_energy", **kwargs)
        self._attr_name = f"{self._device_name} Daily Energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> StateType:
        daily = self._get_daily_consumptions()
        if daily:
            return daily[0].get("total_kwh_of_day")
        return None


class EmeraldDailyFlashesSensor(EmeraldSensorBase):
    """Today's total meter flash/pulse count."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="daily_flashes", **kwargs)
        self._attr_name = f"{self._device_name} Daily Flashes"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:pulse"
        self._attr_entity_category = "diagnostic"

    @property
    def native_value(self) -> StateType:
        daily = self._get_daily_consumptions()
        if daily:
            return daily[0].get("total_consumption_of_day")
        return None


class EmeraldDailyCostSensor(EmeraldSensorBase):
    """Today's total cost."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="daily_cost", **kwargs)
        self._attr_name = f"{self._device_name} Daily Cost"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:currency-usd"

    @property
    def native_value(self) -> StateType:
        daily = self._get_daily_consumptions()
        if daily:
            value = daily[0].get("total_cost_of_day")
            if value is not None:
                return round(value, 2)
        return None


class EmeraldCurrentHourEnergySensor(EmeraldSensorBase):
    """Current hour energy consumption."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="current_hour_energy", **kwargs)
        self._attr_name = f"{self._device_name} Current Hour Energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> StateType:
        block = _get_current_hour_block(self._get_daily_consumptions())
        if block:
            return block.get("kwh")
        return None


class EmeraldCurrentHourCostSensor(EmeraldSensorBase):
    """Current hour cost."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="current_hour_cost", **kwargs)
        self._attr_name = f"{self._device_name} Current Hour Cost"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:cash-clock"

    @property
    def native_value(self) -> StateType:
        block = _get_current_hour_block(self._get_daily_consumptions())
        if block and block.get("cost") is not None:
            return round(block["cost"], 2)
        return None


class EmeraldAvgDailySpendSensor(EmeraldSensorBase):
    """Average daily spend."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="avg_daily_spend", **kwargs)
        self._attr_name = f"{self._device_name} Avg Daily Spend"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "$"
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> StateType:
        value = self._get_device_data().get("average_daily_spend")
        if value is not None:
            return round(value, 2)
        return None


class EmeraldTrendSensor(EmeraldSensorBase):
    """Daily or monthly usage trend."""

    def __init__(self, trend_type: str, **kwargs):
        super().__init__(sensor_type=f"{trend_type}_trend", **kwargs)
        self._trend_type = trend_type
        label = trend_type.replace("_", " ").title()
        self._attr_name = f"{self._device_name} {label} Trend"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:trending-up"

    @property
    def native_value(self) -> StateType:
        return self._get_device_data().get(f"{self._trend_type}_trend")


class EmeraldLastSyncedSensor(EmeraldSensorBase):
    """Last time the device synced data to the cloud."""

    def __init__(self, **kwargs):
        super().__init__(sensor_type="last_synced", **kwargs)
        self._attr_name = f"{self._device_name} Last Synced"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:sync"

    @property
    def native_value(self):
        ts = self._get_device_data().get("synced_timestamp")
        if ts:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return None


class EmeraldStatusSensor(EmeraldSensorBase):
    """Device status with diagnostic attributes."""

    def __init__(self, device: dict, **kwargs):
        super().__init__(sensor_type="status", **kwargs)
        self._attr_name = f"{self._device_name} Status"
        self._attr_entity_category = "diagnostic"

    def _get_device_entry(self) -> dict:
        """Get this device's full entry from coordinator."""
        try:
            if not self.coordinator.data:
                return {}
            return self.coordinator.data.get("devices", {}).get(self._device_id, {}).get("device", {})
        except Exception:
            return {}

    @property
    def native_value(self) -> StateType:
        status = self._get_device_entry().get("device_status")
        return status if status else None

    @property
    def icon(self) -> str:
        status = self._get_device_entry().get("device_status")
        return "mdi:power-plug" if status == "Active" else "mdi:power-plug-off"

    @property
    def extra_state_attributes(self) -> dict | None:
        d = self._get_device_entry()
        if not d:
            return None
        attrs = {
            "serial_number": d.get("serial_number"),
            "mac_address": d.get("device_mac_address"),
            "nmi": d.get("NMI"),
            "impulse_rate": d.get("impulse_rate"),
            "impulse_rate_type": d.get("impulse_rate_type"),
            "installation_type": d.get("installation_type"),
            "device_category": d.get("device_category"),
        }
        return {k: v for k, v in attrs.items() if v is not None}


class EmeraldTariffSensor(EmeraldSensorBase):
    """Tariff rate (supply charge or unit charge)."""

    def __init__(self, tariff_type: str, value: float, **kwargs):
        super().__init__(sensor_type=f"tariff_{tariff_type}", **kwargs)
        label = tariff_type.replace("_", " ").title()
        self._attr_name = f"{self._device_name} {label}"
        unit = "$/day" if "supply" in tariff_type else "$/kWh"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:cash-multiple"
        self._attr_native_value = round(value, 4)
