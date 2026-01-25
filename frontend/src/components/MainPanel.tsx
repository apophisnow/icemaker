/**
 * Main panel combining state display and system diagram in a unified card.
 */

import type { IcemakerState, IcemakerStatus, RelayStates } from '../types/icemaker';
import { useTemperature } from '../contexts/TemperatureContext';

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
}

function Indicator({ label, active, type }: IndicatorProps) {
  const typeClass = active && type ? type : '';
  return (
    <div className={`indicator ${active ? 'active' : ''} ${typeClass}`}>
      <span className="indicator-dot" />
      <span className="indicator-label">{label}</span>
    </div>
  );
}

export function MainPanel({ status, relays, simulatedTimeInState }: MainPanelProps) {
  const { formatTemp } = useTemperature();

  const timeInState = simulatedTimeInState ?? status?.time_in_state_seconds ?? 0;

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
          {status.chill_mode && ` (${status.chill_mode})`}
        </span>
      </div>

      <div className="panel-body">
        {/* Status row */}
        <div className="status-row">
          <span className="status-description">{description}</span>
          <span className="status-time">{formatTime(timeInState)}</span>
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
              <div className="group-label">Refrigeration</div>
              <div className="component-grid">
                <Indicator label="C1" active={relays.compressor_1} type="cool" />
                <Indicator label="C2" active={relays.compressor_2} type="cool" />
                <Indicator label="Fan" active={relays.condenser_fan} />
                <Indicator label="Hot" active={relays.hot_gas_solenoid} type="heat" />
              </div>
            </div>

            <div className="component-group">
              <div className="group-label">Water/Ice</div>
              <div className="component-grid">
                <Indicator label="Valve" active={relays.water_valve} type="water" />
                <Indicator label="Pump" active={relays.recirculating_pump} type="water" />
                <Indicator label="Cut" active={relays.ice_cutter} />
                <Indicator label="LED" active={relays.LED} />
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
