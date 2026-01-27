#!/bin/bash
#
# run.sh - Run the trending stocks scanner
#
# Usage:
#   ./run.sh              # Full scan
#   ./run.sh momentum     # Momentum only
#   ./run.sh --analyze    # Scan + Gemini analysis
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Parse args
ANALYZE=false
SOURCE=""

for arg in "$@"; do
    case $arg in
        --analyze|-a)
            ANALYZE=true
            ;;
        momentum|reddit|news|finviz)
            SOURCE="$arg"
            ;;
    esac
done

# Run scanner
if [[ -n "$SOURCE" ]]; then
    python main.py --source "$SOURCE"
else
    python main.py
fi

# Run Gemini analysis if requested
if [[ "$ANALYZE" == true ]]; then
    echo ""
    ./analyze_with_gemini.sh
fi
