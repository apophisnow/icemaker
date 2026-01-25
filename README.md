# Icemaker Control System

Industrial icemaker control system with async FSM, physics-based simulation, and React dashboard.

## Features

- **Async State Machine**: Event-driven FSM controlling the ice-making cycle (CHILL → ICE → HEAT → repeat)
- **Hardware Abstraction**: Supports real Raspberry Pi GPIO/sensors or mock implementations for development
- **Physics-Based Simulator**: Realistic thermal model for testing without hardware
- **REST + WebSocket API**: Real-time state updates and control via FastAPI
- **React Dashboard**: Live temperature charts, relay status, and cycle control

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  State   │ │  Temp    │ │  Relay   │ │ Controls │       │
│  │ Display  │ │  Chart   │ │  Status  │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │ WebSocket + REST
┌─────────────────────────┴───────────────────────────────────┐
│                     FastAPI Backend                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    Controller                         │  │
│  │  ┌─────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │   FSM   │  │    HAL      │  │ Thermal Model   │   │  │
│  │  │ States  │  │ GPIO/Sensors│  │   (Simulator)   │   │  │
│  │  └─────────┘  └─────────────┘  └─────────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend development)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Automated Setup

The easiest way to get started is using the setup script:

```bash
# Clone the repository
git clone <repo-url>
cd icemaker

# Run setup (auto-detects platform)
./setup.sh
```

The setup script will:
- Detect if running on Raspberry Pi or development machine
- Install uv if not present (or fall back to pip)
- Install appropriate dependencies (including RPi.GPIO on Pi)
- Create `.env` with correct environment settings

### Running the Application

```bash
# With uv (recommended)
uv run python -m icemaker

# Or with virtual environment
source .venv/bin/activate
python -m icemaker
```

### Running with Simulator (Development)

```bash
# Terminal 1: Start backend with simulator
uv run python -m icemaker --simulator

# Terminal 2: Start frontend dev server
cd frontend && npm run dev
```

Open http://localhost:5173 to view the dashboard.

## Raspberry Pi Deployment

### Quick Deploy

```bash
git clone <repo-url> icemaker
cd icemaker
./setup.sh --service
```

This installs dependencies and sets up a systemd service that starts on boot.

### Service Management

```bash
sudo systemctl start icemaker    # Start the service
sudo systemctl stop icemaker     # Stop the service
sudo systemctl status icemaker   # Check status
journalctl -u icemaker -f        # View logs
```

### First-Time Setup (with Priming)

By default, the water priming sequence is skipped on startup (assumes the system is already primed). To run the priming sequence on first boot:

```bash
# One-time priming
ICEMAKER_SKIP_PRIMING=false uv run python -m icemaker

# Or set in config/production.yaml:
# startup:
#   skip_priming: false
```

### Manual Installation (without setup script)

```bash
# Upgrade pip and install
pip install --upgrade pip
pip install ".[rpi]"

# Set environment
export ICEMAKER_ENV=production

# Run
python -m icemaker
```

## Project Structure

```
icemaker/
├── setup.sh               # Automated setup script
├── config/                # YAML configuration files
│   ├── default.yaml       # Default settings
│   ├── development.yaml   # Dev environment (simulator enabled)
│   └── production.yaml    # Production settings (real hardware)
├── src/icemaker/
│   ├── core/              # FSM, states, events, controller
│   ├── hal/               # Hardware abstraction layer
│   ├── simulator/         # Physics-based thermal model
│   └── api/               # FastAPI routes and WebSocket
├── tests/
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
└── frontend/              # React + TypeScript dashboard
```

## Ice-Making Cycle

The system follows this state flow:

### Startup
1. **OFF** - System powered off (initial state)
2. **POWER_ON** - Water priming sequence (optional, skipped by default)
3. **STANDBY** - Ready, waiting for manual start

### Ice-Making Loop
4. **CHILL** (prechill) - Cool plate to 32°F
5. **ICE** - Make ice at -2°F with water recirculation
6. **HEAT** - Harvest ice by heating plate to 38°F
7. **CHILL** (rechill) - Cool to 35°F before next cycle
8. Check bin:
   - If full → **IDLE** (auto-restarts when bin empties)
   - If not full → repeat from step 4

## Configuration

Configuration is loaded from YAML files with environment variable overrides:

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `ICEMAKER_ENV` | Config environment (development/production) | development |
| `ICEMAKER_USE_SIMULATOR` | Enable thermal simulator | false |
| `ICEMAKER_SKIP_PRIMING` | Skip water priming on startup | true |
| `ICEMAKER_PRECHILL_TEMP` | Prechill target temperature (°F) | 32.0 |
| `ICEMAKER_ICE_TEMP` | Ice-making target temperature (°F) | -2.0 |
| `ICEMAKER_HARVEST_TEMP` | Harvest threshold temperature (°F) | 38.0 |
| `ICEMAKER_RECHILL_TEMP` | Rechill target temperature (°F) | 35.0 |
| `ICEMAKER_BIN_THRESHOLD` | Bin full detection threshold (°F) | 35.0 |

### Configuration Files

- `config/default.yaml` - Base defaults
- `config/development.yaml` - Development settings (simulator enabled)
- `config/production.yaml` - Production settings (matches hardware values)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state/` | GET | Current icemaker state |
| `/api/state/cycle` | POST | Start/stop/emergency stop |
| `/api/state/ws` | WebSocket | Real-time updates |
| `/api/relays/` | GET/POST | Relay states |
| `/api/sensors/` | GET | Temperature readings |
| `/api/config/` | GET/PUT | Configuration |
| `/health` | GET | Health check |

## Testing

```bash
# Run all tests
uv run pytest tests -v

# Run unit tests only
uv run pytest tests/unit -v

# Run integration tests only
uv run pytest tests/integration -v

# Run with coverage
uv run pytest tests --cov=icemaker
```

## Hardware Setup

### GPIO Pin Mapping

| Relay | GPIO Pin |
|-------|----------|
| Water Valve | 12 |
| Hot Gas Solenoid | 5 |
| Recirculating Pump | 6 |
| Compressor 1 | 24 |
| Compressor 2 | 25 |
| Condenser Fan | 23 |
| LED | 22 |
| Ice Cutter | 27 |

### Temperature Sensors (DS18B20)

| Sensor | ID |
|--------|-----|
| Plate | 092101487373 |
| Ice Bin | 3c01f0956abd |

## License

MIT
