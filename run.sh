#!/usr/bin/env bash
set -euo pipefail

# Workspace directories
WORKSPACE_DIR="/Users/rajarshighosh/Downloads/omniscience"
BIN_DIR="$WORKSPACE_DIR/toolchain/bin"

export PATH="$BIN_DIR:$PATH"

echo "=========================================================="
echo "Starting Omniscience v0.1 Platform"
echo "=========================================================="

# Check if toolchain is setup
if [ ! -d "$WORKSPACE_DIR/toolchain" ] || [ ! -d "$WORKSPACE_DIR/backend/.venv" ]; then
  echo "Toolchain not found. Bootstrapping first..."
  ./setup_toolchain.sh
fi

# Run backend
echo "-> Launching FastAPI Backend on http://localhost:8000..."
VIRTUAL_ENV="$WORKSPACE_DIR/backend/.venv" "$BIN_DIR/uv" run uvicorn backend.main:app --port 8000 --reload &
BACKEND_PID=$!

# Run frontend
echo "-> Launching React Vite Frontend on http://localhost:5173..."
npm run dev --prefix frontend &
FRONTEND_PID=$!

# Cleanup handler on exit
cleanup() {
  echo ""
  echo "Shutting down Omniscience platform services..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  echo "Goodbye!"
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "=========================================================="
echo "Platform is running!"
echo "- Frontend Dashboard: http://localhost:5173"
echo "- API Interactive Docs: http://localhost:8000/docs"
echo "=========================================================="
echo "Press Ctrl+C to terminate services..."

# Keep script running
wait $BACKEND_PID $FRONTEND_PID
