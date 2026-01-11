#!/bin/bash
# Setup script for ImageNamer on Linux/macOS

echo "========================================"
echo "ImageNamer Setup"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed"
    echo "Please install Python 3.8+ from https://www.python.org"
    exit 1
fi

echo "[1/3] Creating virtual environment..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi

echo "[2/3] Installing dependencies..."
source .venv/bin/activate
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo "[3/3] Creating .env file from template..."
if [ -f .env ]; then
    echo ".env already exists, skipping"
else
    cp .env.example .env
    echo ".env created from template - please edit it with your settings"
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your settings (Ollama URL, image folder, etc.)"
echo "  2. Ensure Ollama is running: ollama serve"
echo "  3. Run: cd src"
echo "  4. Test: python main.py --help"
echo "  5. Preview: python main.py --dry-run"
echo "  6. Process: python main.py"
echo ""
