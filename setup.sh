#!/bin/bash
# Icemaker Setup Script
# Usage: ./setup.sh [--service] [--no-frontend]
#
# This script sets up the icemaker control system after a fresh git clone.
# Run with --service to also install and enable the systemd service.
# Run with --no-frontend to skip frontend build (useful on Pi if building elsewhere).

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Get script directory (where the repo is)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info "Setting up Icemaker in $SCRIPT_DIR"

# Detect if running on Raspberry Pi
is_raspberry_pi() {
    if [ -f /proc/cpuinfo ]; then
        grep -q "Raspberry Pi\|BCM" /proc/cpuinfo 2>/dev/null
        return $?
    fi
    return 1
}

# Detect Python version
get_python() {
    for py in python3.11 python3.10 python3.9 python3; do
        if command -v "$py" &>/dev/null; then
            version=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
                echo "$py"
                return 0
            fi
        fi
    done
    return 1
}

# Check for uv
has_uv() {
    command -v uv &>/dev/null
}

# Check for npm
has_npm() {
    command -v npm &>/dev/null
}

# Install uv if not present
install_uv() {
    info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
}

# Main setup
main() {
    local install_service=false
    local build_frontend=true

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --service)
                install_service=true
                ;;
            --no-frontend)
                build_frontend=false
                ;;
            *)
                warn "Unknown argument: $arg"
                ;;
        esac
    done

    # Check Python
    PYTHON=$(get_python) || error "Python 3.9+ is required but not found"
    info "Found Python: $PYTHON ($($PYTHON --version))"

    # Determine extras based on platform
    if is_raspberry_pi; then
        info "Detected Raspberry Pi - will install hardware dependencies"
        EXTRAS="rpi"
        ENV="production"
    else
        info "Not running on Raspberry Pi - using mock hardware"
        EXTRAS=""
        ENV="development"
    fi

    # Setup with uv (preferred) or pip
    if has_uv; then
        info "Using uv for package management"
        setup_with_uv "$EXTRAS"
    else
        warn "uv not found - attempting to install it"
        install_uv
        if has_uv; then
            info "Using uv for package management"
            setup_with_uv "$EXTRAS"
        else
            warn "Could not install uv - falling back to pip"
            setup_with_pip "$EXTRAS"
        fi
    fi

    # Build frontend
    if [ "$build_frontend" = true ]; then
        setup_frontend
    else
        info "Skipping frontend build (--no-frontend)"
    fi

    # Create environment file
    info "Creating environment configuration..."
    cat > "$SCRIPT_DIR/.env" << EOF
ICEMAKER_ENV=$ENV
ICEMAKER_LOG_LEVEL=INFO
EOF
    info "Created .env file with ICEMAKER_ENV=$ENV"

    # Install systemd service if requested and on Pi
    if [ "$install_service" = true ]; then
        if is_raspberry_pi; then
            install_systemd_service
        else
            warn "--service flag ignored: not running on Raspberry Pi"
        fi
    fi

    # Print success message
    echo ""
    info "Setup complete!"
    echo ""
    echo "To run the icemaker:"
    if has_uv; then
        echo "  uv run python -m icemaker"
    else
        echo "  source .venv/bin/activate"
        echo "  python -m icemaker"
    fi
    echo ""
    echo "For development (frontend + backend):"
    echo "  ./dev.sh"
    echo ""
    if is_raspberry_pi; then
        echo "To install as a system service:"
        echo "  ./setup.sh --service"
        echo ""
        echo "To run priming sequence on first startup:"
        echo "  ICEMAKER_SKIP_PRIMING=false uv run python -m icemaker"
    fi
}

setup_with_uv() {
    local extras="$1"

    info "Syncing dependencies with uv..."
    if [ -n "$extras" ]; then
        uv sync --extra "$extras"
    else
        uv sync
    fi
}

setup_with_pip() {
    local extras="$1"

    info "Creating virtual environment..."
    $PYTHON -m venv .venv

    info "Upgrading pip..."
    .venv/bin/pip install --upgrade pip

    # Pi-optimized pip flags:
    # --no-cache-dir: Save disk space (SD cards are small)
    # --compile: Pre-compile .pyc files for faster startup
    local PIP_FLAGS="--no-cache-dir --compile"

    info "Installing package..."
    if [ -n "$extras" ]; then
        .venv/bin/pip install $PIP_FLAGS -e ".[$extras]"
    else
        .venv/bin/pip install $PIP_FLAGS -e .
    fi
}

setup_frontend() {
    if ! has_npm; then
        warn "npm not found - skipping frontend build"
        warn "Install Node.js to build the frontend, or copy pre-built frontend/dist/"
        return
    fi

    info "Setting up frontend..."
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        info "Installing frontend dependencies..."
        npm install
    else
        info "Frontend dependencies already installed"
    fi

    info "Building frontend..."
    npm run build

    cd "$SCRIPT_DIR"
    info "Frontend built successfully"
}

install_systemd_service() {
    info "Installing systemd service..."

    # Determine the user
    SERVICE_USER="${SUDO_USER:-$USER}"

    # Create service file
    SERVICE_FILE="/etc/systemd/system/icemaker.service"

    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Icemaker Controller
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$SCRIPT_DIR
# Production environment
Environment=ICEMAKER_ENV=production
# Python optimizations for Pi
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=0
Environment=PYTHONOPTIMIZE=1
# Pi-optimized: disable access log, limit concurrent connections
ExecStart=$(which uv 2>/dev/null || echo "$SCRIPT_DIR/.venv/bin/python") run python -m icemaker --no-access-log --limit-concurrency 10
Restart=always
RestartSec=5
# Memory limit to prevent OOM on Pi (adjust as needed)
MemoryMax=256M

[Install]
WantedBy=multi-user.target
EOF

    # Fix ExecStart if using venv instead of uv
    if ! has_uv; then
        sudo sed -i "s|ExecStart=.*|ExecStart=$SCRIPT_DIR/.venv/bin/python -m icemaker --no-access-log --limit-concurrency 10|" "$SERVICE_FILE"
    fi

    info "Reloading systemd daemon..."
    sudo systemctl daemon-reload

    info "Enabling icemaker service..."
    sudo systemctl enable icemaker

    echo ""
    info "Systemd service installed!"
    echo "  Start:   sudo systemctl start icemaker"
    echo "  Stop:    sudo systemctl stop icemaker"
    echo "  Status:  sudo systemctl status icemaker"
    echo "  Logs:    journalctl -u icemaker -f"
}

main "$@"
