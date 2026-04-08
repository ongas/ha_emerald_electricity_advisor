"""Emerald Electricity Advisor integration for Home Assistant."""
import asyncio
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api_client import EmeraldClient, EmeraldAPIError
from .const import DOMAIN
from .coordinator import EmeraldCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Emerald Electricity Advisor from a config entry."""
    _LOGGER.debug("Setting up Emerald Electricity Advisor integration")
    
    hass.data.setdefault(DOMAIN, {})

    email = entry.data["email"]
    password = entry.data["password"]

    client = EmeraldClient(email=email, password=password)

    try:
        _LOGGER.debug("Authenticating with Emerald API")
        await asyncio.wait_for(client.authenticate(), timeout=10.0)
        _LOGGER.debug("Successfully authenticated with Emerald API")
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout connecting to Emerald API")
        raise ConfigEntryNotReady("Could not connect to Emerald API") from None
    except EmeraldAPIError as err:
        _LOGGER.error("Error authenticating with Emerald API: %s", err)
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except Exception as err:
        _LOGGER.error("Unexpected error authenticating with Emerald API: %s", err)
        raise ConfigEntryNotReady(f"Unexpected error: {err}") from err

    coordinator = EmeraldCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    _LOGGER.debug("Setting up platforms for Emerald Electricity Advisor")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Emerald Electricity Advisor integration")
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Successfully unloaded Emerald Electricity Advisor integration")

    return unload_ok
