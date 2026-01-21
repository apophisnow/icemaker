/**
 * SCADA-style system diagram showing icemaker components and their states.
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
      <div className="system-diagram">
        <h3>System Diagram</h3>
        <p className="loading">Loading...</p>
      </div>
    );
  }

  return (
    <div className="system-diagram">
      <h3>System Diagram</h3>
      <div className="diagram-container">
        {/* Refrigeration System */}
        <div className="diagram-section refrigeration">
          <div className="section-label">Refrigeration</div>

          {/* Compressors */}
          <div className="component-row">
            <DiagramComponent
              name="Compressor 1"
              icon="⚙️"
              isActive={relays.compressor_1}
              type="compressor"
            />
            <DiagramComponent
              name="Compressor 2"
              icon="⚙️"
              isActive={relays.compressor_2}
              type="compressor"
            />
          </div>

          {/* Condenser */}
          <div className="component-row">
            <DiagramComponent
              name="Condenser Fan"
              icon="🌀"
              isActive={relays.condenser_fan}
              type="fan"
            />
            <DiagramComponent
              name="Hot Gas Valve"
              icon="🔥"
              isActive={relays.hot_gas_solenoid}
              type="heating"
            />
          </div>
        </div>

        {/* Flow lines connecting sections */}
        <div className="flow-indicator">
          <div className={`flow-line ${relays.compressor_1 || relays.compressor_2 ? 'active' : ''}`}>
            {relays.hot_gas_solenoid ? '→ HOT →' : '→ COLD →'}
          </div>
        </div>

        {/* Ice Making Section */}
        <div className="diagram-section ice-making">
          <div className="section-label">Ice Making</div>

          {/* Water System Controls */}
          <div className="component-row">
            <DiagramComponent
              name="Water Valve"
              icon="💧"
              isActive={relays.water_valve}
              type="water"
            />
            <DiagramComponent
              name="Recirc Pump"
              icon="🔄"
              isActive={relays.recirculating_pump}
              type="pump"
            />
          </div>

          {/* Water Reservoir - now above the plate */}
          <div className="reservoir">
            <div className={`reservoir-visual ${relays.water_valve ? 'filling' : ''}`}>
              <div className="water-level" />
              <span className="reservoir-label">Reservoir</span>
              {waterTemp != null && (
                <span className="reservoir-temp">{formatTemp(waterTemp)}</span>
              )}
            </div>
          </div>

          {/* Water flow animation from reservoir to plate */}
          <div className={`water-flow-indicator ${relays.recirculating_pump ? 'flowing' : ''}`}>
            <div className="water-droplets">
              <span className="droplet">💧</span>
              <span className="droplet">💧</span>
              <span className="droplet">💧</span>
            </div>
          </div>

          {/* Evaporator Plate with ice forming */}
          <div className="evaporator-assembly">
            <div className={`plate-visual ${getPlateState(relays)}`}>
              <div className={`ice-formation ${state === 'ICE' ? 'forming' : ''} ${state === 'HEAT' ? 'releasing' : ''}`}>
                <span className="ice-block">🧊</span>
              </div>
              <span className="plate-icon">❄️</span>
              <span className="plate-label">Evaporator Plate</span>
              {plateTemp !== null && (
                <span className="plate-temp">{formatTemp(plateTemp)}</span>
              )}
            </div>

            {/* Wire cutter grid below plate */}
            <div className={`wire-cutter-grid ${relays.ice_cutter ? 'active' : ''}`}>
              <div className="wire-row">
                <div className="wire" />
                <div className="wire" />
                <div className="wire" />
                <div className="wire" />
                <div className="wire" />
              </div>
              <span className="cutter-label">Wire Cutter</span>
            </div>
          </div>
        </div>

        {/* Ice falling animation */}
        <div className={`ice-drop-zone ${state === 'HEAT' ? 'dropping' : ''}`}>
          <div className="falling-ice">
            <span className="ice-cube">🧊</span>
            <span className="ice-cube">🧊</span>
            <span className="ice-cube">🧊</span>
          </div>
        </div>

        {/* Ice Bin Section */}
        <div className="diagram-section ice-bin">
          <div className="section-label">Ice Storage</div>

          {/* Ice Bin */}
          <div className="ice-bin-visual">
            <div className="bin-container">
              <div className="ice-pile">
                <span className="bin-ice">🧊</span>
                <span className="bin-ice">🧊</span>
                <span className="bin-ice">🧊</span>
              </div>
              <span className="bin-label">Ice Bin</span>
              {binTemp !== null && (
                <span className="bin-temp">{formatTemp(binTemp)}</span>
              )}
            </div>
          </div>
        </div>

        {/* Status Indicator */}
        <div className="diagram-section status">
          <div className="section-label">Status</div>
          <DiagramComponent
            name="Status LED"
            icon="💡"
            isActive={relays.LED}
            type="led"
          />
          <div className="current-mode">
            Mode: <strong>{state || 'Unknown'}</strong>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="diagram-legend">
        <div className="legend-item">
          <span className="legend-indicator active" />
          <span>Active</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator inactive" />
          <span>Inactive</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator heating" />
          <span>Heating</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator cooling" />
          <span>Cooling</span>
        </div>
      </div>
    </div>
  );
}

interface DiagramComponentProps {
  name: string;
  icon: string;
  isActive: boolean;
  type: 'compressor' | 'fan' | 'heating' | 'water' | 'pump' | 'cutter' | 'led';
}

function DiagramComponent({ name, icon, isActive, type }: DiagramComponentProps) {
  return (
    <div className={`diagram-component ${type} ${isActive ? 'active' : 'inactive'}`}>
      <div className="component-icon">{icon}</div>
      <div className="component-info">
        <span className="component-name">{name}</span>
        <span className={`component-status ${isActive ? 'on' : 'off'}`}>
          {isActive ? 'ON' : 'OFF'}
        </span>
      </div>
      {isActive && <div className="activity-pulse" />}
    </div>
  );
}

function getPlateState(relays: RelayStates): string {
  if (relays.hot_gas_solenoid) return 'heating';
  if (relays.compressor_1 || relays.compressor_2) return 'cooling';
  return 'idle';
}
