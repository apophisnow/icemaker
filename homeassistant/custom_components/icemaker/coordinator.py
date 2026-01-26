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
class IcemakerConfig:
    """Data class for icemaker configuration."""

    prechill_temp: float
    prechill_timeout: int
    ice_target_temp: float
    ice_timeout: int
    harvest_threshold: float
    harvest_timeout: int
    harvest_fill_time: int
    rechill_temp: float
    rechill_timeout: int
    bin_full_threshold: float
    standby_timeout: float
    poll_interval: float
    use_simulator: bool
    priming_enabled: bool
    priming_flush_time: int
    priming_pump_time: int
    priming_fill_time: int


@dataclass
class IcemakerData:
    """Data class for icemaker state."""

    state: str
    previous_state: str | None
    plate_temp: float
    bin_temp: float
    target_temp: float | None
    cycle_count: int
    session_cycle_count: int
    time_in_state_seconds: float
    chill_mode: str | None
    relays: dict[str, bool]
    bin_full: bool = False
    config: IcemakerConfig | None = None


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
            data = await response.json()
            # API returns {"relays": {...}}
            return data.get("relays", {})

    async def get_config(self) -> dict[str, Any]:
        """Get current configuration."""
        async with self._session.get(f"{self._base_url}/api/config/") as response:
            response.raise_for_status()
            return await response.json()

    async def update_config(self, **kwargs: Any) -> dict[str, Any]:
        """Update configuration parameters."""
        async with self._session.put(
            f"{self._base_url}/api/config/",
            json=kwargs,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def start_icemaking(self) -> bool:
        """Start an ice-making cycle."""
        async with self._session.post(
            f"{self._base_url}/api/state/cycle",
            json={"action": "start"},
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("success", False)

    async def stop_icemaking(self) -> bool:
        """Stop the current ice-making cycle."""
        async with self._session.post(
            f"{self._base_url}/api/state/cycle",
            json={"action": "stop"},
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("success", False)

    async def emergency_stop(self) -> bool:
        """Trigger emergency stop."""
        async with self._session.post(
            f"{self._base_url}/api/state/cycle",
            json={"action": "emergency_stop"},
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("success", False)

    async def set_relay(self, relay: str, on: bool) -> bool:
        """Set a relay state."""
        async with self._session.post(
            f"{self._base_url}/api/relays/",
            json={"relay": relay, "on": on},
        ) as response:
            response.raise_for_status()
            return True

    async def all_relays_off(self) -> bool:
        """Turn off all relays."""
        async with self._session.post(
            f"{self._base_url}/api/relays/all-off",
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
                state_data, relay_data, config_data = await asyncio.gather(
                    self.client.get_state(),
                    self.client.get_relays(),
                    self.client.get_config(),
                )

                config = IcemakerConfig(
                    prechill_temp=config_data.get("prechill_temp", 32.0),
                    prechill_timeout=config_data.get("prechill_timeout", 120),
                    ice_target_temp=config_data.get("ice_target_temp", -2.0),
                    ice_timeout=config_data.get("ice_timeout", 1500),
                    harvest_threshold=config_data.get("harvest_threshold", 38.0),
                    harvest_timeout=config_data.get("harvest_timeout", 240),
                    harvest_fill_time=config_data.get("harvest_fill_time", 18),
                    rechill_temp=config_data.get("rechill_temp", 35.0),
                    rechill_timeout=config_data.get("rechill_timeout", 300),
                    bin_full_threshold=config_data.get("bin_full_threshold", 35.0),
                    standby_timeout=config_data.get("standby_timeout", 1200.0),
                    poll_interval=config_data.get("poll_interval", 5.0),
                    use_simulator=config_data.get("use_simulator", False),
                    priming_enabled=config_data.get("priming_enabled", False),
                    priming_flush_time=config_data.get("priming_flush_time", 60),
                    priming_pump_time=config_data.get("priming_pump_time", 15),
                    priming_fill_time=config_data.get("priming_fill_time", 15),
                )

                return IcemakerData(
                    state=state_data.get("state", "UNKNOWN"),
                    previous_state=state_data.get("previous_state"),
                    plate_temp=state_data.get("plate_temp", 0.0),
                    bin_temp=state_data.get("bin_temp", 0.0),
                    target_temp=state_data.get("target_temp"),
                    cycle_count=state_data.get("cycle_count", 0),
                    session_cycle_count=state_data.get("session_cycle_count", 0),
                    time_in_state_seconds=state_data.get("time_in_state_seconds", 0.0),
                    chill_mode=state_data.get("chill_mode"),
                    relays=relay_data,
                    bin_full=state_data.get("bin_full", False),
                    config=config,
                )
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with icemaker: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout communicating with icemaker") from err
