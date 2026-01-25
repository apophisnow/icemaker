/**
 * Real-time temperature chart using recharts.
 */

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TemperatureReading } from '../types/icemaker';
import { useTemperature } from '../contexts/TemperatureContext';

interface TemperatureChartProps {
  data: TemperatureReading[];
  targetTemp?: number | null;
}

/**
 * Format simulated time as human-readable elapsed time.
 */
function formatSimulatedTime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.floor(seconds)}s`;
  }
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

/**
 * Custom label for the target reference line.
 * Renders text positioned above the line so it doesn't overlap.
 */
function TargetLabel({ viewBox, value }: { viewBox?: { x: number; y: number; width: number }; value: string }) {
  if (!viewBox) return null;
  const { x, y, width } = viewBox;
  // Position label on the right side of the chart, above the line
  const labelX = x + width - 10;
  return (
    <text
      x={labelX}
      y={y - 6}
      fill="#f59e0b"
      fontSize={12}
      textAnchor="end"
    >
      {value}
    </text>
  );
}

export function TemperatureChart({ data, targetTemp }: TemperatureChartProps) {
  const { convertTemp, unit } = useTemperature();

  // Check if we have simulated time data (simulator mode)
  const hasSimulatedTime = data.length > 0 && data[0].simulated_time_seconds !== undefined;

  // Format data for recharts - convert to display unit
  const chartData = data.map((reading, index) => ({
    index,
    plate: convertTemp(reading.plate_temp_f),
    bin: convertTemp(reading.bin_temp_f),
    time: hasSimulatedTime && reading.simulated_time_seconds !== undefined
      ? formatSimulatedTime(reading.simulated_time_seconds)
      : new Date(reading.timestamp).toLocaleTimeString(),
  }));

  // Calculate Y-axis domain centered on freezing (32°F / 0°C)
  const freezingPoint = unit === 'C' ? 0 : 32;
  const allTemps = data.flatMap((r) => [convertTemp(r.plate_temp_f), convertTemp(r.bin_temp_f)]);
  if (targetTemp !== null && targetTemp !== undefined) {
    allTemps.push(convertTemp(targetTemp));
  }
  // Find max distance from freezing point to ensure all data is visible
  const maxDistanceFromFreezing = Math.max(
    ...allTemps.map(t => Math.abs(t - freezingPoint)),
    unit === 'C' ? 25 : 45  // Minimum range: ±25°C or ±45°F
  );
  const minTemp = freezingPoint - maxDistanceFromFreezing - 5;
  const maxTemp = freezingPoint + maxDistanceFromFreezing + 5;

  // Convert target temp for display
  const displayTargetTemp = targetTemp !== null && targetTemp !== undefined
    ? convertTemp(targetTemp)
    : null;

  return (
    <div className="temperature-chart">
      <h3>Temperature History {hasSimulatedTime && <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>(Simulated Time)</span>}</h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="time"
            stroke="#9ca3af"
            tick={{ fill: '#9ca3af', fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minTemp, maxTemp]}
            stroke="#9ca3af"
            tick={{ fill: '#9ca3af' }}
            tickFormatter={(value) => `${value.toFixed(0)}°${unit}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '4px',
            }}
            labelStyle={{ color: '#9ca3af' }}
            formatter={(value: number) => [`${value.toFixed(1)}°${unit}`]}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="plate"
            name="Plate"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="bin"
            name="Ice Bin"
            stroke="#10b981"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          {/* Freezing point reference line */}
          <ReferenceLine
            y={freezingPoint}
            stroke="#60a5fa"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          {displayTargetTemp !== null && (
            <ReferenceLine
              y={displayTargetTemp}
              stroke="#f59e0b"
              strokeDasharray="5 5"
              label={<TargetLabel value={`Target: ${displayTargetTemp.toFixed(1)}°${unit}`} />}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
