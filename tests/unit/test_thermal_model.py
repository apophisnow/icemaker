"""Tests for physics-based thermal model."""

import pytest

from icemaker.hal.base import RelayName, SensorName
from icemaker.simulator.thermal_model import ThermalModel, ThermalParameters


class TestThermalModelInitialization:
    """Test thermal model initialization."""

    def test_initial_temperature_is_ambient(self, thermal_model: ThermalModel) -> None:
        """Temperatures should start at ambient (70°F)."""
        assert thermal_model.get_temperature(SensorName.PLATE) == 70.0
        assert thermal_model.get_temperature(SensorName.ICE_BIN) == 70.0

    def test_custom_parameters(self) -> None:
        """Model should accept custom parameters."""
        params = ThermalParameters(ambient_temp_f=80.0)
        model = ThermalModel(params)
        assert model.params.ambient_temp_f == 80.0

    def test_initial_relay_states_are_off(self, thermal_model: ThermalModel) -> None:
        """All relays should start OFF."""
        for relay in RelayName:
            assert thermal_model._relay_states[relay] is False


class TestCompressorCooling:
    """Test compressor cooling effects."""

    def test_compressor_cools_plate(self, fast_thermal_model: ThermalModel) -> None:
        """Compressor + condenser should cool the plate."""
        model = fast_thermal_model
        initial_temp = model.get_temperature(SensorName.PLATE)

        model.set_relay_state(RelayName.COMPRESSOR_1, True)
        model.set_relay_state(RelayName.CONDENSER_FAN, True)

        # Simulate 60 seconds
        model.update(60.0)

        final_temp = model.get_temperature(SensorName.PLATE)
        assert final_temp < initial_temp

    def test_compressor_without_condenser_cools_slower(
        self, fast_thermal_model: ThermalModel
    ) -> None:
        """Compressor without condenser should cool slower."""
        # With condenser
        model1 = ThermalModel(ThermalParameters(compressor_cooling_rate=1.5))
        model1.set_relay_state(RelayName.COMPRESSOR_1, True)
        model1.set_relay_state(RelayName.CONDENSER_FAN, True)
        model1.update(60.0)
        temp_with_condenser = model1.get_temperature(SensorName.PLATE)

        # Without condenser
        model2 = ThermalModel(ThermalParameters(compressor_cooling_rate=1.5))
        model2.set_relay_state(RelayName.COMPRESSOR_1, True)
        model2.set_relay_state(RelayName.CONDENSER_FAN, False)
        model2.update(60.0)
        temp_without_condenser = model2.get_temperature(SensorName.PLATE)

        # With condenser should be colder
        assert temp_with_condenser < temp_without_condenser

    def test_both_compressors_work_together(
        self, fast_thermal_model: ThermalModel
    ) -> None:
        """Either compressor should enable cooling."""
        model = fast_thermal_model
        model.set_relay_state(RelayName.COMPRESSOR_2, True)  # Using second compressor
        model.set_relay_state(RelayName.CONDENSER_FAN, True)
        model.update(60.0)

        assert model.get_temperature(SensorName.PLATE) < 70.0


class TestHotGasHeating:
    """Test hot gas solenoid heating effects."""

    def test_hot_gas_heats_plate(self, fast_thermal_model: ThermalModel) -> None:
        """Hot gas solenoid should heat the plate."""
        model = fast_thermal_model
        model.state.plate_temp_f = 10.0  # Start cold

        model.set_relay_state(RelayName.HOT_GAS_SOLENOID, True)
        model.set_relay_state(RelayName.COMPRESSOR_1, True)

        model.update(30.0)

        assert model.get_temperature(SensorName.PLATE) > 10.0


class TestRecirculation:
    """Test recirculation pump effects."""

    def test_recirculation_enhances_cooling(self) -> None:
        """Recirculation pump should enhance cooling rate."""
        params = ThermalParameters(compressor_cooling_rate=0.5)

        # Without recirculation - shorter time to avoid hitting min temp
        model1 = ThermalModel(params)
        model1.set_relay_state(RelayName.COMPRESSOR_1, True)
        model1.set_relay_state(RelayName.CONDENSER_FAN, True)
        model1.update(30.0)
        temp_without_recirc = model1.get_temperature(SensorName.PLATE)

        # With recirculation
        model2 = ThermalModel(params)
        model2.set_relay_state(RelayName.COMPRESSOR_1, True)
        model2.set_relay_state(RelayName.CONDENSER_FAN, True)
        model2.set_relay_state(RelayName.RECIRCULATING_PUMP, True)
        model2.update(30.0)
        temp_with_recirc = model2.get_temperature(SensorName.PLATE)

        assert temp_with_recirc < temp_without_recirc

    def test_recirculation_does_not_enhance_heating(self) -> None:
        """Recirculation should not enhance heating."""
        params = ThermalParameters(hot_gas_heating_rate=8.0)

        # Without recirculation (heating)
        model1 = ThermalModel(params)
        model1.state.plate_temp_f = 20.0
        model1.set_relay_state(RelayName.HOT_GAS_SOLENOID, True)
        model1.update(30.0)
        temp_without_recirc = model1.get_temperature(SensorName.PLATE)

        # With recirculation (heating)
        model2 = ThermalModel(params)
        model2.state.plate_temp_f = 20.0
        model2.set_relay_state(RelayName.HOT_GAS_SOLENOID, True)
        model2.set_relay_state(RelayName.RECIRCULATING_PUMP, True)
        model2.update(30.0)
        temp_with_recirc = model2.get_temperature(SensorName.PLATE)

        # Should be approximately the same (recirculation doesn't affect heating)
        assert abs(temp_with_recirc - temp_without_recirc) < 1.0


class TestAmbientDrift:
    """Test natural drift toward ambient temperature."""

    def test_idle_drifts_toward_ambient(self, thermal_model: ThermalModel) -> None:
        """Idle system should drift toward ambient temperature."""
        thermal_model.state.plate_temp_f = 0.0  # Start cold

        # All relays off, simulate 5 minutes
        thermal_model.update(300.0)

        # Should have warmed toward ambient (70°F)
        assert thermal_model.get_temperature(SensorName.PLATE) > 0.0


class TestTemperatureClamping:
    """Test temperature limits."""

    def test_temperature_clamped_to_minimum(
        self, thermal_model: ThermalModel
    ) -> None:
        """Temperatures should not go below minimum."""
        thermal_model.state.plate_temp_f = -100.0  # Below minimum
        thermal_model.update(0.1)

        assert thermal_model.get_temperature(SensorName.PLATE) >= -10.0

    def test_temperature_clamped_to_maximum(
        self, thermal_model: ThermalModel
    ) -> None:
        """Temperatures should not exceed maximum."""
        thermal_model.state.plate_temp_f = 200.0  # Above maximum
        thermal_model.update(0.1)

        assert thermal_model.get_temperature(SensorName.PLATE) <= 100.0


class TestBinTemperature:
    """Test ice bin temperature behavior."""

    def test_bin_affected_by_plate(self, fast_thermal_model: ThermalModel) -> None:
        """Bin temperature should be affected by plate temperature."""
        model = fast_thermal_model
        model.state.plate_temp_f = 0.0  # Cold plate
        model.state.bin_temp_f = 70.0  # Warm bin

        # Simulate time - bin should cool toward plate temp
        model.update(600.0)

        assert model.get_temperature(SensorName.ICE_BIN) < 70.0


class TestReset:
    """Test model reset functionality."""

    def test_reset_temperatures(self, thermal_model: ThermalModel) -> None:
        """Reset should restore initial temperatures."""
        thermal_model.state.plate_temp_f = 0.0
        thermal_model.state.bin_temp_f = 20.0

        thermal_model.reset(plate_temp=50.0, bin_temp=60.0)

        assert thermal_model.get_temperature(SensorName.PLATE) == 50.0
        assert thermal_model.get_temperature(SensorName.ICE_BIN) == 60.0

    def test_reset_clears_relay_states(self, thermal_model: ThermalModel) -> None:
        """Reset should turn off all relays."""
        thermal_model.set_relay_state(RelayName.COMPRESSOR_1, True)
        thermal_model.set_relay_state(RelayName.CONDENSER_FAN, True)

        thermal_model.reset()

        for relay in RelayName:
            assert thermal_model._relay_states[relay] is False
