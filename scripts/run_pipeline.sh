#!/bin/bash
# Congressional Trade Analysis Pipeline
# Run all steps in sequence

set -e
VENV="/home/pete/.openclaw/workspace-opus/research/congress-alpha/.venv"
SCRIPTS="/home/pete/.openclaw/workspace-opus/research/congress-alpha/scripts"

source "$VENV/bin/activate"

echo "=== Step 1: Build Dataset ==="
python3 "$SCRIPTS/01_build_dataset.py"

echo ""
echo "=== Step 2: Fetch Prices ==="
python3 "$SCRIPTS/02_fetch_prices.py"

echo ""
echo "=== Step 3: Analyze ==="
python3 "$SCRIPTS/03_analyze.py"

echo ""
echo "=== Pipeline Complete ==="
