"""Simulated HAL connected to thermal model."""

from ..hal.base import GPIOInterface, TemperatureSensorInterface
from ..hal.mock_gpio import MockGPIO
from ..hal.mock_sensors import MockSensors
from .thermal_model import ThermalModel, ThermalParameters


def create_simulated_hal(
    thermal_params: ThermalParameters | None = None,
) -> tuple[GPIOInterface, TemperatureSensorInterface, ThermalModel]:
    """Create HAL implementations connected to thermal simulator.

    Creates mock GPIO and sensors that are connected to a physics-based
    thermal model. When relay states change, the thermal model adjusts
    its temperature calculations accordingly. Temperature readings come
    from the thermal model simulation.

    Example:
        gpio, sensors, model = create_simulated_hal()
        await gpio.setup(DEFAULT_RELAY_CONFIG)
        await sensors.setup(DEFAULT_SENSOR_IDS)
        await model.start()  # Run simulation in background

        # Now relay changes affect temperatures
        await gpio.set_relay(RelayName.COMPRESSOR_1, True)
        # ... temperatures will decrease over time

        temp = await sensors.read_temperature(SensorName.PLATE)

    Args:
        thermal_params: Custom thermal parameters. Uses defaults if None.

    Returns:
        Tuple of (GPIO, Sensors, ThermalModel).
        The thermal model must be started separately with model.start()
        or model.run() (blocking).
    """
    model = ThermalModel(thermal_params)

    # Create mock GPIO connected to thermal model
    gpio = MockGPIO()
    gpio.set_change_callback(model.set_relay_state)

    # Create mock sensors connected to thermal model
    sensors = MockSensors()
    sensors.set_temperature_provider(model.get_temperature)

    return gpio, sensors, model
