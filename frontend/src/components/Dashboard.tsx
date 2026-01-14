/**
 * Main dashboard component.
 */

import { useIcemakerState } from '../hooks/useIcemakerState';
import { useTemperature } from '../contexts/TemperatureContext';
import { Controls } from './Controls';
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
      </div>
    </div>
  );
}
