/**
 * Context for temperature unit preference (Celsius/Fahrenheit).
 */

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type TemperatureUnit = 'C' | 'F';

interface TemperatureContextValue {
  unit: TemperatureUnit;
  setUnit: (unit: TemperatureUnit) => void;
  toggleUnit: () => void;
  formatTemp: (tempF: number) => string;
  convertTemp: (tempF: number) => number;
}

const TemperatureContext = createContext<TemperatureContextValue | null>(null);

const STORAGE_KEY = 'icemaker-temp-unit';

function fahrenheitToCelsius(tempF: number): number {
  return (tempF - 32) * 5 / 9;
}

interface TemperatureProviderProps {
  children: ReactNode;
}

export function TemperatureProvider({ children }: TemperatureProviderProps) {
  const [unit, setUnitState] = useState<TemperatureUnit>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return (stored === 'F' || stored === 'C') ? stored : 'C';
  });

  const setUnit = useCallback((newUnit: TemperatureUnit) => {
    setUnitState(newUnit);
    localStorage.setItem(STORAGE_KEY, newUnit);
  }, []);

  const toggleUnit = useCallback(() => {
    setUnit(unit === 'C' ? 'F' : 'C');
  }, [unit, setUnit]);

  const convertTemp = useCallback((tempF: number): number => {
    if (unit === 'F') return tempF;
    return fahrenheitToCelsius(tempF);
  }, [unit]);

  const formatTemp = useCallback((tempF: number): string => {
    const converted = convertTemp(tempF);
    return `${converted.toFixed(1)}°${unit}`;
  }, [unit, convertTemp]);

  return (
    <TemperatureContext.Provider value={{ unit, setUnit, toggleUnit, formatTemp, convertTemp }}>
      {children}
    </TemperatureContext.Provider>
  );
}

export function useTemperature(): TemperatureContextValue {
  const context = useContext(TemperatureContext);
  if (!context) {
    throw new Error('useTemperature must be used within a TemperatureProvider');
  }
  return context;
}
