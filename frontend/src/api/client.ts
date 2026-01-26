/**
 * REST API client for icemaker backend.
 */

import type { ConfigSchemaResponse, IcemakerConfig, IcemakerStatus, RelayStates, TemperatureReading } from '../types/icemaker';

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function fetchStatus(): Promise<IcemakerStatus> {
  return fetchJson<IcemakerStatus>(`${API_BASE}/state/`);
}

export async function fetchRelays(): Promise<RelayStates> {
  const response = await fetchJson<{ relays: RelayStates }>(`${API_BASE}/relays/`);
  return response.relays;
}

export async function fetchTemperatures(): Promise<TemperatureReading> {
  return fetchJson<TemperatureReading>(`${API_BASE}/sensors/`);
}

export async function fetchConfig(): Promise<IcemakerConfig> {
  return fetchJson<IcemakerConfig>(`${API_BASE}/config/`);
}

export async function fetchConfigSchema(): Promise<ConfigSchemaResponse> {
  return fetchJson<ConfigSchemaResponse>(`${API_BASE}/config/schema`);
}

export async function startIcemaking(): Promise<{ success: boolean; message: string }> {
  return fetchJson(`${API_BASE}/state/cycle`, {
    method: 'POST',
    body: JSON.stringify({ action: 'start' }),
  });
}

export async function stopIcemaking(): Promise<{ success: boolean; message: string }> {
  return fetchJson(`${API_BASE}/state/cycle`, {
    method: 'POST',
    body: JSON.stringify({ action: 'stop' }),
  });
}

export async function emergencyStop(): Promise<{ success: boolean; message: string }> {
  return fetchJson(`${API_BASE}/state/cycle`, {
    method: 'POST',
    body: JSON.stringify({ action: 'emergency_stop' }),
  });
}

export async function enterDiagnostic(): Promise<{ success: boolean; message: string }> {
  return fetchJson(`${API_BASE}/state/cycle`, {
    method: 'POST',
    body: JSON.stringify({ action: 'enter_diagnostic' }),
  });
}

export async function exitDiagnostic(): Promise<{ success: boolean; message: string }> {
  return fetchJson(`${API_BASE}/state/cycle`, {
    method: 'POST',
    body: JSON.stringify({ action: 'exit_diagnostic' }),
  });
}

export async function setRelay(
  relay: string,
  on: boolean
): Promise<{ success: boolean }> {
  return fetchJson(`${API_BASE}/relays/`, {
    method: 'POST',
    body: JSON.stringify({ relay, on }),
  });
}

export async function allRelaysOff(): Promise<{ success: boolean }> {
  return fetchJson(`${API_BASE}/relays/all-off`, {
    method: 'POST',
  });
}

export async function updateConfig(
  updates: Partial<IcemakerConfig>
): Promise<IcemakerConfig> {
  return fetchJson(`${API_BASE}/config/`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function resetConfig(): Promise<IcemakerConfig> {
  return fetchJson(`${API_BASE}/config/reset`, {
    method: 'POST',
  });
}

export async function transitionState(
  targetState: string,
  force = false
): Promise<{ success: boolean; new_state: string }> {
  return fetchJson(`${API_BASE}/state/transition`, {
    method: 'POST',
    body: JSON.stringify({ target_state: targetState, force }),
  });
}

// Simulator API

export interface SimulatorStatus {
  enabled: boolean;
  speed_multiplier: number;
  water_temp_f: number;
  plate_temp_f: number;
  bin_temp_f: number;
}

export async function fetchSimulatorStatus(): Promise<SimulatorStatus> {
  return fetchJson<SimulatorStatus>(`${API_BASE}/simulator/`);
}

export async function setSimulatorSpeed(
  multiplier: number
): Promise<{ speed_multiplier: number; message: string }> {
  return fetchJson(`${API_BASE}/simulator/speed`, {
    method: 'POST',
    body: JSON.stringify({ multiplier }),
  });
}

export async function resetSimulator(): Promise<{
  message: string;
  plate_temp_f: number;
  bin_temp_f: number;
  water_temp_f: number;
}> {
  return fetchJson(`${API_BASE}/simulator/reset`, {
    method: 'POST',
  });
}
