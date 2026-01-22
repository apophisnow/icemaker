/**
 * Display current icemaker state with visual indicator.
 */

import type { IcemakerState, IcemakerStatus } from '../types/icemaker';
import { useTemperature } from '../contexts/TemperatureContext';

interface StateDisplayProps {
  status: IcemakerStatus | null;
  /** Simulated time in state from latest temp update (for simulator mode) */
  simulatedTimeInState?: number;
}

const STATE_COLORS: Record<IcemakerState, string> = {
  OFF: '#374151',
  IDLE: '#6b7280',
  POWER_ON: '#f59e0b',
  CHILL: '#3b82f6',
  ICE: '#06b6d4',
  HEAT: '#ef4444',
  ERROR: '#dc2626',
  SHUTDOWN: '#1f2937',
};

const STATE_DESCRIPTIONS: Record<IcemakerState, string> = {
  OFF: 'System powered off',
  IDLE: 'Ready, waiting for start',
  POWER_ON: 'Priming water system',
  CHILL: 'Cooling plate',
  ICE: 'Making ice',
  HEAT: 'Harvesting ice',
  ERROR: 'Error occurred',
  SHUTDOWN: 'Shutting down',
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function StateDisplay({ status, simulatedTimeInState }: StateDisplayProps) {
  const { formatTemp } = useTemperature();

  // Use backend-provided time_in_state_seconds (which uses simulated time in simulator mode)
  // This updates with each WebSocket message from the backend
  const timeInState = simulatedTimeInState ?? status?.time_in_state_seconds ?? 0;

  if (!status) return null;

  const color = STATE_COLORS[status.state];
  const description = STATE_DESCRIPTIONS[status.state];

  return (
    <div className="state-display">
      <div
        className="current-state"
        style={{ backgroundColor: color }}
      >
        <span className="state-label">Current State</span>
        <span className="state-value">{status.state}</span>
        {status.chill_mode && (
          <span className="chill-mode">({status.chill_mode})</span>
        )}
      </div>

      <p className="state-description">{description}</p>

      <div className="state-details">
        <div className="detail-item">
          <span className="label">Cycle Count</span>
          <span className="value">{status.cycle_count}</span>
        </div>

        <div className="detail-item">
          <span className="label">Time in State</span>
          <span className="value">{formatTime(timeInState)}</span>
        </div>

        <div className="detail-item">
          <span className="label">Plate Temp</span>
          <span className="value temp">
            {formatTemp(status.plate_temp)}
          </span>
        </div>

        <div className="detail-item">
          <span className="label">Bin Temp</span>
          <span className="value temp">
            {formatTemp(status.bin_temp)}
          </span>
        </div>

        {status.target_temp !== null && (
          <div className="detail-item">
            <span className="label">Target Temp</span>
            <span className="value temp target">
              {formatTemp(status.target_temp)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
