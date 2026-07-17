#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "Bootstrapping Local Toolchain for Omniscience"
echo "=========================================================="

WORKSPACE_DIR="/Users/rajarshighosh/Downloads/omniscience"
TOOLCHAIN_DIR="$WORKSPACE_DIR/toolchain"
BIN_DIR="$TOOLCHAIN_DIR/bin"

mkdir -p "$TOOLCHAIN_DIR" "$BIN_DIR"

echo "1. Downloading and extracting Node.js (darwin-arm64)..."
if [ ! -f "$BIN_DIR/node" ]; then
  curl -sSfL "https://nodejs.org/dist/v20.15.0/node-v20.15.0-darwin-arm64.tar.gz" | tar -xz -C "$TOOLCHAIN_DIR" --strip-components=1
  echo "Node.js extraction complete!"
else
  echo "Node.js already exists, skipping download."
fi

echo "2. Downloading and extracting Astral uv (darwin-arm64)..."
if [ ! -f "$BIN_DIR/uv" ]; then
  # Fetch latest tarball
  TEMP_UV_DIR=$(mktemp -d)
  curl -sSfL "https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz" | tar -xz -C "$TEMP_UV_DIR"
  mv "$TEMP_UV_DIR"/uv-aarch64-apple-darwin/uv* "$BIN_DIR/"
  rm -rf "$TEMP_UV_DIR"
  echo "uv extraction complete!"
else
  echo "uv already exists, skipping download."
fi

# Set path to include local binaries
export PATH="$BIN_DIR:$PATH"

echo "3. Creating Python Virtual Environment using uv..."
if [ ! -d "$WORKSPACE_DIR/backend/.venv" ]; then
  mkdir -p "$WORKSPACE_DIR/backend"
  uv venv "$WORKSPACE_DIR/backend/.venv" --python 3.11
  echo "Virtual environment created!"
else
  echo "Virtual environment already exists, skipping creation."
fi

# Ensure requirements.txt exists so we can install it
if [ ! -f "$WORKSPACE_DIR/backend/requirements.txt" ]; then
  echo "Creating default backend/requirements.txt..."
  cat << 'EOF' > "$WORKSPACE_DIR/backend/requirements.txt"
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.4
networkx==3.3
openai==1.35.3
google-generativeai==0.7.0
python-dotenv==1.0.1
EOF
fi

echo "4. Installing Python dependencies..."
VIRTUAL_ENV="$WORKSPACE_DIR/backend/.venv" "$BIN_DIR/uv" pip install -r "$WORKSPACE_DIR/backend/requirements.txt"

echo "=========================================================="
echo "Toolchain Setup Complete!"
echo "Node version: $(node -v)"
echo "NPM version:  $(npm -v)"
echo "UV version:   $(uv --version)"
echo "Python:       $($WORKSPACE_DIR/backend/.venv/bin/python --version)"
echo "=========================================================="
