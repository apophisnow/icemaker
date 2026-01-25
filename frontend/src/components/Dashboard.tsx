/**
 * Main dashboard component.
 */

import { useEffect, useState } from 'react';
import { useIcemakerState } from '../hooks/useIcemakerState';
import { useTemperature } from '../contexts/TemperatureContext';
import { useDataLogger } from '../contexts/DataLoggerContext';
import { DataLogger } from './DataLogger';
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
  const { logData, isLogging } = useDataLogger();
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Log data when status updates and logging is active
  useEffect(() => {
    if (isLogging && status) {
      // Get simulated time from the latest temperature reading
      const latestReading = temperatureHistory[temperatureHistory.length - 1];
      const simulatedTime = latestReading?.simulated_time_seconds;
      logData(status, relays, simulatedTime);
    }
  }, [isLogging, status, relays, temperatureHistory, logData]);

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

      <div className="dashboard-layout">
        <aside className="sidebar">
          <MainPanel
            status={status}
            relays={relays}
            simulatedTimeInState={status?.time_in_state_seconds}
          />
          <DataLogger />
        </aside>

        <main className="main-content">
          <TemperatureChart
            data={temperatureHistory}
            targetTemp={status?.target_temp}
          />
        </main>
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
