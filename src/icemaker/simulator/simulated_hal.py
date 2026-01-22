"""Simulated HAL connected to physics simulator."""

from ..hal.base import GPIOInterface, TemperatureSensorInterface
from ..hal.mock_gpio import MockGPIO
from ..hal.mock_sensors import MockSensors
from .physics_model import PhysicsSimulator, SimulatorParams


def create_simulated_hal(
    params: SimulatorParams | None = None,
) -> tuple[GPIOInterface, TemperatureSensorInterface, PhysicsSimulator]:
    """Create HAL implementations connected to physics simulator.

    Creates mock GPIO and sensors that are connected to a physics-based
    simulator. When relay states change, the simulator adjusts its
    temperature calculations accordingly. Temperature readings come
    from the physics simulation.

    Example:
        gpio, sensors, simulator = create_simulated_hal()
        await gpio.setup(DEFAULT_RELAY_CONFIG)
        await sensors.setup(DEFAULT_SENSOR_IDS)
        await simulator.start()  # Run simulation in background

        # Now relay changes affect temperatures
        await gpio.set_relay(RelayName.COMPRESSOR_1, True)
        # ... temperatures will decrease over time

        temp = await sensors.read_temperature(SensorName.PLATE)

    Args:
        params: Custom simulator parameters. Uses defaults if None.

    Returns:
        Tuple of (GPIO, Sensors, PhysicsSimulator).
        The simulator must be started separately with simulator.start()
        or simulator.run() (blocking).
    """
    simulator = PhysicsSimulator(params)

    # Create mock GPIO connected to simulator
    gpio = MockGPIO()
    gpio.set_change_callback(simulator.set_relay_state)

    # Create mock sensors connected to simulator
    sensors = MockSensors()
    sensors.set_temperature_provider(simulator.get_temperature)

    return gpio, sensors, simulator
