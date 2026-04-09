"""DataUpdateCoordinator for Emerald Electricity Advisor."""
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import EmeraldClient, EmeraldAPIError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Poll every 60 seconds — LiveLink keeps cloud data near-real-time
UPDATE_INTERVAL = timedelta(seconds=60)


class EmeraldCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator that fetches all Emerald data for all devices."""

    def __init__(self, hass: HomeAssistant, client: EmeraldClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.properties: list[dict] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Emerald API."""
        try:
            # Fetch properties (includes device info + tariff)
            self.properties = await self.client.get_properties()

            result: dict[str, Any] = {"devices": {}}

            for prop in self.properties:
                for device in prop.get("devices", []):
                    device_id = device.get("id")
                    if not device_id:
                        continue

                    device_data = {}
                    try:
                        # Try today first
                        device_data = await self.client.get_device_data(device_id) or {}

                        # If today has no data yet, fall back to yesterday
                        if not device_data or not device_data.get("daily_consumptions"):
                            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                            _LOGGER.debug(
                                "No data for today for %s, trying yesterday (%s)",
                                device_id, yesterday,
                            )
                            fallback = await self.client.get_device_data(
                                device_id, start_date=yesterday, end_date=yesterday
                            ) or {}
                            if fallback.get("daily_consumptions"):
                                device_data = fallback
                    except EmeraldAPIError as err:
                        _LOGGER.warning("Could not fetch data for %s: %s", device_id, err)

                    result["devices"][device_id] = {
                        "device": device,
                        "property": prop,
                        "data": device_data,
                    }

            return result

        except EmeraldAPIError as err:
            raise UpdateFailed(f"Error communicating with Emerald API: {err}") from err
