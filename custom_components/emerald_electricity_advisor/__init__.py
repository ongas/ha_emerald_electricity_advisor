"""Emerald Electricity Advisor integration for Home Assistant."""
import asyncio
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api_client import EmeraldClient
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Emerald Electricity Advisor from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    email = entry.data["email"]
    password = entry.data["password"]

    client = EmeraldClient(email=email, password=password)

    try:
        await asyncio.wait_for(client.authenticate(), timeout=10.0)
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout connecting to Emerald API")
        raise ConfigEntryNotReady from None
    except Exception as err:
        _LOGGER.error("Error authenticating with Emerald API: %s", err)
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {"client": client, "devices": entry.data.get("devices", [])}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
