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

  // Format data for recharts - convert to display unit
  const chartData = data.map((reading, index) => ({
    index,
    plate: convertTemp(reading.plate_temp_f),
    bin: convertTemp(reading.bin_temp_f),
    time: new Date(reading.timestamp).toLocaleTimeString(),
  }));

  // Calculate Y-axis domain using converted temps
  const allTemps = data.flatMap((r) => [convertTemp(r.plate_temp_f), convertTemp(r.bin_temp_f)]);
  if (targetTemp !== null && targetTemp !== undefined) {
    allTemps.push(convertTemp(targetTemp));
  }
  const minTemp = Math.min(...allTemps, unit === 'C' ? -18 : 0) - 5;
  const maxTemp = Math.max(...allTemps, unit === 'C' ? 27 : 80) + 5;

  // Convert target temp for display
  const displayTargetTemp = targetTemp !== null && targetTemp !== undefined
    ? convertTemp(targetTemp)
    : null;

  return (
    <div className="temperature-chart">
      <h3>Temperature History</h3>
      <ResponsiveContainer width="100%" height={300}>
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
