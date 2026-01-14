import { Dashboard } from './components/Dashboard';
import { DataLoggerProvider } from './contexts/DataLoggerContext';
import { TemperatureProvider } from './contexts/TemperatureContext';
import './styles/index.css';

function App() {
  return (
    <TemperatureProvider>
      <DataLoggerProvider>
        <Dashboard />
      </DataLoggerProvider>
    </TemperatureProvider>
  );
}

export default App;
