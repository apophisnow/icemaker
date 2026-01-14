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

- Python 3.10+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd icemaker

# Install Python dependencies
uv add fastapi uvicorn websockets pydantic pyyaml pytest pytest-asyncio httpx

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### Running with Simulator

```bash
# Terminal 1: Start backend with simulator
uv run python -m icemaker --simulator

# Terminal 2: Start frontend dev server
cd frontend && npm run dev
```

Open http://localhost:5173 to view the dashboard.

### Running on Raspberry Pi

```bash
# Install Raspberry Pi dependencies
uv add RPi.GPIO w1thermsensor

# Start without simulator (uses real hardware)
uv run python -m icemaker
```

## Project Structure

```
icemaker/
├── config/                 # YAML configuration files
│   ├── default.yaml       # Default settings
│   └── development.yaml   # Dev environment (faster timeouts)
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

The system follows this cycle:

1. **IDLE** - Waiting for start command
2. **CHILL** (prechill) - Cool plate to 32°F
3. **ICE** - Make ice at -2°F with water recirculation
4. **HEAT** - Harvest ice by heating plate to 38°F
5. **CHILL** (rechill) - Cool to 35°F before next cycle
6. Check bin → if full, return to IDLE; otherwise repeat

## Configuration

Configuration is loaded from YAML files with environment variable overrides:

| Environment Variable | Description |
|---------------------|-------------|
| `ICEMAKER_ENV` | Config environment (development/production) |
| `ICEMAKER_USE_SIMULATOR` | Enable thermal simulator |
| `ICEMAKER_PRECHILL_TEMP` | Prechill target temperature |
| `ICEMAKER_ICE_TEMP` | Ice-making target temperature |
| `ICEMAKER_HARVEST_TEMP` | Harvest threshold temperature |
| `ICEMAKER_BIN_THRESHOLD` | Bin full detection threshold |

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
