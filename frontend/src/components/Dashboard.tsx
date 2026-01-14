/**
 * Main dashboard component.
 */

import { useEffect } from 'react';
import { useIcemakerState } from '../hooks/useIcemakerState';
import { useTemperature } from '../contexts/TemperatureContext';
import { useDataLogger } from '../contexts/DataLoggerContext';
import { Controls } from './Controls';
import { DataLogger } from './DataLogger';
import { RelayStatus } from './RelayStatus';
import { StateDisplay } from './StateDisplay';
import { TemperatureChart } from './TemperatureChart';

export function Dashboard() {
  const {
    status,
    relays,
    temperatureHistory,
    isConnected,
    isLoading,
    error,
    clearError,
    refresh,
  } = useIcemakerState();
  const { unit, toggleUnit } = useTemperature();
  const { logData, isLogging } = useDataLogger();

  // Log data when status updates and logging is active
  useEffect(() => {
    if (isLogging && status) {
      logData(status, relays);
    }
  }, [isLogging, status, relays, logData]);

  if (isLoading) {
    return (
      <div className="dashboard loading-state">
        <div className="loading-spinner" />
        <p>Loading icemaker status...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Icemaker Control Panel</h1>
        <div className="header-status">
          <button
            className="unit-toggle"
            onClick={toggleUnit}
            title="Toggle temperature unit"
          >
            °{unit}
          </button>
          <div
            className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}
          >
            <span className="status-dot" />
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError}>Dismiss</button>
        </div>
      )}

      <div className="dashboard-grid">
        <section className="state-section">
          <StateDisplay status={status} />
        </section>

        <section className="chart-section">
          <TemperatureChart
            data={temperatureHistory}
            targetTemp={status?.target_temp}
          />
        </section>

        <section className="relay-section">
          <RelayStatus relays={relays} />
        </section>

        <section className="controls-section">
          <Controls
            currentState={status?.state}
            onError={() => clearError()}
            onRefresh={refresh}
          />
        </section>

        <section className="logger-section">
          <DataLogger />
        </section>
      </div>
    </div>
  );
}
