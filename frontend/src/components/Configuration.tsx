/**
 * Configuration panel for icemaker settings.
 * Dynamically renders fields based on schema from backend.
 */

import { useEffect, useState } from 'react';
import {
  fetchConfig,
  fetchConfigSchema,
  fetchSimulatorStatus,
  resetConfig,
  resetSimulator,
  setSimulatorSpeed,
  updateConfig,
} from '../api/client';
import type { SimulatorStatus } from '../api/client';
import { useTemperature } from '../contexts/TemperatureContext';
import type { ConfigFieldSchema, ConfigSchemaResponse, IcemakerConfig } from '../types/icemaker';

interface ConfigFieldProps {
  field: ConfigFieldSchema;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  tempUnit?: string;
  convertTemp?: (f: number) => number;
}

function ConfigField({ field, value, onChange, disabled, tempUnit, convertTemp }: ConfigFieldProps) {
  const isTemp = field.unit === '°F';
  const displayValue = isTemp && convertTemp ? convertTemp(value) : value;
  const displayUnit = isTemp && tempUnit ? tempUnit : field.unit || '';

  // Use local state to allow intermediate input states like "-" or "-0"
  const [inputValue, setInputValue] = useState(displayValue.toString());

  // Sync with external value changes
  useEffect(() => {
    setInputValue((Math.round(displayValue * 10) / 10).toString());
  }, [displayValue]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    setInputValue(raw);

    // Only propagate valid numbers
    const parsed = parseFloat(raw);
    if (!isNaN(parsed)) {
      // Convert back to Fahrenheit if it's a temperature field
      if (isTemp && tempUnit === '°C') {
        onChange((parsed * 9) / 5 + 32);
      } else {
        onChange(parsed);
      }
    }
  };

  // Adjust min/max for Celsius if temperature field
  let min = field.min_value ?? 0;
  let max = field.max_value ?? 100;
  if (isTemp && tempUnit === '°C') {
    min = Math.round(((min - 32) * 5) / 9);
    max = Math.round(((max - 32) * 5) / 9);
  }

  return (
    <div className="config-field">
      <label className="config-label" title={field.description}>{field.name}</label>
      <div className="config-input-group">
        <input
          type="number"
          value={inputValue}
          min={min}
          max={max}
          step={field.step ?? 1}
          onChange={handleInputChange}
          disabled={disabled || field.readonly}
          className="config-input"
        />
        <span className="config-unit">{displayUnit}</span>
      </div>
    </div>
  );
}

interface BooleanFieldProps {
  field: ConfigFieldSchema;
  value: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}

function BooleanField({ field, value, onChange, disabled }: BooleanFieldProps) {
  return (
    <div className="config-toggle-field">
      <label className="config-label" title={field.description}>{field.name}</label>
      <button
        className={`toggle-btn ${value ? 'active' : ''}`}
        onClick={() => onChange(!value)}
        disabled={disabled || field.readonly}
      >
        {value ? 'Enabled' : 'Disabled'}
      </button>
    </div>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  chill: 'Prechill (CHILL)',
  ice: 'Ice Making (ICE)',
  harvest: 'Harvest (HEAT)',
  rechill: 'Rechill (CHILL)',
  idle: 'Bin Full (IDLE)',
  standby: 'Standby (STANDBY)',
  priming: 'Priming (POWER_ON)',
  system: 'System',
};

export function Configuration() {
  const [schema, setSchema] = useState<ConfigSchemaResponse | null>(null);
  const [config, setConfig] = useState<IcemakerConfig | null>(null);
  const [simStatus, setSimStatus] = useState<SimulatorStatus | null>(null);
  const [pendingChanges, setPendingChanges] = useState<Partial<IcemakerConfig>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
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
      const [schemaData, configData, simData] = await Promise.all([
        fetchConfigSchema(),
        fetchConfig(),
        fetchSimulatorStatus().catch(() => null),
      ]);
      setSchema(schemaData);
      setConfig(configData);
      setSimStatus(simData);
      setPendingChanges({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (key: string, value: number | boolean) => {
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

  const handleFactoryReset = async () => {
    if (!confirm('Reset all settings to factory defaults? This cannot be undone.')) {
      return;
    }

    try {
      setIsResetting(true);
      setError(null);
      const factoryConfig = await resetConfig();
      setConfig(factoryConfig);
      setPendingChanges({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to reset to factory defaults');
    } finally {
      setIsResetting(false);
    }
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

  const getValue = (key: string): number | boolean => {
    if (key in pendingChanges) {
      return pendingChanges[key as keyof IcemakerConfig] as number | boolean;
    }
    return config?.[key as keyof IcemakerConfig] as number | boolean ?? 0;
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

  // Group fields by category
  const fieldsByCategory: Record<string, ConfigFieldSchema[]> = {};
  schema?.fields.forEach((field) => {
    if (!fieldsByCategory[field.category]) {
      fieldsByCategory[field.category] = [];
    }
    fieldsByCategory[field.category].push(field);
  });

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

          {schema?.categories.map((category) => {
            const fields = fieldsByCategory[category];
            if (!fields || fields.length === 0) return null;

            // Separate boolean and numeric fields
            const boolFields = fields.filter((f) => f.type === 'bool');
            const numericFields = fields.filter((f) => f.type !== 'bool');

            return (
              <div key={category} className="config-section">
                <h4>{CATEGORY_LABELS[category] || category}</h4>

                {/* Render boolean fields first as toggles */}
                {boolFields.map((field) => (
                  <BooleanField
                    key={field.key}
                    field={field}
                    value={getValue(field.key) as boolean}
                    onChange={(v) => handleChange(field.key, v)}
                    disabled={isSaving}
                  />
                ))}

                {/* Render numeric fields in grid */}
                {numericFields.length > 0 && (
                  <div className="config-grid">
                    {numericFields.map((field) => (
                      <ConfigField
                        key={field.key}
                        field={field}
                        value={getValue(field.key) as number}
                        onChange={(v) => handleChange(field.key, v)}
                        disabled={isSaving}
                        tempUnit={field.unit === '°F' ? tempUnit : undefined}
                        convertTemp={field.unit === '°F' ? convertTemp : undefined}
                      />
                    ))}
                  </div>
                )}

                {/* Factory reset button in system section */}
                {category === 'system' && (
                  <button
                    className="btn btn-warning btn-block btn-sm"
                    onClick={handleFactoryReset}
                    disabled={isResetting || isSaving}
                    style={{ marginTop: '0.75rem' }}
                  >
                    {isResetting ? 'Resetting...' : 'Reset to Factory Defaults'}
                  </button>
                )}
              </div>
            );
          })}

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
