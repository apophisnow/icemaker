"""Tests for HAL interfaces."""

import pytest

from icemaker.hal.base import DEFAULT_RELAY_CONFIG, RelayName, SensorName
from icemaker.hal.mock_gpio import MockGPIO
from icemaker.hal.mock_sensors import MockSensors


class TestMockGPIO:
    """Test MockGPIO implementation."""

    @pytest.mark.asyncio
    async def test_setup_initializes_all_relays_off(
        self, initialized_gpio: MockGPIO
    ) -> None:
        """All relays should be OFF after setup."""
        for relay in RelayName:
            state = await initialized_gpio.get_relay(relay)
            assert state is False

    @pytest.mark.asyncio
    async def test_set_relay_on(self, initialized_gpio: MockGPIO) -> None:
        """Should be able to turn relay ON."""
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)
        state = await initialized_gpio.get_relay(RelayName.COMPRESSOR_1)
        assert state is True

    @pytest.mark.asyncio
    async def test_set_relay_off(self, initialized_gpio: MockGPIO) -> None:
        """Should be able to turn relay OFF."""
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, False)
        state = await initialized_gpio.get_relay(RelayName.COMPRESSOR_1)
        assert state is False

    @pytest.mark.asyncio
    async def test_get_all_relays(self, initialized_gpio: MockGPIO) -> None:
        """get_all_relays should return all relay states."""
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)
        await initialized_gpio.set_relay(RelayName.CONDENSER_FAN, True)

        states = await initialized_gpio.get_all_relays()

        assert states[RelayName.COMPRESSOR_1] is True
        assert states[RelayName.CONDENSER_FAN] is True
        assert states[RelayName.WATER_VALVE] is False

    @pytest.mark.asyncio
    async def test_unknown_relay_raises_error(
        self, mock_gpio: MockGPIO
    ) -> None:
        """Setting unknown relay should raise ValueError."""
        # Not initialized, so all relays are unknown
        with pytest.raises(ValueError, match="Unknown relay"):
            await mock_gpio.set_relay(RelayName.COMPRESSOR_1, True)

    @pytest.mark.asyncio
    async def test_change_callback(self, initialized_gpio: MockGPIO) -> None:
        """Change callback should be called on state change."""
        changes: list = []

        def callback(relay: RelayName, state: bool) -> None:
            changes.append((relay, state))

        initialized_gpio.set_change_callback(callback)
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)

        assert len(changes) == 1
        assert changes[0] == (RelayName.COMPRESSOR_1, True)

    @pytest.mark.asyncio
    async def test_callback_not_called_if_state_unchanged(
        self, initialized_gpio: MockGPIO
    ) -> None:
        """Callback should not be called if state doesn't change."""
        changes: list = []

        def callback(relay: RelayName, state: bool) -> None:
            changes.append((relay, state))

        initialized_gpio.set_change_callback(callback)

        # Turn ON twice
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)

        assert len(changes) == 1

    @pytest.mark.asyncio
    async def test_cleanup_turns_off_all_relays(
        self, initialized_gpio: MockGPIO
    ) -> None:
        """Cleanup should turn off all relays."""
        await initialized_gpio.set_relay(RelayName.COMPRESSOR_1, True)
        await initialized_gpio.set_relay(RelayName.CONDENSER_FAN, True)

        await initialized_gpio.cleanup()

        states = await initialized_gpio.get_all_relays()
        for state in states.values():
            assert state is False


class TestMockSensors:
    """Test MockSensors implementation."""

    @pytest.mark.asyncio
    async def test_initial_temperatures(
        self, initialized_sensors: MockSensors
    ) -> None:
        """Should have default initial temperatures."""
        plate = await initialized_sensors.read_temperature(SensorName.PLATE)
        bin_temp = await initialized_sensors.read_temperature(SensorName.ICE_BIN)

        assert plate == 70.0
        assert bin_temp == 70.0

    @pytest.mark.asyncio
    async def test_set_temperature(
        self, initialized_sensors: MockSensors
    ) -> None:
        """Should be able to manually set temperature."""
        initialized_sensors.set_temperature(SensorName.PLATE, 32.0)
        temp = await initialized_sensors.read_temperature(SensorName.PLATE)
        assert temp == 32.0

    @pytest.mark.asyncio
    async def test_read_all_temperatures(
        self, initialized_sensors: MockSensors
    ) -> None:
        """read_all_temperatures should return all sensor values."""
        initialized_sensors.set_temperature(SensorName.PLATE, 10.0)
        initialized_sensors.set_temperature(SensorName.ICE_BIN, 35.0)

        temps = await initialized_sensors.read_all_temperatures()

        assert temps[SensorName.PLATE] == 10.0
        assert temps[SensorName.ICE_BIN] == 35.0

    @pytest.mark.asyncio
    async def test_temperature_provider(
        self, initialized_sensors: MockSensors
    ) -> None:
        """Temperature provider should override static values."""

        def provider(sensor: SensorName) -> float:
            return 42.0 if sensor == SensorName.PLATE else 55.0

        initialized_sensors.set_temperature_provider(provider)

        plate = await initialized_sensors.read_temperature(SensorName.PLATE)
        bin_temp = await initialized_sensors.read_temperature(SensorName.ICE_BIN)

        assert plate == 42.0
        assert bin_temp == 55.0

    @pytest.mark.asyncio
    async def test_custom_initial_temps(self) -> None:
        """Should accept custom initial temperatures."""
        sensors = MockSensors(
            initial_temps={
                SensorName.PLATE: 50.0,
                SensorName.ICE_BIN: 40.0,
            }
        )
        await sensors.setup({})

        plate = await sensors.read_temperature(SensorName.PLATE)
        bin_temp = await sensors.read_temperature(SensorName.ICE_BIN)

        assert plate == 50.0
        assert bin_temp == 40.0
