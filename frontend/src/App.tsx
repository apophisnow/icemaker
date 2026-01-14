import { Dashboard } from './components/Dashboard';
import { TemperatureProvider } from './contexts/TemperatureContext';
import './styles/index.css';

function App() {
  return (
    <TemperatureProvider>
      <Dashboard />
    </TemperatureProvider>
  );
}

export default App;
