/**
 * Visual display of relay states.
 */

import type { RelayStates } from '../types/icemaker';

interface RelayStatusProps {
  relays: RelayStates | null;
}

const RELAY_DISPLAY_NAMES: Record<keyof RelayStates, string> = {
  water_valve: 'Water Valve',
  hot_gas_solenoid: 'Hot Gas',
  recirculating_pump: 'Recirculating Pump',
  compressor_1: 'Compressor 1',
  compressor_2: 'Compressor 2',
  condenser_fan: 'Condenser Fan',
  LED: 'LED',
  ice_cutter: 'Ice Cutter',
};

const RELAY_ORDER: (keyof RelayStates)[] = [
  'compressor_1',
  'compressor_2',
  'condenser_fan',
  'hot_gas_solenoid',
  'water_valve',
  'recirculating_pump',
  'ice_cutter',
  'LED',
];

export function RelayStatus({ relays }: RelayStatusProps) {
  if (!relays) {
    return (
      <div className="relay-status">
        <h3>Relay Status</h3>
        <p className="loading">Loading...</p>
      </div>
    );
  }

  return (
    <div className="relay-status">
      <h3>Relay Status</h3>
      <div className="relay-grid">
        {RELAY_ORDER.map((key) => {
          const isOn = relays[key];
          return (
            <div
              key={key}
              className={`relay-item ${isOn ? 'on' : 'off'}`}
            >
              <div className={`relay-indicator ${isOn ? 'on' : 'off'}`} />
              <span className="relay-name">{RELAY_DISPLAY_NAMES[key]}</span>
              <span className="relay-state">{isOn ? 'ON' : 'OFF'}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
