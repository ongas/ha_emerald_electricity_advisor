"""Emerald Electricity Advisor API client."""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .const import (
    EMERALD_SIGN_IN,
    EMERALD_TOKEN_REFRESH,
    EMERALD_PROPERTY_LIST,
    EMERALD_DEVICE_DATA,
)


class EmeraldAPIError(Exception):
    """Base exception for Emerald API errors."""


class EmeraldAuthError(EmeraldAPIError):
    """Authentication failed."""


class EmeraldClient:
    """Emerald Electricity Advisor API client."""

    def __init__(self, email: str, password: str):
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def authenticate(self) -> bool:
        """Authenticate and get bearer token."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        try:
            payload = {
                "app_version": "1.2.1",
                "device_name": "Home Assistant",
                "device_os_version": "1.0",
                "device_token": "",
                "device_type": "ha",
                "email": self.email,
                "passcode": None,
                "password": self.password,
            }

            async with self._session.post(EMERALD_SIGN_IN, json=payload) as resp:
                if resp.status != 200:
                    raise EmeraldAuthError(f"Auth failed: {resp.status}")

                data = await resp.json()
                if data.get("code") != 200:
                    raise EmeraldAuthError(f"Auth failed: {data.get('message', 'Unknown error')}")

                self.token = data["info"]["token"]
                # Token lasts ~24 hours, refresh after 23 hours
                self.token_expires = datetime.now() + timedelta(hours=23)
                return True

        except aiohttp.ClientError as e:
            raise EmeraldAPIError(f"Connection error: {e}")

    async def refresh_token(self) -> bool:
        """Refresh the bearer token."""
        if not self.token:
            return await self.authenticate()

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {
                "app_version": "1.2.1",
                "device_name": "Home Assistant",
                "device_os_version": "1.0",
                "device_type": "ha",
                "background_sync_count": 0,
            }

            async with self._session.post(
                EMERALD_TOKEN_REFRESH, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    return await self.authenticate()

                data = await resp.json()
                if data.get("code") != 200:
                    return await self.authenticate()

                self.token = data["info"]["token"]
                self.token_expires = datetime.now() + timedelta(hours=23)
                return True

        except Exception:
            return await self.authenticate()

    async def _ensure_authenticated(self) -> None:
        """Ensure token is valid, refresh if needed."""
        if not self.token or (self.token_expires and datetime.now() > self.token_expires):
            await self.refresh_token()

    async def get_properties(self) -> list:
        """Get list of properties and their devices."""
        await self._ensure_authenticated()

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self._session.get(EMERALD_PROPERTY_LIST, headers=headers) as resp:
                if resp.status != 200:
                    raise EmeraldAPIError(f"Failed to get properties: {resp.status}")

                data = await resp.json()
                if data.get("code") != 200:
                    raise EmeraldAPIError(f"API error: {data.get('message')}")

                return data.get("info", {}).get("property", [])

        except aiohttp.ClientError as e:
            raise EmeraldAPIError(f"Connection error: {e}")

    async def get_device_data(
        self, device_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get device energy data for date range."""
        await self._ensure_authenticated()

        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = start_date

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {
                "device_id": device_id,
                "start_date": start_date,
                "end_date": end_date,
            }

            async with self._session.get(
                EMERALD_DEVICE_DATA, params=params, headers=headers
            ) as resp:
                if resp.status != 200:
                    raise EmeraldAPIError(f"Failed to get device data: {resp.status}")

                data = await resp.json()
                if data.get("code") != 200:
                    raise EmeraldAPIError(f"API error: {data.get('message')}")

                return data.get("info", {})

        except aiohttp.ClientError as e:
            raise EmeraldAPIError(f"Connection error: {e}")

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()
