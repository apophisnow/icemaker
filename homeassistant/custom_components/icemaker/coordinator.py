"""Data update coordinator for Icemaker."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


@dataclass
class IcemakerData:
    """Data class for icemaker state."""

    state: str
    previous_state: str | None
    plate_temp: float
    bin_temp: float
    target_temp: float | None
    cycle_count: int
    time_in_state_seconds: float
    chill_mode: str | None
    relays: dict[str, bool]


class IcemakerApiClient:
    """API client for communicating with the icemaker."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = port
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def get_state(self) -> dict[str, Any]:
        """Get current icemaker state."""
        async with self._session.get(f"{self._base_url}/api/state/") as response:
            response.raise_for_status()
            return await response.json()

    async def get_relays(self) -> dict[str, bool]:
        """Get current relay states."""
        async with self._session.get(f"{self._base_url}/api/relays/") as response:
            response.raise_for_status()
            return await response.json()

    async def start_cycle(self) -> bool:
        """Start an ice-making cycle."""
        async with self._session.post(
            f"{self._base_url}/api/state/start"
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("success", False)

    async def emergency_stop(self) -> bool:
        """Trigger emergency stop."""
        async with self._session.post(
            f"{self._base_url}/api/state/emergency-stop"
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("success", False)

    async def set_relay(self, relay: str, state: bool) -> bool:
        """Set a relay state."""
        async with self._session.post(
            f"{self._base_url}/api/relays/{relay}",
            json={"state": state},
        ) as response:
            response.raise_for_status()
            return True

    async def test_connection(self) -> bool:
        """Test connection to the icemaker."""
        try:
            async with self._session.get(
                f"{self._base_url}/health", timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        except Exception:
            return False


class IcemakerCoordinator(DataUpdateCoordinator[IcemakerData]):
    """Coordinator for fetching icemaker data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: IcemakerApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Icemaker",
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> IcemakerData:
        """Fetch data from the icemaker."""
        try:
            async with asyncio.timeout(10):
                state_data, relay_data = await asyncio.gather(
                    self.client.get_state(),
                    self.client.get_relays(),
                )

                return IcemakerData(
                    state=state_data.get("state", "UNKNOWN"),
                    previous_state=state_data.get("previous_state"),
                    plate_temp=state_data.get("plate_temp", 0.0),
                    bin_temp=state_data.get("bin_temp", 0.0),
                    target_temp=state_data.get("target_temp"),
                    cycle_count=state_data.get("cycle_count", 0),
                    time_in_state_seconds=state_data.get("time_in_state_seconds", 0.0),
                    chill_mode=state_data.get("chill_mode"),
                    relays=relay_data,
                )
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with icemaker: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout communicating with icemaker") from err
