#!/bin/bash
#
# run_full_analysis.sh - Run scanner and then Gemini analysis in one command
#
# Usage: ./run_full_analysis.sh [options]
#
# Options:
#   --top N        Show top N results (default: 10)
#   --no-raw       Skip saving raw scanner data
#   --skip-gemini  Only run scanner, skip Gemini analysis
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Parse arguments
TOP_N=10
NO_RAW=""
SKIP_GEMINI=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --top)
            TOP_N="$2"
            shift 2
            ;;
        --no-raw)
            NO_RAW="--no-raw"
            shift
            ;;
        --skip-gemini)
            SKIP_GEMINI=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          TRENDING STOCKS - FULL ANALYSIS PIPELINE         ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Activate virtual environment
if [[ -d "venv" ]]; then
    source venv/bin/activate
else
    echo -e "${RED}Error: Virtual environment not found. Run: python -m venv venv${NC}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────
# STEP 1: Run Scanner
# ─────────────────────────────────────────────────────────────────────
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  STEP 1: Running Trending Stocks Scanner${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

START_TIME=$(date +%s)

python main.py --top "$TOP_N" $NO_RAW

SCANNER_EXIT=$?
SCANNER_TIME=$(($(date +%s) - START_TIME))

if [[ $SCANNER_EXIT -ne 0 ]]; then
    echo -e "${RED}Scanner failed with exit code $SCANNER_EXIT${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Scanner completed in ${SCANNER_TIME}s${NC}"

# Extract raw data directory from report
RAW_DATA_DIR=$(python3 -c "import json; print(json.load(open('output/trending_report.json')).get('raw_data_dir', ''))" 2>/dev/null)

# ─────────────────────────────────────────────────────────────────────
# STEP 2: Run Gemini Analysis
# ─────────────────────────────────────────────────────────────────────
if [[ "$SKIP_GEMINI" == "false" ]]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  STEP 2: Running Gemini AI Analysis${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    GEMINI_START=$(date +%s)

    ./analyze_with_gemini.sh

    GEMINI_EXIT=$?
    GEMINI_TIME=$(($(date +%s) - GEMINI_START))

    if [[ $GEMINI_EXIT -ne 0 ]]; then
        echo -e "${YELLOW}Gemini analysis failed (exit code $GEMINI_EXIT)${NC}"
        echo -e "${YELLOW}Scanner results are still available in output/trending_report.json${NC}"
    else
        echo ""
        echo -e "${GREEN}Gemini analysis completed in ${GEMINI_TIME}s${NC}"
    fi
fi

# ─────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────
TOTAL_TIME=$(($(date +%s) - START_TIME))

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                    ANALYSIS COMPLETE                      ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}Total time:${NC} ${TOTAL_TIME}s"
echo ""
echo -e "  ${GREEN}Outputs:${NC}"
echo -e "    Scanner Report:  output/trending_report.json"
if [[ -n "$RAW_DATA_DIR" && "$RAW_DATA_DIR" != "None" ]]; then
    echo -e "    Raw Data:        $RAW_DATA_DIR"
fi
if [[ "$SKIP_GEMINI" == "false" && $GEMINI_EXIT -eq 0 ]]; then
    DATE_STR=$(date +%Y-%m-%d)
    echo -e "    Gemini HTML:     output/analysis_${DATE_STR}.html"
    echo -e "    Gemini JSON:     output/analysis_${DATE_STR}.json"
fi
echo ""
