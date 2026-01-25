/**
 * Compact SCADA-style system diagram showing icemaker components and their states.
 * Designed to fit in ~25% of display width.
 */

import type { RelayStates, IcemakerState } from '../types/icemaker';
import { useTemperature } from '../contexts/TemperatureContext';

interface SystemDiagramProps {
  relays: RelayStates | null;
  plateTemp: number | null;
  binTemp: number | null;
  waterTemp?: number | null;
  state: IcemakerState | null;
}

export function SystemDiagram({
  relays,
  plateTemp,
  binTemp,
  waterTemp,
  state,
}: SystemDiagramProps) {
  const { formatTemp } = useTemperature();

  if (!relays) {
    return (
      <div className="system-diagram-compact">
        <div className="diagram-header">System</div>
        <p className="loading">Loading...</p>
      </div>
    );
  }

  const plateState = getPlateState(relays);

  return (
    <div className="system-diagram-compact">
      <div className="diagram-header">
        <span>System</span>
        <span className={`state-badge ${state?.toLowerCase() || ''}`}>{state || '—'}</span>
      </div>

      <div className="diagram-body">
        {/* Refrigeration row */}
        <div className="component-group">
          <div className="group-label">Refrigeration</div>
          <div className="component-grid">
            <Indicator label="C1" active={relays.compressor_1} type="cool" />
            <Indicator label="C2" active={relays.compressor_2} type="cool" />
            <Indicator label="Fan" active={relays.condenser_fan} />
            <Indicator label="Hot" active={relays.hot_gas_solenoid} type="heat" />
          </div>
        </div>

        {/* Water/Ice row */}
        <div className="component-group">
          <div className="group-label">Water/Ice</div>
          <div className="component-grid">
            <Indicator label="Valve" active={relays.water_valve} type="water" />
            <Indicator label="Pump" active={relays.recirculating_pump} type="water" />
            <Indicator label="Cut" active={relays.ice_cutter} />
            <Indicator label="LED" active={relays.LED} />
          </div>
        </div>

        {/* Temperature display */}
        <div className="temp-row">
          <div className={`temp-box ${plateState}`}>
            <span className="temp-label">Plate</span>
            <span className="temp-value">{plateTemp !== null ? formatTemp(plateTemp) : '—'}</span>
          </div>
          {waterTemp != null && (
            <div className="temp-box water">
              <span className="temp-label">Water</span>
              <span className="temp-value">{formatTemp(waterTemp)}</span>
            </div>
          )}
          <div className="temp-box">
            <span className="temp-label">Bin</span>
            <span className="temp-value">{binTemp !== null ? formatTemp(binTemp) : '—'}</span>
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
      </div>
    </div>
  );
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

function getPlateState(relays: RelayStates): string {
  if (relays.hot_gas_solenoid) return 'heating';
  if (relays.compressor_1 || relays.compressor_2) return 'cooling';
  return 'idle';
}
