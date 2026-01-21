/**
 * Display current icemaker state with visual indicator.
 */

import { useEffect, useState } from 'react';
import type { IcemakerState, IcemakerStatus } from '../types/icemaker';
import { useTemperature } from '../contexts/TemperatureContext';

interface StateDisplayProps {
  status: IcemakerStatus | null;
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

function calculateTimeInState(stateEnterTime: string): number {
  const enterTime = new Date(stateEnterTime).getTime();
  const now = Date.now();
  return Math.max(0, (now - enterTime) / 1000);
}

export function StateDisplay({ status }: StateDisplayProps) {
  const { formatTemp } = useTemperature();
  const [timeInState, setTimeInState] = useState(0);

  // Update time in state every second
  useEffect(() => {
    if (!status?.state_enter_time) return;

    // Calculate initial value
    setTimeInState(calculateTimeInState(status.state_enter_time));

    // Update every second
    const interval = setInterval(() => {
      setTimeInState(calculateTimeInState(status.state_enter_time));
    }, 1000);

    return () => clearInterval(interval);
  }, [status?.state_enter_time]);

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
