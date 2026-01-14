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

const WS_URL = `ws://${window.location.hostname}:8000/api/state/ws`;
const MAX_HISTORY = 100;

export function useIcemakerState() {
  const [state, setState] = useState<IcemakerState>({
    status: null,
    relays: null,
    temperatureHistory: [],
    isConnected: false,
    isLoading: true,
    error: null,
  });

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
          timestamp: message.timestamp,
        };
        setState((prev) => ({
          ...prev,
          temperatureHistory: [
            ...prev.temperatureHistory.slice(-MAX_HISTORY + 1),
            tempReading,
          ],
          status: prev.status
            ? {
                ...prev.status,
                plate_temp: data.plate_temp_f,
                bin_temp: data.bin_temp_f,
              }
            : null,
        }));
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
