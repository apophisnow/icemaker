/**
 * Configuration panel for icemaker settings.
 */

import { useEffect, useState } from 'react';
import {
  fetchConfig,
  fetchSimulatorStatus,
  resetSimulator,
  setSimulatorSpeed,
  updateConfig,
} from '../api/client';
import type { SimulatorStatus } from '../api/client';
import { useTemperature } from '../contexts/TemperatureContext';
import type { IcemakerConfig } from '../types/icemaker';

interface ConfigFieldProps {
  label: string;
  value: number;
  unit: string;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

function ConfigField({ label, value, unit, min, max, step, onChange, disabled }: ConfigFieldProps) {
  return (
    <div className="config-field">
      <label className="config-label">{label}</label>
      <div className="config-input-group">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          disabled={disabled}
          className="config-input"
        />
        <span className="config-unit">{unit}</span>
      </div>
    </div>
  );
}

export function Configuration() {
  const [config, setConfig] = useState<IcemakerConfig | null>(null);
  const [simStatus, setSimStatus] = useState<SimulatorStatus | null>(null);
  const [pendingChanges, setPendingChanges] = useState<Partial<IcemakerConfig>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const { unit, convertTemp } = useTemperature();

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [configData, simData] = await Promise.all([
        fetchConfig(),
        fetchSimulatorStatus().catch(() => null),
      ]);
      setConfig(configData);
      setSimStatus(simData);
      setPendingChanges({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (key: keyof IcemakerConfig, value: number) => {
    setPendingChanges((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (Object.keys(pendingChanges).length === 0) return;

    try {
      setIsSaving(true);
      setError(null);
      const updated = await updateConfig(pendingChanges);
      setConfig(updated);
      setPendingChanges({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setPendingChanges({});
  };

  const handleSpeedChange = async (speed: number) => {
    try {
      const result = await setSimulatorSpeed(speed);
      setSimStatus((prev) =>
        prev ? { ...prev, speed_multiplier: result.speed_multiplier } : null
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set speed');
    }
  };

  const handleSimulatorReset = async () => {
    try {
      await resetSimulator();
      const simData = await fetchSimulatorStatus();
      setSimStatus(simData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to reset simulator');
    }
  };

  const getValue = (key: keyof IcemakerConfig): number => {
    if (key in pendingChanges) {
      return pendingChanges[key] as number;
    }
    return config?.[key] as number ?? 0;
  };

  // Convert temperature for display (config is stored in F)
  const getTempValue = (key: keyof IcemakerConfig): number => {
    const rawValue = getValue(key);
    return unit === 'C' ? convertTemp(rawValue) : rawValue;
  };

  // Convert temperature back to F for storage
  const handleTempChange = (key: keyof IcemakerConfig, displayValue: number) => {
    const storedValue = unit === 'C' ? (displayValue * 9) / 5 + 32 : displayValue;
    handleChange(key, storedValue);
  };

  const hasChanges = Object.keys(pendingChanges).length > 0;
  const tempUnit = `°${unit}`;

  if (isLoading) {
    return (
      <div className="configuration">
        <h3>Configuration</h3>
        <div className="config-loading">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="configuration">
      <div className="config-header" onClick={() => setIsExpanded(!isExpanded)}>
        <h3>Configuration</h3>
        <button className="config-toggle">
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {error && (
        <div className="config-error">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {isExpanded && (
        <>
          {simStatus?.enabled && (
            <div className="config-section">
              <h4>Simulator</h4>
              <div className="config-speed-control">
                <label className="config-label">Speed</label>
                <div className="speed-buttons">
                  {[1, 5, 10, 30, 60].map((speed) => (
                    <button
                      key={speed}
                      className={`speed-btn ${simStatus.speed_multiplier === speed ? 'active' : ''}`}
                      onClick={() => handleSpeedChange(speed)}
                    >
                      {speed}x
                    </button>
                  ))}
                </div>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleSimulatorReset}
                >
                  Reset Temps
                </button>
              </div>
            </div>
          )}

          <div className="config-section">
            <h4>Temperature Thresholds</h4>
            <div className="config-grid">
              <ConfigField
                label="Prechill Temp"
                value={Math.round(getTempValue('prechill_temp') * 10) / 10}
                unit={tempUnit}
                min={unit === 'C' ? -7 : 20}
                max={unit === 'C' ? 10 : 50}
                step={0.5}
                onChange={(v) => handleTempChange('prechill_temp', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Ice Target Temp"
                value={Math.round(getTempValue('ice_target_temp') * 10) / 10}
                unit={tempUnit}
                min={unit === 'C' ? -29 : -20}
                max={unit === 'C' ? -7 : 20}
                step={0.5}
                onChange={(v) => handleTempChange('ice_target_temp', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Harvest Threshold"
                value={Math.round(getTempValue('harvest_threshold') * 10) / 10}
                unit={tempUnit}
                min={unit === 'C' ? -1 : 30}
                max={unit === 'C' ? 16 : 60}
                step={0.5}
                onChange={(v) => handleTempChange('harvest_threshold', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Rechill Temp"
                value={Math.round(getTempValue('rechill_temp') * 10) / 10}
                unit={tempUnit}
                min={unit === 'C' ? -4 : 25}
                max={unit === 'C' ? 10 : 50}
                step={0.5}
                onChange={(v) => handleTempChange('rechill_temp', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Bin Full Threshold"
                value={Math.round(getTempValue('bin_full_threshold') * 10) / 10}
                unit={tempUnit}
                min={unit === 'C' ? -7 : 20}
                max={unit === 'C' ? 10 : 50}
                step={0.5}
                onChange={(v) => handleTempChange('bin_full_threshold', v)}
                disabled={isSaving}
              />
            </div>
          </div>

          <div className="config-section">
            <h4>Timeouts</h4>
            <div className="config-grid">
              <ConfigField
                label="Prechill Timeout"
                value={getValue('prechill_timeout')}
                unit="sec"
                min={30}
                max={600}
                step={10}
                onChange={(v) => handleChange('prechill_timeout', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Ice Timeout"
                value={getValue('ice_timeout')}
                unit="sec"
                min={300}
                max={3600}
                step={60}
                onChange={(v) => handleChange('ice_timeout', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Harvest Timeout"
                value={getValue('harvest_timeout')}
                unit="sec"
                min={60}
                max={600}
                step={10}
                onChange={(v) => handleChange('harvest_timeout', v)}
                disabled={isSaving}
              />
              <ConfigField
                label="Rechill Timeout"
                value={getValue('rechill_timeout')}
                unit="sec"
                min={60}
                max={600}
                step={10}
                onChange={(v) => handleChange('rechill_timeout', v)}
                disabled={isSaving}
              />
            </div>
          </div>

          <div className="config-section">
            <h4>System</h4>
            <div className="config-grid">
              <ConfigField
                label="Poll Interval"
                value={getValue('poll_interval')}
                unit="sec"
                min={1}
                max={30}
                step={0.5}
                onChange={(v) => handleChange('poll_interval', v)}
                disabled={isSaving}
              />
            </div>
            <div className="config-info">
              <span className="config-simulator-label">Simulator Mode:</span>
              <span className={`config-simulator-value ${config?.use_simulator ? 'enabled' : 'disabled'}`}>
                {config?.use_simulator ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>

          {hasChanges && (
            <div className="config-actions">
              <button
                className="btn btn-secondary"
                onClick={handleReset}
                disabled={isSaving}
              >
                Reset
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
