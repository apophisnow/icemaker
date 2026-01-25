/**
 * Settings panel containing controls and configuration.
 * Slides in from the right when opened.
 */

import { useState } from 'react';
import { emergencyStop, powerOff, powerOn, startCycle, stopCycle } from '../api/client';
import type { IcemakerState } from '../types/icemaker';
import { Configuration } from './Configuration';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  currentState: IcemakerState | undefined;
  onRefresh: () => void;
}

export function SettingsPanel({ isOpen, onClose, currentState, onRefresh }: SettingsPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const canPowerOn = isOff;
  const canPowerOff = isStandby || isError;
  const canStart = isStandby || isIdle;
  const canStop = isInCycle || isIdle;

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
              {isOff ? (
                <button
                  className="btn btn-success btn-block"
                  onClick={() => handleAction(powerOn, 'Failed to power on')}
                  disabled={!canPowerOn || isLoading}
                >
                  {isLoading ? 'Powering On...' : 'Power On'}
                </button>
              ) : (
                <button
                  className="btn btn-secondary btn-block"
                  onClick={() => handleAction(powerOff, 'Failed to power off')}
                  disabled={!canPowerOff || isLoading}
                >
                  Power Off
                </button>
              )}

              {isInCycle ? (
                <button
                  className="btn btn-warning btn-block"
                  onClick={() => handleAction(stopCycle, 'Failed to stop cycle')}
                  disabled={!canStop || isLoading}
                >
                  Stop Cycle
                </button>
              ) : (
                <button
                  className="btn btn-primary btn-block"
                  onClick={() => handleAction(startCycle, 'Failed to start cycle')}
                  disabled={!canStart || isLoading}
                >
                  {isLoading ? 'Starting...' : 'Start Cycle'}
                </button>
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
              {isOff && 'System is off. Power on to initialize.'}
              {currentState === 'POWER_ON' && 'Priming water system...'}
              {isStandby && 'Ready. Start a cycle to begin making ice.'}
              {isIdle && 'Paused (bin full). Auto-restarts when bin empties.'}
              {isInCycle && 'Cycle in progress.'}
              {isError && 'Error state. Use Emergency Stop to reset.'}
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
