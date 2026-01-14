/**
 * Control buttons for icemaker operation.
 */

import { useState } from 'react';
import { emergencyStop, startCycle, stopCycle } from '../api/client';
import type { IcemakerState } from '../types/icemaker';

interface ControlsProps {
  currentState: IcemakerState | undefined;
  onError: (message: string) => void;
  onRefresh: () => void;
}

export function Controls({ currentState, onError, onRefresh }: ControlsProps) {
  const [isLoading, setIsLoading] = useState(false);

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

  const canStart = currentState === 'IDLE';
  const canStop = currentState && !['IDLE', 'ERROR', 'SHUTDOWN'].includes(currentState);

  return (
    <div className="controls">
      <h3>Controls</h3>
      <div className="control-buttons">
        <button
          className="btn btn-primary"
          onClick={handleStartCycle}
          disabled={!canStart || isLoading}
        >
          {isLoading ? 'Starting...' : 'Start Cycle'}
        </button>

        <button
          className="btn btn-secondary"
          onClick={handleStopCycle}
          disabled={!canStop || isLoading}
        >
          Stop Cycle
        </button>

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
          {canStart && 'Ready to start a new ice-making cycle.'}
          {canStop && 'Cycle in progress. Stop to return to IDLE.'}
          {currentState === 'ERROR' && 'Error state. Use emergency stop to reset.'}
        </p>
      </div>
    </div>
  );
}
