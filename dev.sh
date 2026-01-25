#!/bin/bash
# Development script - runs both backend and frontend with hot reload
#
# Usage: ./dev.sh
#
# Backend runs on http://localhost:8000
# Frontend runs on http://localhost:5173 (with proxy to backend)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for required tools
has_uv() { command -v uv &>/dev/null; }
has_npm() { command -v npm &>/dev/null; }

# Cleanup function to kill background processes
cleanup() {
    echo ""
    info "Shutting down..."
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    wait 2>/dev/null
    info "Done"
}

trap cleanup EXIT INT TERM

# Start backend
start_backend() {
    info "Starting backend on http://localhost:8000..."
    if has_uv; then
        uv run python -m icemaker --log-level DEBUG &
    else
        source .venv/bin/activate
        python -m icemaker --log-level DEBUG &
    fi
    BACKEND_PID=$!
}

# Start frontend
start_frontend() {
    if ! has_npm; then
        warn "npm not found - frontend will not be started"
        warn "Access the API directly at http://localhost:8000"
        return
    fi

    # Wait a moment for backend to start
    sleep 2

    info "Starting frontend on http://localhost:5173..."
    cd "$SCRIPT_DIR/frontend"
    npm run dev &
    FRONTEND_PID=$!
    cd "$SCRIPT_DIR"
}

main() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║     Icemaker Development Environment      ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"

    # Check dependencies
    if ! has_uv && [ ! -d ".venv" ]; then
        error "Neither uv nor .venv found. Run ./setup.sh first."
    fi

    start_backend
    start_frontend

    echo ""
    info "Development servers running:"
    echo "  Backend API:  http://localhost:8000"
    if has_npm; then
        echo "  Frontend:     http://localhost:5173"
    fi
    echo ""
    info "Press Ctrl+C to stop"
    echo ""

    # Wait for either process to exit
    wait
}

main "$@"
