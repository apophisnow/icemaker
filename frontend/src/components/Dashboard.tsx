/**
 * Main dashboard component.
 */

import { useState, useEffect } from 'react';
import { useIcemakerState } from '../hooks/useIcemakerState';
import { useTemperature } from '../contexts/TemperatureContext';
import { fetchVersion, applyUpdate } from '../api/client';
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
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  // Check for updates on mount and every 60 seconds
  useEffect(() => {
    const checkForUpdates = async () => {
      try {
        const version = await fetchVersion();
        setUpdateAvailable(version.update_available);
      } catch {
        // Ignore errors - update check is not critical
      }
    };

    checkForUpdates();
    const interval = setInterval(checkForUpdates, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleUpdate = async () => {
    if (isUpdating) return;
    setIsUpdating(true);
    try {
      await applyUpdate();
      // Service will restart, page will lose connection
    } catch {
      setIsUpdating(false);
    }
  };

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
        {updateAvailable && (
          <button
            className="update-notice"
            onClick={handleUpdate}
            disabled={isUpdating}
            title="Click to pull updates and restart server"
          >
            {isUpdating ? 'Updating...' : 'Update available'}
          </button>
        )}
        <div className="header-actions">
          <button
            className="header-btn"
            onClick={toggleUnit}
            title="Toggle temperature unit"
          >
            °{unit}
          </button>
          <button
            className="header-btn settings-btn"
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
        shutdownRequested={status?.shutdown_requested ?? false}
        onRefresh={refresh}
      />
    </div>
  );
}
