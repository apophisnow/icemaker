/**
 * Settings panel containing controls and configuration.
 * Slides in from the right when opened.
 */

import { useState, useCallback, useEffect } from 'react';
import { emergencyStop, startIcemaking, stopIcemaking, enterDiagnostic, exitDiagnostic } from '../api/client';
import type { IcemakerState, TemperatureReading } from '../types/icemaker';
import { getRetentionHours, setRetentionHours } from '../hooks/useIcemakerState';
import { Configuration } from './Configuration';

const STORAGE_KEY = 'icemaker_temp_history';
const RETENTION_OPTIONS = [1, 6, 12, 24, 48, 72];

function downloadTemperatureCSV() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return 0;

  const readings: TemperatureReading[] = JSON.parse(stored);
  if (readings.length === 0) return 0;

  const headers = [
    'timestamp',
    'simulated_time_seconds',
    'plate_temp_f',
    'bin_temp_f',
    'water_temp_f',
  ];

  const rows = readings.map((r) =>
    [
      r.timestamp,
      r.simulated_time_seconds?.toFixed(2) ?? '',
      r.plate_temp_f.toFixed(2),
      r.bin_temp_f.toFixed(2),
      r.water_temp_f?.toFixed(2) ?? '',
    ].join(',')
  );

  const csvContent = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  const dateStr = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-');
  link.setAttribute('href', url);
  link.setAttribute('download', `icemaker-temps-${dateStr}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  return readings.length;
}

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  currentState: IcemakerState | undefined;
  shutdownRequested: boolean;
  onRefresh: () => void;
}

export function SettingsPanel({ isOpen, onClose, currentState, shutdownRequested, onRefresh }: SettingsPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retentionHours, setRetentionHoursState] = useState(getRetentionHours);

  useEffect(() => {
    if (isOpen) {
      setRetentionHoursState(getRetentionHours());
    }
  }, [isOpen]);

  const handleRetentionChange = useCallback((hours: number) => {
    setRetentionHours(hours);
    setRetentionHoursState(hours);
  }, []);

  const handleDownloadCSV = useCallback(() => {
    const count = downloadTemperatureCSV();
    if (count === 0) {
      setError('No temperature data to export');
    }
  }, []);

  const handleAction = async (action: () => Promise<unknown>, errorMsg: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await action();
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const isOff = currentState === 'OFF';
  const isStandby = currentState === 'STANDBY';
  const isIdle = currentState === 'IDLE';
  const isInCycle = currentState && ['CHILL', 'ICE', 'HEAT'].includes(currentState);
  const isError = currentState === 'ERROR';
  const isDiagnostic = currentState === 'DIAGNOSTIC';

  const canStart = isOff || isStandby || isIdle;
  const canStop = (isStandby || isIdle || isError || isInCycle) && !shutdownRequested;
  const canEnterDiagnostic = isOff;

  return (
    <>
      {/* Backdrop */}
      <div
        className={`settings-backdrop ${isOpen ? 'open' : ''}`}
        onClick={onClose}
      />

      {/* Panel */}
      <div className={`settings-panel ${isOpen ? 'open' : ''}`}>
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="settings-content">
          {/* Controls Section */}
          <div className="settings-section">
            <h3>Controls</h3>

            {error && (
              <div className="settings-error">
                {error}
                <button onClick={() => setError(null)}>×</button>
              </div>
            )}

            <div className="control-buttons">
              {isDiagnostic ? (
                <button
                  className="btn btn-warning btn-block"
                  onClick={() => handleAction(exitDiagnostic, 'Failed to exit diagnostic mode')}
                  disabled={isLoading}
                >
                  Exit Diagnostic Mode
                </button>
              ) : (
                <>
                  {canStart && (
                    <button
                      className="btn btn-success btn-block"
                      onClick={() => handleAction(startIcemaking, 'Failed to start ice making')}
                      disabled={isLoading}
                    >
                      {isLoading ? 'Starting...' : 'Start Icemaking'}
                    </button>
                  )}
                  {canStop && (
                    <button
                      className="btn btn-secondary btn-block"
                      onClick={() => handleAction(stopIcemaking, 'Failed to stop ice making')}
                      disabled={isLoading}
                    >
                      Stop Icemaking
                    </button>
                  )}
                  {isOff && (
                    <button
                      className="btn btn-secondary btn-block"
                      onClick={() => handleAction(enterDiagnostic, 'Failed to enter diagnostic mode')}
                      disabled={!canEnterDiagnostic || isLoading}
                    >
                      Diagnostic Mode
                    </button>
                  )}
                </>
              )}

              <button
                className="btn btn-danger btn-block"
                onClick={() => handleAction(emergencyStop, 'Failed to execute emergency stop')}
                disabled={isLoading}
              >
                EMERGENCY STOP
              </button>
            </div>

            <p className="control-hint">
              {isOff && 'System is off. Start icemaking or enter diagnostic mode.'}
              {currentState === 'POWER_ON' && 'Priming water system...'}
              {isStandby && 'Ready to make ice.'}
              {isIdle && 'Paused (bin full). Auto-restarts when bin empties.'}
              {isInCycle && 'Cycle in progress.'}
              {isError && 'Error state. Use Emergency Stop to reset.'}
              {isDiagnostic && 'Diagnostic mode. Click relay indicators to toggle manually.'}
            </p>
          </div>

          {/* Data Section */}
          <div className="settings-section">
            <h3>Data</h3>

            <div className="config-field" style={{ marginBottom: '0.75rem' }}>
              <span className="config-label">Data Retention</span>
              <div className="speed-buttons">
                {RETENTION_OPTIONS.map((hours) => (
                  <button
                    key={hours}
                    className={`speed-btn ${retentionHours === hours ? 'active' : ''}`}
                    onClick={() => handleRetentionChange(hours)}
                  >
                    {hours}h
                  </button>
                ))}
              </div>
            </div>

            <button
              className="btn btn-secondary btn-block"
              onClick={handleDownloadCSV}
            >
              Download Temperature CSV
            </button>
            <p className="control-hint">
              Exports temperature history from browser storage (up to {retentionHours} hours).
            </p>
          </div>

          {/* Configuration Section */}
          <div className="settings-section">
            <Configuration />
          </div>
        </div>
      </div>
    </>
  );
}
