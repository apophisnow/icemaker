"""Integration tests for the API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from icemaker.api.app import app, app_state
from icemaker.config import IcemakerConfig, StateConfig
from icemaker.core.controller import IcemakerController
from icemaker.core.states import IcemakerState
from icemaker.simulator.simulated_hal import create_simulated_hal


@pytest.fixture
async def test_client():
    """Create test client with initialized controller."""
    # Create fast config
    config = IcemakerConfig()
    config.prechill = StateConfig(target_temp=50.0, timeout_seconds=5)
    config.poll_interval = 0.1
    config.use_simulator = True

    # Create HAL
    gpio, sensors, model = create_simulated_hal()

    # Create and initialize controller
    controller = IcemakerController(
        config=config,
        gpio=gpio,
        sensors=sensors,
        thermal_model=model,
    )
    await controller.initialize()

    # Set up app state
    app_state.controller = controller

    # Create client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup
    await controller.stop()


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, test_client: AsyncClient) -> None:
        """Health endpoint should return healthy status."""
        response = await test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["controller_running"] is True


class TestStateEndpoints:
    """Test state-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_state(self, test_client: AsyncClient) -> None:
        """Should return current state."""
        response = await test_client.get("/api/state/")
        assert response.status_code == 200

        data = response.json()
        assert data["state"] == "IDLE"
        assert "plate_temp" in data
        assert "bin_temp" in data
        assert "cycle_count" in data

    @pytest.mark.asyncio
    async def test_start_cycle(self, test_client: AsyncClient) -> None:
        """Should be able to start cycle."""
        response = await test_client.post(
            "/api/state/cycle",
            json={"action": "start"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        # Verify state changed
        state_response = await test_client.get("/api/state/")
        assert state_response.json()["state"] == "CHILL"

    @pytest.mark.asyncio
    async def test_emergency_stop(self, test_client: AsyncClient) -> None:
        """Should be able to emergency stop."""
        # Start a cycle first
        await test_client.post("/api/state/cycle", json={"action": "start"})

        response = await test_client.post(
            "/api/state/cycle",
            json={"action": "emergency_stop"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True


class TestRelayEndpoints:
    """Test relay control endpoints."""

    @pytest.mark.asyncio
    async def test_get_relays(self, test_client: AsyncClient) -> None:
        """Should return all relay states."""
        response = await test_client.get("/api/relays/")
        assert response.status_code == 200

        data = response.json()
        assert "relays" in data
        assert "compressor_1" in data["relays"]
        assert "water_valve" in data["relays"]

    @pytest.mark.asyncio
    async def test_set_relay(self, test_client: AsyncClient) -> None:
        """Should be able to set relay state."""
        response = await test_client.post(
            "/api/relays/",
            json={"relay": "compressor_1", "on": True},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["state"] is True

    @pytest.mark.asyncio
    async def test_set_invalid_relay(self, test_client: AsyncClient) -> None:
        """Should return error for invalid relay."""
        response = await test_client.post(
            "/api/relays/",
            json={"relay": "invalid_relay", "on": True},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_all_relays_off(self, test_client: AsyncClient) -> None:
        """Should turn off all relays."""
        # Turn on some relays
        await test_client.post(
            "/api/relays/",
            json={"relay": "compressor_1", "on": True},
        )

        response = await test_client.post("/api/relays/all-off")
        assert response.status_code == 200

        # Verify all off
        relay_response = await test_client.get("/api/relays/")
        relays = relay_response.json()["relays"]
        for state in relays.values():
            assert state is False


class TestSensorEndpoints:
    """Test sensor reading endpoints."""

    @pytest.mark.asyncio
    async def test_get_temperatures(self, test_client: AsyncClient) -> None:
        """Should return temperature readings."""
        response = await test_client.get("/api/sensors/")
        assert response.status_code == 200

        data = response.json()
        assert "plate_temp_f" in data
        assert "bin_temp_f" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_get_plate_temperature(self, test_client: AsyncClient) -> None:
        """Should return plate temperature."""
        response = await test_client.get("/api/sensors/plate")
        assert response.status_code == 200

        data = response.json()
        assert data["sensor"] == "plate"
        assert "temperature_f" in data

    @pytest.mark.asyncio
    async def test_get_bin_temperature(self, test_client: AsyncClient) -> None:
        """Should return bin temperature."""
        response = await test_client.get("/api/sensors/bin")
        assert response.status_code == 200

        data = response.json()
        assert data["sensor"] == "ice_bin"
        assert "temperature_f" in data


class TestConfigEndpoints:
    """Test configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_config(self, test_client: AsyncClient) -> None:
        """Should return current configuration."""
        response = await test_client.get("/api/config/")
        assert response.status_code == 200

        data = response.json()
        assert "prechill_temp" in data
        assert "ice_target_temp" in data
        assert "harvest_threshold" in data
        assert "bin_full_threshold" in data

    @pytest.mark.asyncio
    async def test_update_config(self, test_client: AsyncClient) -> None:
        """Should update configuration."""
        response = await test_client.put(
            "/api/config/",
            json={"prechill_temp": 30.0, "bin_full_threshold": 40.0},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["prechill_temp"] == 30.0
        assert data["bin_full_threshold"] == 40.0
