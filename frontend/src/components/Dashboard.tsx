/**
 * Main dashboard component.
 */

import { useState } from 'react';
import { useIcemakerState } from '../hooks/useIcemakerState';
import { useTemperature } from '../contexts/TemperatureContext';
import { MainPanel } from './MainPanel';
import { SettingsPanel } from './SettingsPanel';
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
  const [settingsOpen, setSettingsOpen] = useState(false);

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
        <h1>Icemaker</h1>
        <div className="header-actions">
          <button
            className="header-btn"
            onClick={toggleUnit}
            title="Toggle temperature unit"
          >
            °{unit}
          </button>
          <button
            className="header-btn"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            style={{ fontSize: '1.25rem' }}
          >
            ⚙
          </button>
          <div
            className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}
          >
            <span className="status-dot" />
          </div>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError}>×</button>
        </div>
      )}

      <div className="dashboard-grid">
        <MainPanel
          status={status}
          relays={relays}
          simulatedTimeInState={status?.time_in_state_seconds}
        />
        <div className="chart-card">
          <TemperatureChart
            data={temperatureHistory}
            targetTemp={status?.target_temp}
          />
        </div>
      </div>

      <SettingsPanel
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        currentState={status?.state}
        onRefresh={refresh}
      />
    </div>
  );
}
