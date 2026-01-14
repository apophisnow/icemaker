"""Constants for the Icemaker integration."""

DOMAIN = "icemaker"

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_PORT = 8000

# Update intervals
SCAN_INTERVAL_SECONDS = 5

# Icemaker states
ICEMAKER_STATES = [
    "IDLE",
    "POWER_ON",
    "CHILL",
    "ICE",
    "HEAT",
    "ERROR",
    "SHUTDOWN",
]

# Relay names
RELAY_NAMES = [
    "water_valve",
    "hot_gas_solenoid",
    "recirculating_pump",
    "compressor_1",
    "compressor_2",
    "condenser_fan",
    "LED",
    "ice_cutter",
]

# Friendly names for relays
RELAY_FRIENDLY_NAMES = {
    "water_valve": "Water Valve",
    "hot_gas_solenoid": "Hot Gas Solenoid",
    "recirculating_pump": "Recirculating Pump",
    "compressor_1": "Compressor 1",
    "compressor_2": "Compressor 2",
    "condenser_fan": "Condenser Fan",
    "LED": "LED",
    "ice_cutter": "Ice Cutter",
}
