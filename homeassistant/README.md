# Icemaker Home Assistant Integration

Custom Home Assistant integration for monitoring and controlling the icemaker.

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Icemaker" and install
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/icemaker` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Icemaker"
3. Enter the host and port of your icemaker (default port: 8000)

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.icemaker_state` | Current state (IDLE, CHILL, ICE, HEAT, etc.) |
| `sensor.icemaker_plate_temperature` | Plate temperature in °F |
| `sensor.icemaker_bin_temperature` | Ice bin temperature in °F |
| `sensor.icemaker_target_temperature` | Target temperature for current state |
| `sensor.icemaker_cycle_count` | Total completed ice-making cycles |
| `sensor.icemaker_time_in_state` | Time spent in current state |

### Binary Sensors (Relays)

| Entity | Description |
|--------|-------------|
| `binary_sensor.icemaker_water_valve` | Water valve relay state |
| `binary_sensor.icemaker_hot_gas_solenoid` | Hot gas solenoid relay state |
| `binary_sensor.icemaker_recirculating_pump` | Recirculating pump relay state |
| `binary_sensor.icemaker_compressor_1` | Compressor 1 relay state |
| `binary_sensor.icemaker_compressor_2` | Compressor 2 relay state |
| `binary_sensor.icemaker_condenser_fan` | Condenser fan relay state |
| `binary_sensor.icemaker_led` | LED relay state |
| `binary_sensor.icemaker_ice_cutter` | Ice cutter relay state |

### Buttons

| Entity | Description |
|--------|-------------|
| `button.icemaker_start_cycle` | Start an ice-making cycle |
| `button.icemaker_emergency_stop` | Emergency stop - turns off all relays |

## Example Automations

### Notify when cycle completes

```yaml
automation:
  - alias: "Icemaker Cycle Complete"
    trigger:
      - platform: state
        entity_id: sensor.icemaker_state
        to: "IDLE"
        from: "HEAT"
    action:
      - service: notify.mobile_app
        data:
          message: "Ice making cycle complete! {{ states('sensor.icemaker_cycle_count') }} cycles total."
```

### Dashboard Card

```yaml
type: entities
title: Icemaker
entities:
  - entity: sensor.icemaker_state
  - entity: sensor.icemaker_plate_temperature
  - entity: sensor.icemaker_bin_temperature
  - entity: sensor.icemaker_target_temperature
  - entity: sensor.icemaker_cycle_count
  - type: divider
  - entity: button.icemaker_start_cycle
  - entity: button.icemaker_emergency_stop
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Icemaker running with API accessible on the network
