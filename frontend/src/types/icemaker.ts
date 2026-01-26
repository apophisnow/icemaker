/**
 * TypeScript types for icemaker control system.
 */

export type IcemakerState =
  | 'OFF'
  | 'STANDBY'
  | 'IDLE'
  | 'POWER_ON'
  | 'CHILL'
  | 'ICE'
  | 'HEAT'
  | 'ERROR'
  | 'SHUTDOWN'
  | 'DIAGNOSTIC';

export interface RelayStates {
  water_valve: boolean;
  hot_gas_solenoid: boolean;
  recirculating_pump: boolean;
  compressor_1: boolean;
  compressor_2: boolean;
  condenser_fan: boolean;
  LED: boolean;
  ice_cutter: boolean;
}

export interface TemperatureReading {
  plate_temp_f: number;
  bin_temp_f: number;
  water_temp_f?: number;
  simulated_time_seconds?: number;
  timestamp: string;
}

export interface IcemakerStatus {
  state: IcemakerState;
  previous_state: IcemakerState | null;
  state_enter_time: string;
  cycle_count: number;  // Lifetime cycle count
  session_cycle_count: number;  // Session cycle count (since server start)
  plate_temp: number;
  bin_temp: number;
  water_temp?: number;
  target_temp: number | null;
  time_in_state_seconds: number;
  chill_mode: string | null;
  shutdown_requested: boolean;  // Graceful shutdown in progress
}

export interface WebSocketMessage {
  type: 'state_update' | 'temp_update' | 'relay_update' | 'error';
  data: Record<string, unknown>;
  timestamp: string;
}

export interface IcemakerConfig {
  prechill_temp: number;
  prechill_timeout: number;
  ice_target_temp: number;
  ice_timeout: number;
  harvest_threshold: number;
  harvest_timeout: number;
  harvest_fill_time: number;
  rechill_temp: number;
  rechill_timeout: number;
  bin_full_threshold: number;
  poll_interval: number;
  standby_timeout: number;
  use_simulator: boolean;
  priming_enabled: boolean;
  priming_flush_time: number;
  priming_pump_time: number;
  priming_fill_time: number;
}

export interface ConfigFieldSchema {
  key: string;
  name: string;
  description: string;
  type: 'float' | 'int' | 'bool';
  category: 'chill' | 'ice' | 'harvest' | 'rechill' | 'idle' | 'standby' | 'priming' | 'system';
  unit?: string;
  min_value?: number;
  max_value?: number;
  step?: number;
  default?: number | boolean;
  readonly: boolean;
}

export interface ConfigSchemaResponse {
  fields: ConfigFieldSchema[];
  categories: string[];
}

export interface StateUpdateData {
  state: IcemakerState;
  previous_state: IcemakerState | null;
  plate_temp: number;
  bin_temp: number;
  target_temp: number | null;
  cycle_count: number;
  session_cycle_count: number;
  time_in_state_seconds: number;
  chill_mode: string | null;
}

export interface TempUpdateData {
  plate_temp_f: number;
  bin_temp_f: number;
  water_temp_f?: number;
  target_temp?: number;
  simulated_time_seconds?: number;
  time_in_state_seconds?: number;
}

export interface RelayUpdateData {
  relays: RelayStates;
}

export interface ErrorData {
  message: string;
  error_type?: string;
}
