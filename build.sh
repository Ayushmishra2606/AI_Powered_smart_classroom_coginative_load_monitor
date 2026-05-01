#!/usr/bin/env bash
# build.sh — Render build script

# Exit on error
set -e

echo "==> Starting build..."

# 1. Install pip dependencies
echo "==> Upgrading pip..."
python -m pip install --upgrade pip

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

# 2. Ensure directories exist for the app
echo "==> Creating required directories..."
mkdir -p face-reccognization/database
mkdir -p static/face_uploads
mkdir -p instance

echo "==> Build complete!"
