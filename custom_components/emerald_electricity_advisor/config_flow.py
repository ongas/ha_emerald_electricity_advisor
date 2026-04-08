"""Config flow for Emerald Electricity Advisor integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .api_client import EmeraldClient, EmeraldAuthError, EmeraldAPIError


class EmeraldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emerald Electricity Advisor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test credentials
                client = EmeraldClient(user_input["email"], user_input["password"])
                await client.authenticate()

                # Get properties to verify API access
                properties = await client.get_properties()
                await client.close()

                if not properties:
                    errors["base"] = "no_devices"
                else:
                    # Check if we already have this email configured
                    await self.async_set_unique_id(user_input["email"])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input["email"],
                        data=user_input,
                    )

            except EmeraldAuthError:
                errors["base"] = "invalid_auth"
            except EmeraldAPIError as e:
                errors["base"] = "api_error"
            except Exception as e:
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={},
        )


config_flow = EmeraldConfigFlow
