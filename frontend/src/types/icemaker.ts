/**
 * TypeScript types for icemaker control system.
 */

export type IcemakerState =
  | 'OFF'
  | 'IDLE'
  | 'POWER_ON'
  | 'CHILL'
  | 'ICE'
  | 'HEAT'
  | 'ERROR'
  | 'SHUTDOWN';

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
  ice_thickness_mm?: number;
  timestamp: string;
}

export interface IcemakerStatus {
  state: IcemakerState;
  previous_state: IcemakerState | null;
  state_enter_time: string;
  cycle_count: number;
  plate_temp: number;
  bin_temp: number;
  water_temp?: number;
  ice_thickness_mm?: number;
  target_temp: number | null;
  time_in_state_seconds: number;
  chill_mode: string | null;
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
  rechill_temp: number;
  rechill_timeout: number;
  bin_full_threshold: number;
  poll_interval: number;
  use_simulator: boolean;
}

export interface StateUpdateData {
  state: IcemakerState;
  previous_state: IcemakerState | null;
  plate_temp: number;
  bin_temp: number;
  target_temp: number | null;
  cycle_count: number;
  time_in_state_seconds: number;
  chill_mode: string | null;
}

export interface TempUpdateData {
  plate_temp_f: number;
  bin_temp_f: number;
  water_temp_f?: number;
  ice_thickness_mm?: number;
  target_temp?: number;
}

export interface RelayUpdateData {
  relays: RelayStates;
}

export interface ErrorData {
  message: string;
  error_type?: string;
}
