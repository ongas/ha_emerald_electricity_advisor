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
                        # Try today first, then scan back up to 7 days
                        for days_ago in range(8):
                            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                            device_data = await self.client.get_device_data(
                                device_id, start_date=date, end_date=date
                            ) or {}
                            if device_data.get("daily_consumptions"):
                                if days_ago > 0:
                                    _LOGGER.debug(
                                        "Using data from %s for %s (today + %d recent days empty)",
                                        date, device_id, days_ago,
                                    )
                                break
                        else:
                            _LOGGER.warning("No data found in last 7 days for %s", device_id)
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
