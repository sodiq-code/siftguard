#!/bin/bash
# SIFTGuard Setup Script
# Works on SIFT Workstation, Ubuntu, and most Linux distros

set -e

echo "╔══════════════════════════════════════╗"
echo "║  SIFTGuard — Setup Script            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 1. Create virtual environment
echo "[1/5] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
echo "[2/5] Installing Python dependencies..."
pip install --quiet -r requirements.txt

# 3. Install system forensic tools (if not already installed)
echo "[3/5] Checking forensic tools..."

# Sleuthkit
if ! command -v fls &> /dev/null; then
    echo "      Installing sleuthkit..."
    sudo apt-get install -y sleuthkit 2>/dev/null || brew install sleuthkit 2>/dev/null || true
fi

# log2timeline / plaso (optional — falls back to reconstruction)
if ! command -v log2timeline.py &> /dev/null; then
    echo "      log2timeline not found — timeline reconstruction will be used"
fi

echo "      ✓ Tool check complete"

# 4. Create .env from example
echo "[4/5] Creating .env configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "      Created .env — IMPORTANT: Add your GROQ_API_KEY"
fi

# 5. Create evidence directory structure
echo "[5/5] Creating evidence directories..."
mkdir -p data/evidence/memory
mkdir -p data/evidence/logs
mkdir -p data/evidence/disk
mkdir -p data/cases

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add GROQ_API_KEY to .env"
echo "  2. Place evidence files in data/evidence/"
echo "     - Memory dumps → data/evidence/memory/"
echo "     - EVTX logs   → data/evidence/logs/"
echo "     - Disk images  → data/evidence/disk/"
echo "  3. Run: source .venv/bin/activate && python main.py"
