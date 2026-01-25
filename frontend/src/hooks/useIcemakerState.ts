/**
 * Hook for managing icemaker state with WebSocket updates.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchRelays, fetchStatus } from '../api/client';
import type {
  IcemakerStatus,
  RelayStates,
  RelayUpdateData,
  StateUpdateData,
  TempUpdateData,
  TemperatureReading,
  WebSocketMessage,
} from '../types/icemaker';
import { useWebSocket } from './useWebSocket';

interface IcemakerState {
  status: IcemakerStatus | null;
  relays: RelayStates | null;
  temperatureHistory: TemperatureReading[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

// Use current host for WebSocket (works in both dev and production)
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${WS_PROTOCOL}//${window.location.host}/api/state/ws`;
const MAX_HISTORY = 1000;
const STORAGE_KEY = 'icemaker_temp_history';
const RETENTION_KEY = 'icemaker_retention_hours';
const DEFAULT_RETENTION_HOURS = 24;

export function getRetentionHours(): number {
  try {
    const stored = localStorage.getItem(RETENTION_KEY);
    if (stored) {
      const hours = parseInt(stored, 10);
      if (!isNaN(hours) && hours > 0) return hours;
    }
  } catch {
    // Ignore storage errors
  }
  return DEFAULT_RETENTION_HOURS;
}

export function setRetentionHours(hours: number): void {
  try {
    localStorage.setItem(RETENTION_KEY, String(hours));
  } catch {
    // Ignore storage errors
  }
}

function loadStoredHistory(): TemperatureReading[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as TemperatureReading[];
      const retentionMs = getRetentionHours() * 60 * 60 * 1000;
      const cutoff = Date.now() - retentionMs;
      return parsed.filter(r => new Date(r.timestamp).getTime() > cutoff);
    }
  } catch {
    // Ignore storage errors
  }
  return [];
}

function saveHistory(history: TemperatureReading[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Ignore storage errors (quota exceeded, etc.)
  }
}

export function useIcemakerState() {
  const [state, setState] = useState<IcemakerState>(() => ({
    status: null,
    relays: null,
    temperatureHistory: loadStoredHistory(),
    isConnected: false,
    isLoading: true,
    error: null,
  }));

  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'state_update': {
        const data = message.data as unknown as StateUpdateData;
        setState((prev) => ({
          ...prev,
          status: prev.status
            ? {
                ...prev.status,
                state: data.state,
                previous_state: data.previous_state,
                plate_temp: data.plate_temp,
                bin_temp: data.bin_temp,
                target_temp: data.target_temp,
                cycle_count: data.cycle_count,
                session_cycle_count: data.session_cycle_count,
                time_in_state_seconds: data.time_in_state_seconds,
                chill_mode: data.chill_mode,
              }
            : null,
        }));
        break;
      }

      case 'temp_update': {
        const data = message.data as unknown as TempUpdateData;
        const tempReading: TemperatureReading = {
          plate_temp_f: data.plate_temp_f,
          bin_temp_f: data.bin_temp_f,
          water_temp_f: data.water_temp_f,
          simulated_time_seconds: data.simulated_time_seconds,
          timestamp: message.timestamp,
        };
        setState((prev) => {
          const newHistory = [
            ...prev.temperatureHistory.slice(-MAX_HISTORY + 1),
            tempReading,
          ];
          // Save to localStorage
          saveHistory(newHistory);
          return {
            ...prev,
            temperatureHistory: newHistory,
            status: prev.status
              ? {
                  ...prev.status,
                  plate_temp: data.plate_temp_f,
                  bin_temp: data.bin_temp_f,
                  water_temp: data.water_temp_f,
                  target_temp: data.target_temp ?? prev.status.target_temp,
                  time_in_state_seconds:
                    data.time_in_state_seconds ?? prev.status.time_in_state_seconds,
                }
              : null,
          };
        });
        break;
      }

      case 'relay_update': {
        const data = message.data as unknown as RelayUpdateData;
        setState((prev) => ({
          ...prev,
          relays: data.relays,
        }));
        break;
      }

      case 'error': {
        const data = message.data as { message: string };
        setState((prev) => ({
          ...prev,
          error: data.message,
        }));
        break;
      }
    }
  }, []);

  const { isConnected, reconnect } = useWebSocket({
    url: WS_URL,
    onMessage: handleMessage,
  });

  // Initial fetch
  useEffect(() => {
    async function loadInitialState() {
      try {
        const [status, relays] = await Promise.all([
          fetchStatus(),
          fetchRelays(),
        ]);
        setState((prev) => ({
          ...prev,
          status,
          relays,
          isLoading: false,
        }));
      } catch (e) {
        setState((prev) => ({
          ...prev,
          error: e instanceof Error ? e.message : 'Failed to load state',
          isLoading: false,
        }));
      }
    }
    loadInitialState();
  }, []);

  useEffect(() => {
    setState((prev) => ({ ...prev, isConnected }));
  }, [isConnected]);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [status, relays] = await Promise.all([
        fetchStatus(),
        fetchRelays(),
      ]);
      setState((prev) => ({
        ...prev,
        status,
        relays,
        error: null,
      }));
    } catch (e) {
      setState((prev) => ({
        ...prev,
        error: e instanceof Error ? e.message : 'Failed to refresh',
      }));
    }
  }, []);

  return { ...state, reconnect, clearError, refresh };
}
