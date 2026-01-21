/**
 * Control buttons for icemaker operation.
 */

import { useState } from 'react';
import { emergencyStop, powerOff, powerOn, startCycle, stopCycle } from '../api/client';
import type { IcemakerState } from '../types/icemaker';

interface ControlsProps {
  currentState: IcemakerState | undefined;
  onError: (message: string) => void;
  onRefresh: () => void;
}

export function Controls({ currentState, onError, onRefresh }: ControlsProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handlePowerOn = async () => {
    setIsLoading(true);
    try {
      await powerOn();
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to power on');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePowerOff = async () => {
    setIsLoading(true);
    try {
      await powerOff();
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to power off');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartCycle = async () => {
    setIsLoading(true);
    try {
      await startCycle();
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to start cycle');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopCycle = async () => {
    setIsLoading(true);
    try {
      await stopCycle();
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to stop cycle');
    } finally {
      setIsLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    setIsLoading(true);
    try {
      await emergencyStop();
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to execute emergency stop');
    } finally {
      setIsLoading(false);
    }
  };

  const isOff = currentState === 'OFF';
  const isIdle = currentState === 'IDLE';
  const isPoweringOn = currentState === 'POWER_ON';
  const isInCycle = currentState && ['CHILL', 'ICE', 'HEAT'].includes(currentState);
  const isError = currentState === 'ERROR';

  const canPowerOn = isOff;
  const canPowerOff = isIdle || isError;
  const canStart = isIdle;
  const canStop = isInCycle;

  return (
    <div className="controls">
      <h3>Controls</h3>
      <div className="control-buttons">
        {/* Power On/Off toggle */}
        {isOff ? (
          <button
            className="btn btn-success"
            onClick={handlePowerOn}
            disabled={!canPowerOn || isLoading}
          >
            {isLoading ? 'Powering On...' : 'Power On'}
          </button>
        ) : (
          <button
            className="btn btn-secondary"
            onClick={handlePowerOff}
            disabled={!canPowerOff || isLoading}
          >
            Power Off
          </button>
        )}

        {/* Start/Stop cycle toggle */}
        {isInCycle ? (
          <button
            className="btn btn-warning"
            onClick={handleStopCycle}
            disabled={!canStop || isLoading}
          >
            Stop Cycle
          </button>
        ) : (
          <button
            className="btn btn-primary"
            onClick={handleStartCycle}
            disabled={!canStart || isLoading}
          >
            {isLoading ? 'Starting...' : 'Start Cycle'}
          </button>
        )}

        <button
          className="btn btn-danger"
          onClick={handleEmergencyStop}
          disabled={isLoading}
        >
          EMERGENCY STOP
        </button>
      </div>

      <div className="control-info">
        <p>
          {isOff && 'System is off. Press Power On to initialize.'}
          {isPoweringOn && 'Powering on... Water system priming in progress.'}
          {isIdle && 'Ready. Press Start Cycle to begin making ice.'}
          {isInCycle && 'Cycle in progress. Press Stop to return to idle.'}
          {isError && 'Error state. Use Emergency Stop to reset.'}
        </p>
      </div>
    </div>
  );
}
