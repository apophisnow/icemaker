/**
 * Context for data logging functionality.
 * Records temperature and state data for export to CSV.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import type { IcemakerStatus, RelayStates } from '../types/icemaker';

export interface LogEntry {
  timestamp: string;
  simulated_time_seconds: number | null;
  state: string;
  plate_temp_f: number;
  bin_temp_f: number;
  target_temp_f: number | null;
  cycle_count: number;
  chill_mode: string | null;
  // Relay states
  compressor_1: boolean;
  compressor_2: boolean;
  condenser_fan: boolean;
  hot_gas_solenoid: boolean;
  water_valve: boolean;
  recirculating_pump: boolean;
  ice_cutter: boolean;
}

interface DataLoggerContextValue {
  isLogging: boolean;
  entryCount: number;
  startLogging: () => void;
  stopLogging: () => void;
  downloadLog: () => void;
  clearLog: () => void;
  logData: (status: IcemakerStatus, relays: RelayStates | null, simulatedTime?: number) => void;
}

const DataLoggerContext = createContext<DataLoggerContextValue | null>(null);

interface DataLoggerProviderProps {
  children: ReactNode;
}

export function DataLoggerProvider({ children }: DataLoggerProviderProps) {
  const [isLogging, setIsLogging] = useState(false);
  const [entryCount, setEntryCount] = useState(0);
  const logEntriesRef = useRef<LogEntry[]>([]);
  const startTimeRef = useRef<Date | null>(null);

  const startLogging = useCallback(() => {
    logEntriesRef.current = [];
    startTimeRef.current = new Date();
    setEntryCount(0);
    setIsLogging(true);
  }, []);

  const stopLogging = useCallback(() => {
    setIsLogging(false);
  }, []);

  const clearLog = useCallback(() => {
    logEntriesRef.current = [];
    startTimeRef.current = null;
    setEntryCount(0);
  }, []);

  const logData = useCallback(
    (status: IcemakerStatus, relays: RelayStates | null, simulatedTime?: number) => {
      if (!isLogging) return;

      const entry: LogEntry = {
        timestamp: new Date().toISOString(),
        simulated_time_seconds: simulatedTime ?? null,
        state: status.state,
        plate_temp_f: status.plate_temp,
        bin_temp_f: status.bin_temp,
        target_temp_f: status.target_temp,
        cycle_count: status.cycle_count,
        chill_mode: status.chill_mode,
        compressor_1: relays?.compressor_1 ?? false,
        compressor_2: relays?.compressor_2 ?? false,
        condenser_fan: relays?.condenser_fan ?? false,
        hot_gas_solenoid: relays?.hot_gas_solenoid ?? false,
        water_valve: relays?.water_valve ?? false,
        recirculating_pump: relays?.recirculating_pump ?? false,
        ice_cutter: relays?.ice_cutter ?? false,
      };

      logEntriesRef.current.push(entry);
      setEntryCount(logEntriesRef.current.length);
    },
    [isLogging]
  );

  const downloadLog = useCallback(() => {
    const entries = logEntriesRef.current;
    if (entries.length === 0) return;

    // Build CSV header
    const headers = [
      'timestamp',
      'simulated_time_seconds',
      'state',
      'plate_temp_f',
      'bin_temp_f',
      'target_temp_f',
      'cycle_count',
      'chill_mode',
      'compressor_1',
      'compressor_2',
      'condenser_fan',
      'hot_gas_solenoid',
      'water_valve',
      'recirculating_pump',
      'ice_cutter',
    ];

    // Build CSV rows
    const rows = entries.map((entry) =>
      [
        entry.timestamp,
        entry.simulated_time_seconds?.toFixed(2) ?? '',
        entry.state,
        entry.plate_temp_f.toFixed(2),
        entry.bin_temp_f.toFixed(2),
        entry.target_temp_f?.toFixed(2) ?? '',
        entry.cycle_count,
        entry.chill_mode ?? '',
        entry.compressor_1 ? '1' : '0',
        entry.compressor_2 ? '1' : '0',
        entry.condenser_fan ? '1' : '0',
        entry.hot_gas_solenoid ? '1' : '0',
        entry.water_valve ? '1' : '0',
        entry.recirculating_pump ? '1' : '0',
        entry.ice_cutter ? '1' : '0',
      ].join(',')
    );

    const csvContent = [headers.join(','), ...rows].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    // Generate filename with timestamp
    const startTime = startTimeRef.current ?? new Date();
    const dateStr = startTime.toISOString().slice(0, 19).replace(/[T:]/g, '-');
    link.setAttribute('href', url);
    link.setAttribute('download', `icemaker-log-${dateStr}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, []);

  return (
    <DataLoggerContext.Provider
      value={{
        isLogging,
        entryCount,
        startLogging,
        stopLogging,
        downloadLog,
        clearLog,
        logData,
      }}
    >
      {children}
    </DataLoggerContext.Provider>
  );
}

export function useDataLogger(): DataLoggerContextValue {
  const context = useContext(DataLoggerContext);
  if (!context) {
    throw new Error('useDataLogger must be used within a DataLoggerProvider');
  }
  return context;
}
