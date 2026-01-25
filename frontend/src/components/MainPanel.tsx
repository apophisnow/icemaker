/**
 * Main panel combining state display and system diagram in a unified card.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { IcemakerState, IcemakerStatus, RelayStates } from '../types/icemaker';
import { useTemperature } from '../contexts/TemperatureContext';
import { setRelay } from '../api/client';

interface MainPanelProps {
  status: IcemakerStatus | null;
  relays: RelayStates | null;
  simulatedTimeInState?: number;
}

const STATE_DESCRIPTIONS: Record<IcemakerState, string> = {
  OFF: 'System powered off',
  STANDBY: 'Ready to start',
  IDLE: 'Bin full, waiting',
  POWER_ON: 'Priming water',
  CHILL: 'Cooling plate',
  ICE: 'Making ice',
  HEAT: 'Harvesting ice',
  ERROR: 'Error occurred',
  SHUTDOWN: 'Shutting down',
  DIAGNOSTIC: 'Manual control',
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function getPlateState(relays: RelayStates): string {
  if (relays.hot_gas_solenoid) return 'heating';
  if (relays.compressor_1 || relays.compressor_2) return 'cooling';
  return 'idle';
}

interface IndicatorProps {
  label: string;
  active: boolean;
  type?: 'cool' | 'heat' | 'water';
  relayName?: string;
  isDiagnostic?: boolean;
  onToggle?: (relayName: string, newState: boolean) => void;
}

function Indicator({ label, active, type, relayName, isDiagnostic, onToggle }: IndicatorProps) {
  const typeClass = active && type ? type : '';
  const isClickable = isDiagnostic && relayName && onToggle;

  const handleClick = () => {
    if (isClickable) {
      onToggle(relayName, !active);
    }
  };

  return (
    <div
      className={`indicator ${active ? 'active' : ''} ${typeClass} ${isClickable ? 'clickable' : ''}`}
      onClick={handleClick}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={isClickable ? (e) => e.key === 'Enter' && handleClick() : undefined}
    >
      <span className="indicator-dot" />
      <span className="indicator-label">{label}</span>
    </div>
  );
}

export function MainPanel({ status, relays, simulatedTimeInState }: MainPanelProps) {
  const { formatTemp } = useTemperature();
  const isDiagnostic = status?.state === 'DIAGNOSTIC';

  // Handle relay toggle in diagnostic mode
  const handleRelayToggle = useCallback(async (relayName: string, newState: boolean) => {
    try {
      await setRelay(relayName, newState);
    } catch (error) {
      console.error('Failed to toggle relay:', error);
    }
  }, []);

  // Local timer for smooth time display updates
  const backendTime = simulatedTimeInState ?? status?.time_in_state_seconds ?? 0;
  const [displayTime, setDisplayTime] = useState(backendTime);
  const lastUpdateRef = useRef<number>(Date.now());
  const lastBackendTimeRef = useRef<number>(backendTime);

  // Sync with backend time when it changes
  useEffect(() => {
    if (backendTime !== lastBackendTimeRef.current) {
      lastBackendTimeRef.current = backendTime;
      lastUpdateRef.current = Date.now();
      setDisplayTime(backendTime);
    }
  }, [backendTime]);

  // Update display every second
  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = (Date.now() - lastUpdateRef.current) / 1000;
      setDisplayTime(lastBackendTimeRef.current + elapsed);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!status) {
    return (
      <div className="main-panel">
        <div className="panel-header">
          <span>Icemaker</span>
          <span className="state-badge">—</span>
        </div>
        <p className="loading">Loading...</p>
      </div>
    );
  }

  const description = STATE_DESCRIPTIONS[status.state];
  const plateState = relays ? getPlateState(relays) : 'idle';

  return (
    <div className="main-panel">
      {/* Header with state badge */}
      <div className="panel-header">
        <span>Icemaker</span>
        <span className={`state-badge ${status.state.toLowerCase()}`}>
          {status.state}
          {((status.state === 'CHILL' && status.chill_mode) || status.shutdown_requested) && ' ('}
          {status.state === 'CHILL' && status.chill_mode}
          {status.state === 'CHILL' && status.chill_mode && status.shutdown_requested && ', '}
          {status.shutdown_requested && 'shutting down'}
          {((status.state === 'CHILL' && status.chill_mode) || status.shutdown_requested) && ')'}
        </span>
      </div>

      <div className="panel-body">
        {/* Status row */}
        <div className="status-row">
          <span className="status-description">{description}</span>
          <span className="status-time">{formatTime(displayTime)}</span>
        </div>

        {/* Cycle counts */}
        <div className="stats-row">
          <div className="stat-item">
            <span className="stat-label">Session</span>
            <span className="stat-value">{status.session_cycle_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Lifetime</span>
            <span className="stat-value">{status.cycle_count}</span>
          </div>
        </div>

        {/* Temperature display */}
        <div className="temp-row">
          <div className={`temp-box ${plateState}`}>
            <span className="temp-label">Plate</span>
            <span className="temp-value">{formatTemp(status.plate_temp)}</span>
          </div>
          {status.water_temp != null && (
            <div className="temp-box water">
              <span className="temp-label">Water</span>
              <span className="temp-value">{formatTemp(status.water_temp)}</span>
            </div>
          )}
          <div className="temp-box">
            <span className="temp-label">Bin</span>
            <span className="temp-value">{formatTemp(status.bin_temp)}</span>
          </div>
          {status.target_temp !== null && (
            <div className="temp-box target">
              <span className="temp-label">Target</span>
              <span className="temp-value">{formatTemp(status.target_temp)}</span>
            </div>
          )}
        </div>

        {/* Relay indicators */}
        {relays && (
          <>
            <div className="component-group">
              <div className="group-label">Refrigeration{isDiagnostic && ' (click to toggle)'}</div>
              <div className="component-grid">
                <Indicator label="C1" active={relays.compressor_1} type="cool" relayName="compressor_1" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
                <Indicator label="C2" active={relays.compressor_2} type="cool" relayName="compressor_2" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
                <Indicator label="Fan" active={relays.condenser_fan} relayName="condenser_fan" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
                <Indicator label="Hot" active={relays.hot_gas_solenoid} type="heat" relayName="hot_gas_solenoid" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
              </div>
            </div>

            <div className="component-group">
              <div className="group-label">Water/Ice{isDiagnostic && ' (click to toggle)'}</div>
              <div className="component-grid">
                <Indicator label="Valve" active={relays.water_valve} type="water" relayName="water_valve" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
                <Indicator label="Pump" active={relays.recirculating_pump} type="water" relayName="recirculating_pump" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
                <Indicator label="Cut" active={relays.ice_cutter} relayName="ice_cutter" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
                <Indicator label="LED" active={relays.LED} relayName="LED" isDiagnostic={isDiagnostic} onToggle={handleRelayToggle} />
              </div>
            </div>

            {/* Visual representation */}
            <div className="visual-row">
              <div className={`plate-icon-compact ${plateState}`}>
                {plateState === 'heating' ? '🔥' : '❄️'}
              </div>
              <div className={`flow-arrow ${relays.recirculating_pump ? 'active' : ''}`}>
                {relays.hot_gas_solenoid ? '↓' : '↑'}
              </div>
              <div className="bin-icon-compact">🧊</div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
