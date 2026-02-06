#!/bin/bash
#
# analyze_with_gemini.sh - Deep-dive analysis with Gemini, outputs styled HTML
#
# Usage: ./analyze_with_gemini.sh [report_file]
#
# Requires: gemini CLI installed and configured
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="${1:-$SCRIPT_DIR/output/trending_report.json}"
RAW_DIR="$SCRIPT_DIR/output/raw"
DATE_STR=$(date +%Y-%m-%d)
TIME_STR=$(date +%H:%M)
OUTPUT_HTML="$SCRIPT_DIR/output/analysis_${DATE_STR}.html"
OUTPUT_JSON="$SCRIPT_DIR/output/analysis_${DATE_STR}.json"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}       GEMINI AI DEEP-DIVE ANALYSIS          ${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Check if report file exists
if [[ ! -f "$REPORT_FILE" ]]; then
    echo -e "${RED}Error: Report file not found: $REPORT_FILE${NC}"
    echo "Run the trending stocks scanner first: python main.py"
    exit 1
fi

# Find the most recent raw data folder
LATEST_RAW_DIR=$(ls -td "$RAW_DIR"/*/ 2>/dev/null | head -1)
if [[ -z "$LATEST_RAW_DIR" ]]; then
    echo -e "${YELLOW}Warning: No raw data folder found, using summary report only${NC}"
    USE_RAW_DATA=false
else
    USE_RAW_DATA=true
    echo -e "${GREEN}Using raw data from: $LATEST_RAW_DIR${NC}"
fi

# Find gemini CLI
GEMINI_CMD=""
if [[ -x "/opt/homebrew/bin/gemini" ]]; then
    GEMINI_CMD="/opt/homebrew/bin/gemini"
elif [[ -x "/usr/local/bin/gemini" ]]; then
    GEMINI_CMD="/usr/local/bin/gemini"
elif command -v gemini &> /dev/null; then
    GEMINI_CMD="gemini"
fi

if [[ -z "$GEMINI_CMD" ]]; then
    echo -e "${YELLOW}Warning: gemini CLI not found.${NC}"
    echo "Install Gemini CLI or set up an alias."
    exit 1
fi

echo -e "${GREEN}Reading report from: $REPORT_FILE${NC}"
echo ""

# Build the prompt for structured JSON output
read -r -d '' PROMPT << 'EOF' || true
You are an expert quantitative trading analyst. Analyze this multi-source trending stocks data and produce a STRUCTURED JSON response.

IMPORTANT: Your response must be ONLY valid JSON, no markdown, no explanation outside the JSON.

Return this exact JSON structure:

{
  "executive_summary": {
    "market_regime": "string describing current market regime (risk-on, risk-off, rotation, etc.)",
    "dominant_themes": ["theme1", "theme2", "theme3"],
    "key_insight": "One sentence key takeaway",
    "overall_bias": "bullish|bearish|neutral",
    "confidence": "high|medium|low",
    "macro_context": {
      "vix_assessment": "Low/Elevated/High - what VIX level implies for positioning",
      "yield_environment": "Rising/Falling/Stable - impact on growth vs value",
      "dollar_trend": "Strong/Weak - impact on multinationals and commodities",
      "credit_conditions": "Tight/Loose - HYG/LQD spread assessment",
      "market_breadth": "Broad/Narrow - how many stocks participating in the move"
    }
  },
  "sector_analysis": {
    "leading_sectors": [
      {"sector": "name", "reason": "why leading", "outlook": "string"}
    ],
    "lagging_sectors": [
      {"sector": "name", "reason": "why lagging", "outlook": "string"}
    ],
    "rotation_signal": "description of any sector rotation"
  },
  "deep_dives": [
    {
      "ticker": "SYMBOL",
      "company": "Company Name",
      "company_description": "2-3 sentences describing what the company does, its market position, and key products/services",
      "verdict": "STRONG BUY|BUY|HOLD|SELL|STRONG SELL",
      "confidence": "high|medium|low",
      "probability": {
        "win_probability": 65,
        "risk_reward_ratio": "2.5:1",
        "expected_move": "+12% to +18%",
        "timeframe": "2-4 weeks"
      },
      "why_bullish": "3-4 sentences explaining the specific reasons why this stock is attractive RIGHT NOW. What's driving the momentum? What catalyst is upcoming? Why is money flowing in?",
      "rationale": "2-3 sentences providing the logical reasoning behind the recommendation. Connect the data points: momentum scores, sentiment, sector rotation, theme alignment.",
      "thesis": "2-3 sentence investment thesis",
      "bull_case": "Why this could go higher",
      "bear_case": "What could go wrong",
      "technicals": {
        "trend": "uptrend|downtrend|sideways",
        "momentum": "strong|moderate|weak|negative",
        "volume_signal": "accumulation|distribution|neutral",
        "key_levels": {
          "support": "price or N/A",
          "resistance": "price or N/A",
          "stop_loss": "suggested stop"
        }
      },
      "sentiment": {
        "reddit": "bullish|bearish|neutral|N/A",
        "news": "positive|negative|neutral|N/A",
        "social_risk": "high|medium|low (crowding risk)"
      },
      "catalysts": ["upcoming catalyst 1", "catalyst 2"],
      "risks": ["risk 1", "risk 2"],
      "action": {
        "entry_zone": "price range",
        "target": "price target",
        "stop": "stop loss",
        "position_size": "small|medium|large",
        "timeframe": "day trade|swing|position"
      },
      "exit_strategy": {
        "profit_target": "When to take profits (e.g., 'At $150 resistance or +15% gain')",
        "time_exit": "When to exit based on time (e.g., 'Exit if no movement after 2 weeks')",
        "trailing_stop": "How to trail stops as trade works (e.g., 'Move stop to breakeven at +5%, trail by 8% after +10%')"
      },
      "if_wrong": {
        "warning_signs": ["Sign that thesis is breaking 1", "Sign 2", "Sign 3"],
        "exit_triggers": ["Specific condition to exit immediately 1", "Exit trigger 2"],
        "max_loss": "Maximum acceptable loss before exiting (e.g., '-8% from entry')",
        "invalidation": "What would completely invalidate the bullish thesis"
      },
      "score_breakdown": {
        "momentum": 0,
        "finviz": 0,
        "reddit": 0,
        "news": 0,
        "google_trends": 0,
        "short_interest": 0,
        "combined": 0
      }
    }
  ],
  "avoid_list": [
    {
      "ticker": "SYMBOL",
      "reason": "Why to avoid",
      "risk_type": "overextended|crowded|deteriorating|trap"
    }
  ],
  "market_risks": [
    {
      "risk": "description",
      "severity": "high|medium|low",
      "hedge": "how to hedge or protect"
    }
  ],
  "trading_plan": {
    "premarket_focus": ["item1", "item2"],
    "key_levels": {
      "SPY": {"support": "price", "resistance": "price"},
      "QQQ": {"support": "price", "resistance": "price"}
    },
    "best_setups": ["setup1", "setup2", "setup3"],
    "avoid_times": "times to avoid trading if any",
    "risk_limit": "suggested daily risk limit guidance"
  },
  "hidden_gems": [
    {
      "ticker": "SYMBOL",
      "company": "Company Name",
      "market_cap": "small-cap|mid-cap",
      "why_overlooked": "Why this stock isn't on most radars",
      "thesis": "2-3 sentence investment thesis",
      "catalyst": "Specific upcoming catalyst",
      "risk": "Main risk to monitor",
      "entry_zone": "price range",
      "target": "price target",
      "stop": "stop loss",
      "score_breakdown": {
        "momentum": 0,
        "finviz": 0,
        "reddit": 0,
        "news": 0,
        "google_trends": 0,
        "short_interest": 0,
        "combined": 0
      }
    }
  ],
  "squeeze_watch": [
    {
      "ticker": "SYMBOL",
      "company": "Company Name",
      "short_float": 0,
      "days_to_cover": 0,
      "squeeze_thesis": "Why this could squeeze",
      "trigger": "What would trigger the squeeze",
      "risk_level": "high|medium|low",
      "notes": "Additional context"
    }
  ],
  "breakout_watch": [
    {
      "ticker": "SYMBOL",
      "company": "Company Name",
      "pattern": "Description of technical pattern",
      "breakout_level": "price level to watch",
      "volume_confirmation": "What volume to look for",
      "target_on_breakout": "price target if breaks out",
      "notes": "Additional context"
    }
  ],
  "short_deep_dives": [
    {
      "ticker": "SYMBOL",
      "company": "Company Name",
      "company_description": "2-3 sentences describing the company",
      "verdict": "STRONG SHORT|SHORT|AVOID LONG|REDUCE",
      "confidence": "high|medium|low",
      "short_score": 0,
      "probability": {
        "win_probability": 65,
        "risk_reward_ratio": "2:1",
        "expected_move": "-10% to -20%",
        "timeframe": "2-6 weeks"
      },
      "why_bearish": "3-4 sentences explaining why this stock is weak RIGHT NOW. What's breaking down technically? What fundamental deterioration? What negative catalyst?",
      "rationale": "2-3 sentences connecting the data: bearish momentum, insider selling, downgrades, options flow",
      "thesis": "2-3 sentence short thesis",
      "bear_case": "Why this could fall further (your thesis)",
      "bull_risk": "What could go wrong with the short (squeeze, turnaround, buyout)",
      "technicals": {
        "trend": "downtrend|breakdown|topping",
        "momentum": "negative|weak|deteriorating",
        "volume_signal": "distribution|capitulation|neutral",
        "key_levels": {
          "resistance": "price level where to set stop",
          "support_target": "price target on breakdown",
          "stop_loss": "cover/stop level above resistance"
        }
      },
      "squeeze_risk": {
        "short_float_pct": 0,
        "days_to_cover": 0,
        "risk_level": "high|medium|low",
        "squeeze_warning": "Assessment of squeeze risk and how to manage it"
      },
      "bearish_signals": ["signal1", "signal2", "signal3"],
      "catalysts": ["negative catalyst 1", "negative catalyst 2"],
      "action": {
        "entry_zone": "price range to initiate short / buy puts",
        "cover_target": "price to cover for profit",
        "stop_loss": "price to cover for loss (above resistance)",
        "position_size": "small|medium (shorts should be smaller)",
        "instrument": "short shares|put options|put spread",
        "timeframe": "swing|position"
      },
      "if_wrong": {
        "warning_signs": ["Sign short thesis is failing 1", "Sign 2"],
        "exit_triggers": ["Cover immediately if..."],
        "max_loss": "Maximum acceptable loss on the short",
        "invalidation": "What would kill the bearish thesis"
      },
      "score_breakdown": {
        "bearish_momentum": 0,
        "fundamentals": 0,
        "analyst_downgrades": 0,
        "bearish_options": 0,
        "insider_selling": 0,
        "combined_short_score": 0
      }
    }
  ],
  "pair_trades": [
    {
      "pair_name": "Descriptive name (e.g. 'Semis Leader vs Laggard')",
      "sector": "Shared sector or theme",
      "rationale": "Why this pair works - what structural relationship exists",
      "long_leg": {
        "ticker": "SYMBOL",
        "company": "Company Name",
        "why_long": "1-2 sentences on strength",
        "entry": "price range",
        "target": "price target"
      },
      "short_leg": {
        "ticker": "SYMBOL",
        "company": "Company Name",
        "why_short": "1-2 sentences on weakness",
        "entry": "price range",
        "cover_target": "cover target"
      },
      "spread_thesis": "How the spread should move and why",
      "risk": "What could make the pair diverge against you",
      "correlation": "high|medium - how correlated are these names",
      "timeframe": "Expected holding period",
      "net_exposure": "market-neutral|slight long bias|slight short bias"
    }
  ]
}

RULES:
1. Provide deep_dives for the TOP 6 stocks from the combined rankings
2. Include ALL score data from the input for each stock in score_breakdown
3. Be specific with price levels where possible
4. For stocks without price data, use "N/A" for levels
5. Base your analysis on the actual data provided, not assumptions
6. The avoid_list should include 3-5 stocks that look risky despite appearing in the data
7. HIDDEN GEMS (CRITICAL) - Provide 4-5 stocks that:
   - Are NOT in the top 10 by combined score but still show promise
   - Are small-cap or mid-cap (avoid mega-caps like AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA)
   - Show unusual activity: high reddit buzz relative to market cap, unusual volume, new highs in niche sectors
   - May be flying under the radar because they're not household names
   - Look for stocks with strong momentum but lower news/reddit coverage (contrarian signal)
   - Prioritize stocks from hot themes (semis, uranium, precious metals, energy) that aren't the obvious plays
8. SQUEEZE WATCH - Identify 3 stocks with high short interest that could squeeze:
   - Use the short_interest data from the input (top_short_interest array)
   - Look for high short_float (>15%) combined with positive momentum
   - Consider days-to-cover and recent volume
9. BREAKOUT WATCH - Identify 3-5 stocks showing technical breakout potential:
   - Look for stocks with strong momentum scores but not yet overbought
   - Consider volume signals (accumulation)
   - Identify key resistance levels that could break
10. IMPORTANT - For each stock provide:
   - company_description: What the company actually does (products, services, market position)
   - why_bullish: Specific reasons why NOW is a good entry. Be concrete about catalysts, momentum, and what's driving the move
   - probability: Estimate win probability (50-85%), risk/reward ratio, expected move range, and timeframe
   - rationale: Connect the dots - explain how the momentum score, sentiment, sector rotation, and theme alignment support your verdict
8. Win probability should reflect realistic odds based on the data:
   - STRONG BUY with high confidence: 70-85%
   - BUY with high confidence: 65-75%
   - BUY with medium confidence: 55-65%
   - HOLD: 45-55%
   - Adjust based on multi-source confirmation and theme alignment
9. EXIT STRATEGY - For each stock provide clear exit criteria:
   - profit_target: Specific price or percentage to take profits
   - time_exit: When to exit if the trade isn't working (time-based stop)
   - trailing_stop: How to protect profits as the trade works
10. IF WRONG - Help traders know when to cut losses:
   - warning_signs: 3 specific signs the thesis is breaking (e.g., "Volume dries up", "Breaks below 20-day MA", "Sector rotation out of tech")
   - exit_triggers: 2 specific conditions that should trigger immediate exit
   - max_loss: Maximum acceptable loss (usually -5% to -10%)
   - invalidation: What would completely kill the bullish case
11. DATA SOURCES AVAILABLE (RAW DATA):
   You now have access to the COMPLETE raw data from each scanner, not just summaries:
   - momentum: ALL stocks with price changes, volume ratios, technical signals
   - reddit: ALL mentions with subreddits, upvotes, sentiment scores
   - news: ALL articles with sources, categories, sentiment
   - finviz_signals: Complete lists of gainers, losers, unusual volume, new highs, oversold, overbought
   - google_trends: ALL trending stocks with trend values and breakout flags
   - short_interest: ALL stocks with short float %, days-to-cover, squeeze risk
   - options_activity: ALL unusual options flow with volume/OI ratios, put/call ratios, signals
   - insider_trading: ALL insider buys/sells with transaction values, roles
   - perplexity: AI-discovered tickers with catalysts and sentiment
   - combined: Final weighted scores combining all sources
12. For HIDDEN GEMS, prioritize finding stocks that:
   - Have momentum_score > 60 but are NOT in the top 10 combined
   - Show up in top_short_interest with squeeze_risk = "high" or "medium"
   - Are in hot themes but less covered (lower reddit/news scores relative to momentum)
   - Have google_trends activity (is_breakout = true is especially interesting)
13. SHORT DEEP DIVES (CRITICAL) - Analyze the short_candidates data and provide deep dives for the TOP 4 short candidates:
   - Use the short_candidates array which has short_score, bearish_signals, and individual source scores
   - Use the raw_bearish_momentum and raw_fundamentals data for technical/fundamental detail
   - Look for confluence: bearish momentum + fundamental stress + insider selling + analyst downgrades
   - Assess squeeze risk honestly: if short_float > 20%, warn clearly
   - Suggest appropriate instruments: direct short for liquid names, put options for squeeze-risk names
   - Position sizing should be SMALLER than longs (shorts have unlimited risk)
   - Always include a stop loss ABOVE the nearest resistance level
14. PAIR TRADES - Identify 2-3 long/short pairs:
   - Find stocks from the SAME sector where one is in top longs and the other in top shorts
   - Or find divergence within a hot theme (strongest name long vs weakest name short)
   - These should be correlated enough to hedge each other but diverging on fundamentals
   - Specify the net market exposure (ideally market-neutral)
15. MACRO CONTEXT - In executive_summary.macro_context:
   - VIX: Look at VXX in the momentum data for volatility assessment
   - Yields: Look at TLT in momentum data (falling TLT = rising yields)
   - Dollar: Look at UUP or infer from commodity/international performance
   - Credit: Look at HYG in momentum data (falling HYG = widening spreads)
   - Breadth: Assess from the overall momentum data (what % of tickers are above MA20/MA50)
16. EARNINGS FLAGS - When you know a stock has earnings coming in the next 2 weeks, note it:
   - In deep_dives: add "EARNINGS APPROACHING" to catalysts
   - In short_deep_dives: note that shorts around earnings are extra risky
   - Use your knowledge of earnings calendar dates

TRENDING STOCKS DATA:
EOF

# Build combined data from raw files or fallback to summary report
if [[ "$USE_RAW_DATA" == "true" ]]; then
    echo -e "${YELLOW}Loading raw data files...${NC}"

    # Use Python to combine all raw JSON files into a single structured object
    RAW_DATA=$(python3 << PYEOF
import json
import os
from pathlib import Path

raw_dir = Path("$LATEST_RAW_DIR")
report_file = Path("$REPORT_FILE")

# Start with the summary report for metadata
combined = {}
if report_file.exists():
    with open(report_file) as f:
        summary = json.load(f)
        combined['timestamp'] = summary.get('timestamp')
        combined['discovery_stats'] = summary.get('discovery_stats', {})
        combined['hot_themes'] = summary.get('hot_themes', [])
        combined['short_candidates'] = summary.get('short_candidates', [])

# Load each raw data file
raw_files = [
    'themes',
    'momentum',
    'reddit',
    'news',
    'sectors',
    'finviz_signals',
    'google_trends',
    'short_interest',
    'options_activity',
    'perplexity',
    'insider_trading',
    'combined',
    'bearish_momentum',
    'fundamentals',
    'short_candidates',
]

for name in raw_files:
    file_path = raw_dir / f"{name}.json"
    if file_path.exists():
        try:
            with open(file_path) as f:
                data = json.load(f)
                # Limit large arrays to prevent token overflow
                if isinstance(data, list) and len(data) > 50:
                    combined[f'raw_{name}'] = data[:50]
                    combined[f'raw_{name}_note'] = f"Showing top 50 of {len(data)} total"
                else:
                    combined[f'raw_{name}'] = data
        except:
            pass

# Add summary note
file_counts = {name: len(combined.get(f'raw_{name}', [])) if isinstance(combined.get(f'raw_{name}'), list) else 'dict' for name in raw_files}
combined['_data_summary'] = {
    'source': str(raw_dir),
    'file_counts': file_counts
}

print(json.dumps(combined, indent=2, default=str))
PYEOF
)

    if [[ -z "$RAW_DATA" ]]; then
        echo -e "${YELLOW}Failed to load raw data, falling back to summary${NC}"
        RAW_DATA=$(cat "$REPORT_FILE")
    fi
else
    RAW_DATA=$(cat "$REPORT_FILE")
fi

FULL_PROMPT="$PROMPT

$RAW_DATA"

echo -e "${YELLOW}Calling Gemini for deep-dive analysis...${NC}"
echo -e "${YELLOW}(Sending $(echo "$RAW_DATA" | wc -c | tr -d ' ') bytes of data)${NC}"
echo ""

# Call Gemini CLI - pipe prompt via stdin
ANALYSIS=$(echo "$FULL_PROMPT" | "$GEMINI_CMD" --model gemini-3-pro-preview 2>/dev/null)
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 || -z "$ANALYSIS" ]]; then
    echo -e "${RED}Gemini analysis failed (exit code: $EXIT_CODE)${NC}"
    exit 1
fi

# Clean the response - remove markdown code blocks using Python for reliability
CLEAN_JSON=$(echo "$ANALYSIS" | python3 -c '
import sys
import re

text = sys.stdin.read()

# Remove markdown code blocks
text = re.sub(r"^```json\s*\n?", "", text, flags=re.MULTILINE)
text = re.sub(r"^```\s*\n?", "", text, flags=re.MULTILINE)
text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
text = text.strip()

# Find the JSON object
match = re.search(r"\{.*\}", text, re.DOTALL)
if match:
    print(match.group(0))
else:
    print(text)
')

# Validate JSON
if ! echo "$CLEAN_JSON" | python3 -m json.tool > /dev/null 2>&1; then
    echo -e "${RED}Warning: Response is not valid JSON. Saving raw output.${NC}"
    echo "$ANALYSIS" > "$OUTPUT_JSON"
    echo "Raw output saved to: $OUTPUT_JSON"
    exit 1
fi

# Save JSON
echo "$CLEAN_JSON" > "$OUTPUT_JSON"
echo -e "${GREEN}JSON saved to: $OUTPUT_JSON${NC}"

# Generate HTML report
echo -e "${YELLOW}Generating HTML report...${NC}"

python3 << PYTHON_SCRIPT
import json
import sys
from datetime import datetime
from pathlib import Path

# Read the analysis JSON
with open("$OUTPUT_JSON", "r") as f:
    data = json.load(f)

# Read original report for additional context
with open("$REPORT_FILE", "r") as f:
    report = json.load(f)

# Read raw data summary if available
raw_data_dir = "$LATEST_RAW_DIR" if "$USE_RAW_DATA" == "true" else None
raw_data_summary = {}
if raw_data_dir:
    try:
        summary_file = Path(raw_data_dir) / "_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                raw_data_summary = json.load(f)
    except:
        pass

date_str = "$DATE_STR"
time_str = "$TIME_STR"

def verdict_color(verdict):
    v = verdict.upper()
    if "STRONG BUY" in v: return "#3fb950"
    if "BUY" in v: return "#58a6ff"
    if "HOLD" in v: return "#d29922"
    if "STRONG SELL" in v: return "#f85149"
    if "SELL" in v: return "#f85149"
    return "#8b949e"

def verdict_bg(verdict):
    v = verdict.upper()
    if "STRONG BUY" in v: return "rgba(63,185,80,0.15)"
    if "BUY" in v: return "rgba(88,166,255,0.15)"
    if "HOLD" in v: return "rgba(210,153,34,0.15)"
    if "STRONG SELL" in v: return "rgba(248,81,73,0.15)"
    if "SELL" in v: return "rgba(248,81,73,0.15)"
    return "rgba(139,148,158,0.1)"

def bias_color(bias):
    b = bias.lower()
    if "bullish" in b: return "#3fb950"
    if "bearish" in b: return "#f85149"
    return "#d29922"

def confidence_badge(conf):
    c = conf.lower()
    if "high" in c: return ('<span class="badge badge-green">HIGH</span>')
    if "medium" in c: return ('<span class="badge badge-orange">MEDIUM</span>')
    return ('<span class="badge badge-muted">LOW</span>')

def sentiment_icon(sent):
    if not sent or sent == "N/A": return "—"
    s = sent.lower()
    if "bullish" in s or "positive" in s: return '<span style="color:#3fb950">▲</span>'
    if "bearish" in s or "negative" in s: return '<span style="color:#f85149">▼</span>'
    return '<span style="color:#8b949e">●</span>'

def risk_color(level):
    l = level.lower() if level else "low"
    if "high" in l: return "#f85149"
    if "medium" in l: return "#d29922"
    return "#3fb950"

exec_summary = data.get("executive_summary", {})
sector_analysis = data.get("sector_analysis", {})
deep_dives = data.get("deep_dives", [])
avoid_list = data.get("avoid_list", [])
market_risks = data.get("market_risks", [])
trading_plan = data.get("trading_plan", {})
hidden_gems = data.get("hidden_gems", [])
squeeze_watch = data.get("squeeze_watch", [])
breakout_watch = data.get("breakout_watch", [])
short_deep_dives = data.get("short_deep_dives", [])
pair_trades = data.get("pair_trades", [])
hot_themes = report.get("hot_themes", [])
discovery_stats = report.get("discovery_stats", {})
raw_data_dir = report.get("raw_data_dir", None)

# Get raw data counts if available
raw_file_counts = raw_data_summary.get("data_counts", {})

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Intelligence Report - {date_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Syne:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg-deep: #05080f;
    --bg: #0a0f1a;
    --surface: #0f1629;
    --surface2: #141d33;
    --surface3: #1a2540;
    --border: #243352;
    --border-glow: rgba(99, 179, 237, 0.15);
    --text: #f0f4fc;
    --text-muted: #7a8ba8;
    --accent: #63b3ed;
    --accent-bright: #90cdf4;
    --green: #48bb78;
    --green-glow: rgba(72, 187, 120, 0.4);
    --orange: #ed8936;
    --orange-glow: rgba(237, 137, 54, 0.4);
    --red: #fc8181;
    --purple: #b794f4;
    --purple-glow: rgba(183, 148, 244, 0.4);
    --cyan: #4fd1c5;
    --pink: #f687b3;
    --gradient-1: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --gradient-2: linear-gradient(135deg, #48bb78 0%, #38b2ac 100%);
    --gradient-3: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
    --gradient-4: linear-gradient(135deg, #b794f4 0%, #9f7aea 100%);
    --noise: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg-deep);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    line-height: 1.6;
    padding: 3rem 2rem;
    max-width: 1400px;
    margin: 0 auto;
    min-height: 100vh;
    position: relative;
  }}

  body::before {{
    content: '';
    position: fixed;
    inset: 0;
    background: var(--noise);
    pointer-events: none;
    z-index: 1000;
  }}

  body::after {{
    content: '';
    position: fixed;
    top: -50%;
    right: -30%;
    width: 80%;
    height: 80%;
    background: radial-gradient(ellipse, rgba(99, 179, 237, 0.08) 0%, transparent 60%);
    pointer-events: none;
  }}

  @keyframes fadeSlideIn {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}

  @keyframes pulseGlow {{
    0%, 100% {{ box-shadow: 0 0 20px rgba(99, 179, 237, 0.1); }}
    50% {{ box-shadow: 0 0 30px rgba(99, 179, 237, 0.2); }}
  }}

  @keyframes shimmer {{
    0% {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
  }}

  h1 {{
    font-family: 'Syne', sans-serif;
    font-size: 2.8rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--text) 0%, var(--accent-bright) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: fadeSlideIn 0.8s ease-out;
  }}

  h1 span {{
    font-weight: 400;
    background: linear-gradient(135deg, var(--text-muted) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    background-clip: text;
  }}

  .subtitle {{
    font-family: 'DM Sans', sans-serif;
    color: var(--text-muted);
    font-size: 1rem;
    margin-bottom: 3rem;
    animation: fadeSlideIn 0.8s ease-out 0.1s both;
  }}

  .section {{
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface2) 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
    animation: fadeSlideIn 0.6s ease-out both;
  }}

  .section::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: var(--noise);
    opacity: 0.5;
    pointer-events: none;
  }}

  .section:nth-child(1) {{ animation-delay: 0.1s; }}
  .section:nth-child(2) {{ animation-delay: 0.2s; }}
  .section:nth-child(3) {{ animation-delay: 0.3s; }}
  .section:nth-child(4) {{ animation-delay: 0.4s; }}
  .section:nth-child(5) {{ animation-delay: 0.5s; }}

  .section-title {{
    font-family: 'Syne', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 1.25rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    position: relative;
    z-index: 1;
  }}

  .section-title .icon {{
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
  }}

  .badge {{
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .badge-green {{ background: linear-gradient(135deg, rgba(72,187,120,0.2) 0%, rgba(72,187,120,0.1) 100%); color: var(--green); border: 1px solid rgba(72,187,120,0.3); }}
  .badge-orange {{ background: linear-gradient(135deg, rgba(237,137,54,0.2) 0%, rgba(237,137,54,0.1) 100%); color: var(--orange); border: 1px solid rgba(237,137,54,0.3); }}
  .badge-red {{ background: linear-gradient(135deg, rgba(252,129,129,0.2) 0%, rgba(252,129,129,0.1) 100%); color: var(--red); border: 1px solid rgba(252,129,129,0.3); }}
  .badge-blue {{ background: linear-gradient(135deg, rgba(99,179,237,0.2) 0%, rgba(99,179,237,0.1) 100%); color: var(--accent); border: 1px solid rgba(99,179,237,0.3); }}
  .badge-muted {{ background: linear-gradient(135deg, rgba(122,139,168,0.2) 0%, rgba(122,139,168,0.1) 100%); color: var(--text-muted); border: 1px solid rgba(122,139,168,0.3); }}

  /* Executive Summary */
  .exec-grid {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1.5rem;
    position: relative;
    z-index: 1;
  }}

  .exec-main {{
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
  }}

  .exec-stats {{
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }}

  .stat-card {{
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    text-align: center;
    transition: all 0.3s ease;
  }}

  .stat-card:hover {{
    border-color: var(--accent);
    transform: translateY(-2px);
  }}

  .stat-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }}

  .stat-value {{
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    margin-top: 0.35rem;
  }}

  .themes-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin-top: 1rem;
  }}

  .theme-tag {{
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    transition: all 0.2s ease;
  }}

  .theme-tag:hover {{
    border-color: var(--green);
    transform: translateX(4px);
  }}

  .theme-tag .pct {{
    color: var(--green);
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
  }}

  /* Deep Dive Cards */
  .deep-dive {{
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    margin-bottom: 1.5rem;
    overflow: hidden;
    position: relative;
    transition: all 0.3s ease;
  }}

  .deep-dive:hover {{
    border-color: var(--border-glow);
    transform: translateY(-2px);
  }}

  .deep-dive::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--gradient-1);
  }}

  .dd-header {{
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
  }}

  .dd-ticker-group {{
    display: flex;
    align-items: center;
    gap: 1rem;
  }}

  .dd-ticker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
    background: var(--gradient-1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}

  .dd-company {{
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    color: var(--text-muted);
  }}

  .dd-verdict {{
    padding: 0.5rem 1rem;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .dd-body {{
    padding: 1.5rem;
  }}

  .dd-thesis {{
    font-size: 0.95rem;
    line-height: 1.8;
    margin-bottom: 1.5rem;
    padding: 1rem 1.25rem;
    background: var(--bg);
    border-radius: 12px;
    border-left: 4px solid var(--accent);
    position: relative;
  }}

  .dd-thesis::before {{
    content: '"';
    position: absolute;
    top: -0.5rem;
    left: 1rem;
    font-family: 'Syne', sans-serif;
    font-size: 3rem;
    color: var(--accent);
    opacity: 0.3;
  }}

  .dd-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
  }}

  .dd-box {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    transition: all 0.2s ease;
  }}

  .dd-box:hover {{
    border-color: var(--accent);
  }}

  .dd-box h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.75rem;
  }}

  .dd-box .content {{
    font-size: 0.85rem;
    color: var(--text);
    line-height: 1.6;
  }}

  .dd-box .content.green {{ color: var(--green); }}
  .dd-box .content.red {{ color: var(--red); }}

  /* Company Description */
  .dd-company-desc {{
    margin-bottom: 1.5rem;
    padding: 1rem 1.25rem;
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
  }}

  .company-about {{
    font-size: 0.9rem;
    color: var(--text-muted);
    line-height: 1.7;
  }}

  /* Probability Assessment */
  .dd-probability {{
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-bottom: 1.5rem;
    padding: 1.25rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
  }}

  .prob-gauge {{
    flex-shrink: 0;
  }}

  .prob-circle {{
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: conic-gradient(var(--prob-color) calc(var(--prob-value, 65) * 3.6deg), var(--surface2) 0);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    box-shadow: 0 0 20px rgba(72, 187, 120, 0.3);
  }}

  .prob-circle::before {{
    content: '';
    position: absolute;
    inset: 8px;
    background: var(--bg);
    border-radius: 50%;
  }}

  .prob-value {{
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--text);
    position: relative;
    z-index: 1;
  }}

  .prob-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    position: relative;
    z-index: 1;
  }}

  .prob-details {{
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }}

  .prob-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(36, 51, 82, 0.5);
  }}

  .prob-row:last-child {{
    border-bottom: none;
  }}

  .prob-key {{
    font-size: 0.85rem;
    color: var(--text-muted);
  }}

  .prob-val {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
  }}

  /* Why Bullish Section */
  .dd-why-bullish {{
    margin-bottom: 1.25rem;
    padding: 1.25rem;
    background: linear-gradient(135deg, rgba(72,187,120,0.1) 0%, rgba(72,187,120,0.03) 100%);
    border: 1px solid rgba(72,187,120,0.25);
    border-radius: 12px;
    position: relative;
  }}

  .dd-why-bullish::before {{
    content: '▲';
    position: absolute;
    top: 1rem;
    right: 1rem;
    font-size: 1.5rem;
    color: var(--green);
    opacity: 0.3;
  }}

  .dd-why-bullish h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--green);
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .dd-why-bullish p {{
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--text);
  }}

  /* Rationale Section */
  .dd-rationale {{
    margin-bottom: 1.25rem;
    padding: 1.25rem;
    background: linear-gradient(135deg, rgba(99,179,237,0.1) 0%, rgba(99,179,237,0.03) 100%);
    border: 1px solid rgba(99,179,237,0.25);
    border-radius: 12px;
    position: relative;
  }}

  .dd-rationale::before {{
    content: '◈';
    position: absolute;
    top: 1rem;
    right: 1rem;
    font-size: 1.5rem;
    color: var(--accent);
    opacity: 0.3;
  }}

  .dd-rationale h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .dd-rationale p {{
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--text);
  }}

  /* Exit Strategy Section */
  .dd-exit-strategy {{
    margin-bottom: 1.25rem;
    padding: 1.25rem;
    background: linear-gradient(135deg, rgba(79,209,197,0.1) 0%, rgba(79,209,197,0.03) 100%);
    border: 1px solid rgba(79,209,197,0.25);
    border-radius: 12px;
  }}

  .dd-exit-strategy h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--cyan);
    margin-bottom: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .exit-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
  }}

  .exit-item {{
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem;
    background: var(--bg);
    border-radius: 8px;
    border: 1px solid var(--border);
  }}

  .exit-icon {{
    font-size: 1.25rem;
    flex-shrink: 0;
  }}

  .exit-content {{
    flex: 1;
  }}

  .exit-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.25rem;
  }}

  .exit-value {{
    font-size: 0.85rem;
    color: var(--text);
    line-height: 1.4;
  }}

  .exit-value.green {{
    color: var(--green);
  }}

  /* If Wrong Section */
  .dd-if-wrong {{
    margin-bottom: 1.25rem;
    padding: 1.25rem;
    background: linear-gradient(135deg, rgba(252,129,129,0.1) 0%, rgba(252,129,129,0.03) 100%);
    border: 1px solid rgba(252,129,129,0.25);
    border-radius: 12px;
    position: relative;
  }}

  .dd-if-wrong h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--red);
    margin-bottom: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .if-wrong-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
  }}

  .warning-signs, .exit-triggers {{
    padding: 1rem;
    background: var(--bg);
    border-radius: 8px;
    border: 1px solid var(--border);
  }}

  .warning-header, .trigger-header {{
    font-family: 'Syne', sans-serif;
    font-size: 0.8rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
  }}

  .warning-header {{
    color: var(--orange);
  }}

  .trigger-header {{
    color: var(--red);
  }}

  .warning-signs ul, .exit-triggers ul {{
    list-style: none;
    margin: 0;
    padding: 0;
  }}

  .warning-signs li, .exit-triggers li {{
    font-size: 0.85rem;
    padding: 0.35rem 0;
    padding-left: 1rem;
    position: relative;
    color: var(--text-muted);
    line-height: 1.4;
  }}

  .warning-signs li::before {{
    content: "•";
    position: absolute;
    left: 0;
    color: var(--orange);
  }}

  .exit-triggers li::before {{
    content: "×";
    position: absolute;
    left: 0;
    color: var(--red);
    font-weight: bold;
  }}

  .max-loss {{
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .loss-label {{
    font-size: 0.8rem;
    color: var(--text-muted);
  }}

  .loss-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--red);
  }}

  .invalidation {{
    padding: 0.75rem 1rem;
    background: var(--bg);
    border-radius: 8px;
    border-left: 3px solid var(--red);
    font-size: 0.85rem;
    color: var(--text-muted);
  }}

  .invalidation strong {{
    color: var(--red);
  }}

  .dd-levels {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-top: 0.75rem;
  }}

  .level-item {{
    text-align: center;
    padding: 0.75rem;
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border-radius: 8px;
    border: 1px solid var(--border);
  }}

  .level-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }}

  .level-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
    font-weight: 600;
    margin-top: 0.3rem;
  }}

  .level-value.support {{ color: var(--green); }}
  .level-value.resistance {{ color: var(--red); }}
  .level-value.stop {{ color: var(--orange); }}

  .dd-sentiment {{
    display: flex;
    gap: 1.25rem;
    margin-top: 0.75rem;
  }}

  .sent-item {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
  }}

  .dd-action {{
    margin-top: 1.5rem;
    padding: 1.25rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    position: relative;
    overflow: hidden;
  }}

  .dd-action::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--gradient-2);
  }}

  .dd-action h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--green);
    margin-bottom: 1rem;
  }}

  .action-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    text-align: center;
  }}

  .action-item .label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  .action-item .value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
    font-weight: 600;
    margin-top: 0.3rem;
  }}

  .dd-scores {{
    margin-top: 1.25rem;
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }}

  .score-pill {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.65rem;
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.75rem;
    transition: all 0.2s ease;
  }}

  .score-pill:hover {{
    border-color: var(--accent);
  }}

  .score-pill .score-name {{ color: var(--text-muted); }}
  .score-pill .score-val {{ font-weight: 600; font-family: 'JetBrains Mono', monospace; color: var(--accent); }}

  /* Avoid List */
  .avoid-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
    position: relative;
    z-index: 1;
  }}

  .avoid-card {{
    background: linear-gradient(145deg, rgba(252,129,129,0.08) 0%, rgba(252,129,129,0.03) 100%);
    border: 1px solid rgba(252,129,129,0.25);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    transition: all 0.2s ease;
  }}

  .avoid-card:hover {{
    border-color: var(--red);
    transform: translateX(4px);
  }}

  .avoid-card .ticker {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--red);
  }}

  .avoid-card .reason {{
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.4rem;
    line-height: 1.5;
  }}

  .avoid-card .risk-type {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--red);
    margin-top: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    opacity: 0.8;
  }}

  /* Risks */
  .risk-list {{
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    position: relative;
    z-index: 1;
  }}

  .risk-item {{
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 1rem 1.25rem;
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    transition: all 0.2s ease;
  }}

  .risk-item:hover {{
    border-color: var(--orange);
    transform: translateX(4px);
  }}

  .risk-severity {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-top: 0.35rem;
    flex-shrink: 0;
    box-shadow: 0 0 10px currentColor;
  }}

  .risk-content {{
    flex: 1;
  }}

  .risk-content .risk-text {{
    font-size: 0.9rem;
    line-height: 1.5;
  }}

  .risk-content .risk-hedge {{
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.35rem;
  }}

  /* Trading Plan */
  .plan-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.25rem;
    position: relative;
    z-index: 1;
  }}

  .plan-box {{
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    transition: all 0.2s ease;
  }}

  .plan-box:hover {{
    border-color: var(--cyan);
  }}

  .plan-box h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--cyan);
    margin-bottom: 0.75rem;
  }}

  .plan-box ul {{
    list-style: none;
    font-size: 0.85rem;
  }}

  .plan-box li {{
    padding: 0.35rem 0;
    padding-left: 1.25rem;
    position: relative;
    transition: all 0.2s ease;
  }}

  .plan-box li:hover {{
    color: var(--cyan);
    transform: translateX(4px);
  }}

  .plan-box li::before {{
    content: "→";
    position: absolute;
    left: 0;
    color: var(--cyan);
    opacity: 0.6;
  }}

  .key-levels-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
  }}

  .key-level {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.75rem;
    text-align: center;
    transition: all 0.2s ease;
  }}

  .key-level:hover {{
    border-color: var(--accent);
  }}

  .key-level .sym {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 0.95rem;
  }}

  .key-level .levels {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-top: 0.35rem;
  }}

  .key-level .levels .sup {{ color: var(--green); }}
  .key-level .levels .res {{ color: var(--red); }}

  /* Sector Analysis */
  .sector-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    position: relative;
    z-index: 1;
  }}

  .sector-column h4 {{
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  .sector-column.leading h4 {{ color: var(--green); }}
  .sector-column.lagging h4 {{ color: var(--red); }}

  .sector-item {{
    background: linear-gradient(145deg, var(--surface2) 0%, var(--surface3) 100%);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s ease;
  }}

  .sector-item:hover {{
    transform: translateX(4px);
  }}

  .sector-column.leading .sector-item:hover {{
    border-color: var(--green);
  }}

  .sector-column.lagging .sector-item:hover {{
    border-color: var(--red);
  }}

  .sector-item .name {{
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 0.9rem;
  }}

  .sector-item .reason {{
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    line-height: 1.4;
  }}

  .rotation-note {{
    margin-top: 1.5rem;
    padding: 1rem 1.25rem;
    background: linear-gradient(135deg, rgba(99,179,237,0.1) 0%, rgba(99,179,237,0.05) 100%);
    border: 1px solid rgba(99,179,237,0.25);
    border-radius: 12px;
    font-size: 0.9rem;
    position: relative;
    z-index: 1;
  }}

  .rotation-note strong {{
    color: var(--accent);
  }}

  .footer {{
    text-align: center;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    padding: 2rem 0;
    border-top: 1px solid var(--border);
    margin-top: 3rem;
    position: relative;
  }}

  .footer::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 100px;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
  }}

  @media (max-width: 900px) {{
    body {{ padding: 1.5rem 1rem; }}
    h1 {{ font-size: 2rem; }}
    .exec-grid, .dd-grid, .plan-grid, .sector-grid {{ grid-template-columns: 1fr; }}
    .action-grid {{ grid-template-columns: repeat(3, 1fr); }}
  }}
</style>
</head>
<body>

<h1>Market Intelligence Report <span>/ {date_str}</span></h1>
<p class="subtitle">AI-powered deep-dive analysis generated at {time_str} via Gemini</p>
'''

# Executive Summary Section
bias = exec_summary.get("overall_bias", "neutral")
bias_c = bias_color(bias)
regime = exec_summary.get("market_regime", "Unknown")
key_insight = exec_summary.get("key_insight", "")
confidence = exec_summary.get("confidence", "medium")
dominant_themes = exec_summary.get("dominant_themes", [])

html += f'''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(88,166,255,0.2);color:var(--accent);">◉</span>
    Executive Summary
  </div>
  <div class="exec-grid">
    <div class="exec-main">
      <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;">MARKET REGIME</div>
      <div style="font-size:1.1rem;font-weight:600;margin-bottom:0.75rem;">{regime}</div>
      <div style="font-size:0.85rem;line-height:1.6;">{key_insight}</div>
      <div class="themes-row">
        <span style="font-size:0.75rem;color:var(--text-muted);margin-right:0.5rem;">Hot Themes:</span>
'''

for theme in hot_themes[:5]:
    theme_name = theme.get("theme", "").replace("_", " ").title()
    avg_1m = theme.get("avg_1m", 0)
    html += f'<span class="theme-tag">{theme_name} <span class="pct">+{avg_1m:.1f}%</span></span>'

html += f'''
      </div>
    </div>
    <div class="exec-stats">
      <div class="stat-card">
        <div class="stat-label">Overall Bias</div>
        <div class="stat-value" style="color:{bias_c}">{bias.upper()}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Confidence</div>
        <div class="stat-value">{confidence_badge(confidence)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Tickers Analyzed</div>
        <div class="stat-value" style="color:var(--accent)">{discovery_stats.get("total_unique", 0)}</div>
      </div>
    </div>
  </div>
'''

# Add raw data sources summary if available
if raw_file_counts:
    html += '''
  <div style="margin-top:1rem;padding:1rem;background:var(--bg);border-radius:8px;border:1px solid var(--border);position:relative;z-index:1;">
    <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">Raw Data Sources Used</div>
    <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
'''
    for source, count in raw_file_counts.items():
        if count and count != 'dict' and count > 0:
            html += f'<span style="font-size:0.75rem;padding:0.25rem 0.5rem;background:var(--surface2);border-radius:4px;border:1px solid var(--border);"><span style="color:var(--text-muted);">{source}:</span> <span style="color:var(--accent);font-family:JetBrains Mono,monospace;">{count}</span></span>'
        elif count == 'dict':
            html += f'<span style="font-size:0.75rem;padding:0.25rem 0.5rem;background:var(--surface2);border-radius:4px;border:1px solid var(--border);"><span style="color:var(--text-muted);">{source}:</span> <span style="color:var(--green);font-family:JetBrains Mono,monospace;">loaded</span></span>'
    html += '''
    </div>
  </div>
'''

# Macro Context Bar
macro = exec_summary.get("macro_context", {})
if macro:
    html += '''
  <div style="margin-top:1rem;padding:1.25rem;background:linear-gradient(145deg,var(--surface2) 0%,var(--surface3) 100%);border-radius:12px;border:1px solid var(--border);position:relative;z-index:1;">
    <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.75rem;">Macro Environment</div>
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.75rem;">
'''
    macro_items = [
        ("VIX", macro.get("vix_assessment", "N/A"), "var(--orange)"),
        ("YIELDS", macro.get("yield_environment", "N/A"), "var(--accent)"),
        ("DOLLAR", macro.get("dollar_trend", "N/A"), "var(--cyan)"),
        ("CREDIT", macro.get("credit_conditions", "N/A"), "var(--green)"),
        ("BREADTH", macro.get("market_breadth", "N/A"), "var(--purple)"),
    ]
    for label, value, color in macro_items:
        html += f'''
      <div style="text-align:center;padding:0.5rem;background:var(--bg);border-radius:8px;border:1px solid var(--border);">
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;">{label}</div>
        <div style="font-size:0.8rem;color:{color};margin-top:0.25rem;line-height:1.3;">{value}</div>
      </div>
'''
    html += '''
    </div>
  </div>
'''

html += '''
</div>
'''

# Sector Analysis
leading = sector_analysis.get("leading_sectors", [])
lagging = sector_analysis.get("lagging_sectors", [])
rotation = sector_analysis.get("rotation_signal", "")

html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(188,140,255,0.2);color:var(--purple);">◐</span>
    Sector Analysis
  </div>
  <div class="sector-grid">
    <div class="sector-column leading">
      <h4>▲ Leading Sectors</h4>
'''

for s in leading[:4]:
    html += f'''
      <div class="sector-item">
        <div class="name">{s.get("sector", "")}</div>
        <div class="reason">{s.get("reason", "")}</div>
      </div>
'''

html += '''
    </div>
    <div class="sector-column lagging">
      <h4>▼ Lagging Sectors</h4>
'''

for s in lagging[:4]:
    html += f'''
      <div class="sector-item">
        <div class="name">{s.get("sector", "")}</div>
        <div class="reason">{s.get("reason", "")}</div>
      </div>
'''

html += f'''
    </div>
  </div>
  <div class="rotation-note">
    <strong>Rotation Signal:</strong> {rotation}
  </div>
</div>
'''

# Deep Dives
html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(63,185,80,0.2);color:var(--green);">◆</span>
    Deep Dive Analysis — Top Picks
  </div>
'''

for dd in deep_dives[:8]:
    ticker = dd.get("ticker", "???")
    company = dd.get("company", "")
    company_desc = dd.get("company_description", "")
    verdict = dd.get("verdict", "HOLD")
    conf = dd.get("confidence", "medium")
    thesis = dd.get("thesis", "")
    why_bullish = dd.get("why_bullish", "")
    rationale = dd.get("rationale", "")
    bull = dd.get("bull_case", "")
    bear = dd.get("bear_case", "")

    # Probability assessment
    prob = dd.get("probability", {})
    win_prob = prob.get("win_probability", 50)
    risk_reward = prob.get("risk_reward_ratio", "N/A")
    expected_move = prob.get("expected_move", "N/A")
    prob_timeframe = prob.get("timeframe", "N/A")

    tech = dd.get("technicals", {})
    trend = tech.get("trend", "N/A")
    momentum = tech.get("momentum", "N/A")
    vol_sig = tech.get("volume_signal", "N/A")
    levels = tech.get("key_levels", {})
    support = levels.get("support", "N/A")
    resistance = levels.get("resistance", "N/A")
    stop = levels.get("stop_loss", "N/A")

    sent = dd.get("sentiment", {})
    reddit_sent = sent.get("reddit", "N/A")
    news_sent = sent.get("news", "N/A")
    social_risk = sent.get("social_risk", "low")

    catalysts = dd.get("catalysts", [])
    risks = dd.get("risks", [])

    action = dd.get("action", {})
    entry = action.get("entry_zone", "N/A")
    target = action.get("target", "N/A")
    stop_loss = action.get("stop", "N/A")
    pos_size = action.get("position_size", "small")
    timeframe = action.get("timeframe", "swing")

    # Exit strategy
    exit_strat = dd.get("exit_strategy", {})
    profit_target = exit_strat.get("profit_target", "N/A")
    time_exit = exit_strat.get("time_exit", "N/A")
    trailing_stop = exit_strat.get("trailing_stop", "N/A")

    # If wrong - warning signs and exit triggers
    if_wrong = dd.get("if_wrong", {})
    warning_signs = if_wrong.get("warning_signs", [])
    exit_triggers = if_wrong.get("exit_triggers", [])
    max_loss = if_wrong.get("max_loss", "-8%")
    invalidation = if_wrong.get("invalidation", "N/A")

    scores = dd.get("score_breakdown", {})

    v_color = verdict_color(verdict)
    v_bg = verdict_bg(verdict)

    # Color for probability based on value
    prob_color = "#48bb78" if win_prob >= 65 else "#ed8936" if win_prob >= 50 else "#fc8181"

    html += f'''
  <div class="deep-dive">
    <div class="dd-header">
      <div class="dd-ticker-group">
        <span class="dd-ticker">{ticker}</span>
        <span class="dd-company">{company}</span>
        {confidence_badge(conf)}
      </div>
      <div class="dd-verdict" style="background:{v_bg};color:{v_color}">{verdict}</div>
    </div>
    <div class="dd-body">
      <!-- Company Description -->
      <div class="dd-company-desc">
        <div class="company-about">{company_desc}</div>
      </div>

      <!-- Probability Assessment -->
      <div class="dd-probability">
        <div class="prob-gauge">
          <div class="prob-circle" style="--prob-color:{prob_color}">
            <span class="prob-value">{win_prob}%</span>
            <span class="prob-label">Win Rate</span>
          </div>
        </div>
        <div class="prob-details">
          <div class="prob-row"><span class="prob-key">Risk/Reward</span><span class="prob-val">{risk_reward}</span></div>
          <div class="prob-row"><span class="prob-key">Expected Move</span><span class="prob-val" style="color:var(--green)">{expected_move}</span></div>
          <div class="prob-row"><span class="prob-key">Timeframe</span><span class="prob-val">{prob_timeframe}</span></div>
        </div>
      </div>

      <!-- Why Bullish -->
      <div class="dd-why-bullish">
        <h4>Why Bullish Now</h4>
        <p>{why_bullish}</p>
      </div>

      <!-- Rationale -->
      <div class="dd-rationale">
        <h4>Rationale</h4>
        <p>{rationale}</p>
      </div>

      <div class="dd-thesis">{thesis}</div>

      <div class="dd-grid">
        <div class="dd-box">
          <h4>Bull Case</h4>
          <div class="content green">{bull}</div>
        </div>
        <div class="dd-box">
          <h4>Bear Case</h4>
          <div class="content red">{bear}</div>
        </div>
        <div class="dd-box">
          <h4>Technicals</h4>
          <div class="content">
            Trend: <strong>{trend}</strong><br>
            Momentum: <strong>{momentum}</strong><br>
            Volume: <strong>{vol_sig}</strong>
          </div>
          <div class="dd-levels">
            <div class="level-item">
              <div class="level-label">Support</div>
              <div class="level-value support">{support}</div>
            </div>
            <div class="level-item">
              <div class="level-label">Resistance</div>
              <div class="level-value resistance">{resistance}</div>
            </div>
            <div class="level-item">
              <div class="level-label">Stop</div>
              <div class="level-value stop">{stop}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="dd-grid" style="margin-top:1rem;">
        <div class="dd-box">
          <h4>Catalysts</h4>
          <div class="content">{"<br>".join(["• " + c for c in catalysts[:3]]) if catalysts else "None identified"}</div>
        </div>
        <div class="dd-box">
          <h4>Risks</h4>
          <div class="content red">{"<br>".join(["• " + r for r in risks[:3]]) if risks else "Standard market risk"}</div>
        </div>
        <div class="dd-box">
          <h4>Sentiment</h4>
          <div class="dd-sentiment">
            <span class="sent-item">{sentiment_icon(reddit_sent)} Reddit</span>
            <span class="sent-item">{sentiment_icon(news_sent)} News</span>
            <span class="sent-item" style="color:{risk_color(social_risk)}">Crowd risk: {social_risk}</span>
          </div>
        </div>
      </div>

      <div class="dd-action">
        <h4>Trading Action</h4>
        <div class="action-grid">
          <div class="action-item">
            <div class="label">Entry Zone</div>
            <div class="value" style="color:var(--green)">{entry}</div>
          </div>
          <div class="action-item">
            <div class="label">Target</div>
            <div class="value" style="color:var(--accent)">{target}</div>
          </div>
          <div class="action-item">
            <div class="label">Stop Loss</div>
            <div class="value" style="color:var(--red)">{stop_loss}</div>
          </div>
          <div class="action-item">
            <div class="label">Position</div>
            <div class="value">{pos_size.upper()}</div>
          </div>
          <div class="action-item">
            <div class="label">Timeframe</div>
            <div class="value">{timeframe}</div>
          </div>
        </div>
      </div>

      <!-- Exit Strategy -->
      <div class="dd-exit-strategy">
        <h4>Exit Strategy</h4>
        <div class="exit-grid">
          <div class="exit-item">
            <div class="exit-icon">🎯</div>
            <div class="exit-content">
              <div class="exit-label">Profit Target</div>
              <div class="exit-value green">{profit_target}</div>
            </div>
          </div>
          <div class="exit-item">
            <div class="exit-icon">⏱</div>
            <div class="exit-content">
              <div class="exit-label">Time-Based Exit</div>
              <div class="exit-value">{time_exit}</div>
            </div>
          </div>
          <div class="exit-item">
            <div class="exit-icon">📈</div>
            <div class="exit-content">
              <div class="exit-label">Trailing Stop</div>
              <div class="exit-value">{trailing_stop}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- If Wrong Section -->
      <div class="dd-if-wrong">
        <h4>If Wrong — When to Exit</h4>
        <div class="if-wrong-grid">
          <div class="warning-signs">
            <div class="warning-header">⚠️ Warning Signs</div>
            <ul>{"".join([f"<li>{w}</li>" for w in warning_signs[:3]]) if warning_signs else "<li>Monitor for deteriorating momentum</li>"}
            </ul>
          </div>
          <div class="exit-triggers">
            <div class="trigger-header">🚨 Exit Triggers</div>
            <ul>{"".join([f"<li>{t}</li>" for t in exit_triggers[:2]]) if exit_triggers else "<li>Break of key support</li>"}
            </ul>
            <div class="max-loss">
              <span class="loss-label">Max Loss:</span>
              <span class="loss-value">{max_loss}</span>
            </div>
          </div>
        </div>
        <div class="invalidation">
          <strong>Thesis Invalidation:</strong> {invalidation}
        </div>
      </div>

      <div class="dd-scores">
'''

    for k, v in scores.items():
        html += f'<span class="score-pill"><span class="score-name">{k}:</span> <span class="score-val">{v}</span></span>'

    html += '''
      </div>
    </div>
  </div>
'''

html += '</div>'

# Hidden Gems Section
if hidden_gems:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(183,148,244,0.2);color:var(--purple);">💎</span>
    Hidden Gems — Under-the-Radar Picks
  </div>
  <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem;position:relative;z-index:1;">
    Small and mid-cap stocks showing unusual activity that may be overlooked by the mainstream. Higher risk, higher potential reward.
  </p>
'''
    for gem in hidden_gems[:8]:
        ticker = gem.get("ticker", "???")
        company = gem.get("company", "")
        market_cap = gem.get("market_cap", "small-cap")
        why_overlooked = gem.get("why_overlooked", "")
        thesis = gem.get("thesis", "")
        catalyst = gem.get("catalyst", "")
        risk = gem.get("risk", "")
        entry = gem.get("entry_zone", "N/A")
        target = gem.get("target", "N/A")
        stop = gem.get("stop", "N/A")
        scores = gem.get("score_breakdown", {})

        html += f'''
  <div class="deep-dive" style="border-left:3px solid var(--purple);">
    <div class="dd-header">
      <div class="dd-ticker-group">
        <span class="dd-ticker" style="background:var(--gradient-4);-webkit-background-clip:text;background-clip:text;">{ticker}</span>
        <span class="dd-company">{company}</span>
        <span class="badge badge-muted">{market_cap.upper()}</span>
      </div>
      <span class="badge badge-blue">HIDDEN GEM</span>
    </div>
    <div class="dd-body">
      <div class="dd-why-bullish" style="background:linear-gradient(135deg,rgba(183,148,244,0.1) 0%,rgba(183,148,244,0.03) 100%);border-color:rgba(183,148,244,0.25);">
        <h4 style="color:var(--purple);">Why This Is Overlooked</h4>
        <p>{why_overlooked}</p>
      </div>
      <div class="dd-thesis">{thesis}</div>
      <div class="dd-grid">
        <div class="dd-box">
          <h4>Catalyst</h4>
          <div class="content green">{catalyst}</div>
        </div>
        <div class="dd-box">
          <h4>Main Risk</h4>
          <div class="content red">{risk}</div>
        </div>
        <div class="dd-box">
          <h4>Trade Setup</h4>
          <div class="dd-levels">
            <div class="level-item">
              <div class="level-label">Entry</div>
              <div class="level-value support">{entry}</div>
            </div>
            <div class="level-item">
              <div class="level-label">Target</div>
              <div class="level-value" style="color:var(--accent)">{target}</div>
            </div>
            <div class="level-item">
              <div class="level-label">Stop</div>
              <div class="level-value stop">{stop}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="dd-scores">
'''
        for k, v in scores.items():
            html += f'<span class="score-pill"><span class="score-name">{k}:</span> <span class="score-val">{v}</span></span>'
        html += '''
      </div>
    </div>
  </div>
'''
    html += '</div>'

# Squeeze Watch Section
if squeeze_watch:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(237,137,54,0.2);color:var(--orange);">🔥</span>
    Squeeze Watch — High Short Interest
  </div>
  <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem;position:relative;z-index:1;">
    Stocks with elevated short interest that could experience violent short covering rallies. Very high risk.
  </p>
  <div class="avoid-grid">
'''
    for sq in squeeze_watch[:5]:
        ticker = sq.get("ticker", "???")
        company = sq.get("company", "")
        short_float = sq.get("short_float", 0)
        dtc = sq.get("days_to_cover", 0)
        thesis = sq.get("squeeze_thesis", "")
        trigger = sq.get("trigger", "")
        risk_level = sq.get("risk_level", "high")
        notes = sq.get("notes", "")

        risk_c = "#f85149" if risk_level == "high" else "#ed8936" if risk_level == "medium" else "#48bb78"

        html += f'''
    <div class="avoid-card" style="background:linear-gradient(145deg,rgba(237,137,54,0.08) 0%,rgba(237,137,54,0.03) 100%);border-color:rgba(237,137,54,0.25);">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div class="ticker" style="color:var(--orange)">{ticker}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;">
          <span style="color:var(--red)">{short_float}% short</span> · <span style="color:var(--text-muted)">{dtc}d DTC</span>
        </div>
      </div>
      <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.25rem;">{company}</div>
      <div class="reason" style="margin-top:0.75rem;">{thesis}</div>
      <div style="font-size:0.8rem;margin-top:0.5rem;"><strong style="color:var(--cyan);">Trigger:</strong> {trigger}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.75rem;">
        <span class="risk-type" style="color:{risk_c}">{risk_level.upper()} RISK</span>
      </div>
    </div>
'''
    html += '''
  </div>
</div>
'''

# Breakout Watch Section
if breakout_watch:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(79,209,197,0.2);color:var(--cyan);">📈</span>
    Breakout Watch — Technical Setups
  </div>
  <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem;position:relative;z-index:1;">
    Stocks showing bullish technical patterns that could break out with volume confirmation.
  </p>
  <div class="avoid-grid">
'''
    for bo in breakout_watch[:5]:
        ticker = bo.get("ticker", "???")
        company = bo.get("company", "")
        pattern = bo.get("pattern", "")
        breakout_level = bo.get("breakout_level", "N/A")
        volume_conf = bo.get("volume_confirmation", "")
        target = bo.get("target_on_breakout", "N/A")
        notes = bo.get("notes", "")

        html += f'''
    <div class="avoid-card" style="background:linear-gradient(145deg,rgba(79,209,197,0.08) 0%,rgba(79,209,197,0.03) 100%);border-color:rgba(79,209,197,0.25);">
      <div class="ticker" style="color:var(--cyan)">{ticker}</div>
      <div style="font-size:0.8rem;color:var(--text-muted);">{company}</div>
      <div class="reason" style="margin-top:0.75rem;"><strong>Pattern:</strong> {pattern}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-top:0.75rem;font-size:0.8rem;">
        <div><span style="color:var(--text-muted);">Break above:</span> <span style="color:var(--green);font-family:'JetBrains Mono',monospace;">{breakout_level}</span></div>
        <div><span style="color:var(--text-muted);">Target:</span> <span style="color:var(--cyan);font-family:'JetBrains Mono',monospace;">{target}</span></div>
      </div>
      <div style="font-size:0.8rem;margin-top:0.5rem;color:var(--text-muted);"><strong>Volume:</strong> {volume_conf}</div>
    </div>
'''
    html += '''
  </div>
</div>
'''

# Short Deep Dives Section
if short_deep_dives:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(248,81,73,0.2);color:var(--red);">▼</span>
    Short Candidates — Bearish Deep Dives
  </div>
  <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem;position:relative;z-index:1;">
    Stocks showing technical breakdowns, fundamental deterioration, and bearish smart money flow. Smaller position sizes recommended — shorts carry unlimited risk.
  </p>
'''
    for sd in short_deep_dives[:6]:
        s_ticker = sd.get("ticker", "???")
        s_company = sd.get("company", "")
        s_company_desc = sd.get("company_description", "")
        s_verdict = sd.get("verdict", "SHORT")
        s_conf = sd.get("confidence", "medium")
        s_thesis = sd.get("thesis", "")
        s_why_bearish = sd.get("why_bearish", "")
        s_rationale = sd.get("rationale", "")
        s_bear_case = sd.get("bear_case", "")
        s_bull_risk = sd.get("bull_risk", "")
        s_short_score = sd.get("short_score", 0)

        s_prob = sd.get("probability", {})
        s_win_prob = s_prob.get("win_probability", 50)
        s_risk_reward = s_prob.get("risk_reward_ratio", "N/A")
        s_expected_move = s_prob.get("expected_move", "N/A")
        s_prob_timeframe = s_prob.get("timeframe", "N/A")

        s_tech = sd.get("technicals", {})
        s_trend = s_tech.get("trend", "N/A")
        s_momentum = s_tech.get("momentum", "N/A")
        s_vol_sig = s_tech.get("volume_signal", "N/A")
        s_levels = s_tech.get("key_levels", {})
        s_resistance = s_levels.get("resistance", "N/A")
        s_support_target = s_levels.get("support_target", "N/A")
        s_stop = s_levels.get("stop_loss", "N/A")

        s_squeeze = sd.get("squeeze_risk", {})
        s_sf_pct = s_squeeze.get("short_float_pct", 0)
        s_dtc = s_squeeze.get("days_to_cover", 0)
        s_sq_risk = s_squeeze.get("risk_level", "low")
        s_sq_warning = s_squeeze.get("squeeze_warning", "")

        s_signals = sd.get("bearish_signals", [])
        s_catalysts = sd.get("catalysts", [])

        s_action = sd.get("action", {})
        s_entry = s_action.get("entry_zone", "N/A")
        s_cover = s_action.get("cover_target", "N/A")
        s_stop_loss = s_action.get("stop_loss", "N/A")
        s_pos_size = s_action.get("position_size", "small")
        s_instrument = s_action.get("instrument", "short shares")
        s_timeframe = s_action.get("timeframe", "swing")

        s_if_wrong = sd.get("if_wrong", {})
        s_warnings = s_if_wrong.get("warning_signs", [])
        s_exit_triggers = s_if_wrong.get("exit_triggers", [])
        s_max_loss = s_if_wrong.get("max_loss", "-8%")
        s_invalidation = s_if_wrong.get("invalidation", "N/A")

        s_scores = sd.get("score_breakdown", {})

        s_prob_color = "#48bb78" if s_win_prob >= 65 else "#ed8936" if s_win_prob >= 50 else "#fc8181"
        s_sq_color = "#f85149" if s_sq_risk == "high" else "#d29922" if s_sq_risk == "medium" else "#3fb950"

        html += f'''
  <div class="deep-dive" style="border-left:3px solid var(--red);">
    <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(135deg,#f85149 0%,#d29922 100%);"></div>
    <div class="dd-header">
      <div class="dd-ticker-group">
        <span class="dd-ticker" style="background:linear-gradient(135deg,#f85149 0%,#d29922 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{s_ticker}</span>
        <span class="dd-company">{s_company}</span>
        {confidence_badge(s_conf)}
      </div>
      <div class="dd-verdict" style="background:rgba(248,81,73,0.15);color:#f85149">{s_verdict}</div>
    </div>
    <div class="dd-body">
      <!-- Company Description -->
      <div class="dd-company-desc">
        <div class="company-about">{s_company_desc}</div>
      </div>

      <!-- Probability Assessment -->
      <div class="dd-probability">
        <div class="prob-gauge">
          <div class="prob-circle" style="--prob-color:{s_prob_color}">
            <span class="prob-value">{s_win_prob}%</span>
            <span class="prob-label">Win Rate</span>
          </div>
        </div>
        <div class="prob-details">
          <div class="prob-row"><span class="prob-key">Risk/Reward</span><span class="prob-val">{s_risk_reward}</span></div>
          <div class="prob-row"><span class="prob-key">Expected Move</span><span class="prob-val" style="color:var(--red)">{s_expected_move}</span></div>
          <div class="prob-row"><span class="prob-key">Timeframe</span><span class="prob-val">{s_prob_timeframe}</span></div>
          <div class="prob-row"><span class="prob-key">Short Score</span><span class="prob-val" style="color:var(--red)">{s_short_score}</span></div>
        </div>
      </div>

      <!-- Why Bearish -->
      <div class="dd-why-bullish" style="background:linear-gradient(135deg,rgba(248,81,73,0.1) 0%,rgba(248,81,73,0.03) 100%);border-color:rgba(248,81,73,0.25);">
        <h4 style="color:var(--red);">Why Bearish Now</h4>
        <p>{s_why_bearish}</p>
      </div>

      <!-- Rationale -->
      <div class="dd-rationale" style="background:linear-gradient(135deg,rgba(210,153,34,0.1) 0%,rgba(210,153,34,0.03) 100%);border-color:rgba(210,153,34,0.25);">
        <h4 style="color:var(--orange);">Rationale</h4>
        <p>{s_rationale}</p>
      </div>

      <div class="dd-thesis" style="border-left-color:var(--red);">{s_thesis}</div>

      <div class="dd-grid">
        <div class="dd-box">
          <h4>Bear Case (Your Thesis)</h4>
          <div class="content red">{s_bear_case}</div>
        </div>
        <div class="dd-box">
          <h4>Bull Risk (What Could Go Wrong)</h4>
          <div class="content green">{s_bull_risk}</div>
        </div>
        <div class="dd-box">
          <h4>Technicals</h4>
          <div class="content">
            Trend: <strong>{s_trend}</strong><br>
            Momentum: <strong>{s_momentum}</strong><br>
            Volume: <strong>{s_vol_sig}</strong>
          </div>
          <div class="dd-levels">
            <div class="level-item">
              <div class="level-label">Resistance</div>
              <div class="level-value resistance">{s_resistance}</div>
            </div>
            <div class="level-item">
              <div class="level-label">Target</div>
              <div class="level-value support">{s_support_target}</div>
            </div>
            <div class="level-item">
              <div class="level-label">Stop (Cover)</div>
              <div class="level-value stop">{s_stop}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Squeeze Risk Warning -->
      <div style="margin-top:1rem;padding:1rem;background:linear-gradient(135deg,rgba(237,137,54,0.1) 0%,rgba(237,137,54,0.03) 100%);border:1px solid rgba(237,137,54,0.25);border-radius:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
          <span style="font-family:'Syne',sans-serif;font-size:0.85rem;font-weight:700;color:var(--orange);">SQUEEZE RISK</span>
          <span class="badge" style="background:{'rgba(248,81,73,0.2)' if s_sq_risk == 'high' else 'rgba(210,153,34,0.2)' if s_sq_risk == 'medium' else 'rgba(63,185,80,0.2)'};color:{s_sq_color};border:1px solid {s_sq_color};">{s_sq_risk.upper()}</span>
        </div>
        <div style="display:flex;gap:1.5rem;font-size:0.8rem;margin-bottom:0.5rem;">
          <span><span style="color:var(--text-muted);">Short Float:</span> <span style="color:var(--red);font-family:'JetBrains Mono',monospace;">{s_sf_pct}%</span></span>
          <span><span style="color:var(--text-muted);">Days to Cover:</span> <span style="font-family:'JetBrains Mono',monospace;">{s_dtc}d</span></span>
        </div>
        <div style="font-size:0.8rem;color:var(--text-muted);">{s_sq_warning}</div>
      </div>

      <div class="dd-grid" style="margin-top:1rem;">
        <div class="dd-box">
          <h4>Bearish Catalysts</h4>
          <div class="content red">{"<br>".join(["▼ " + c for c in s_catalysts[:3]]) if s_catalysts else "General deterioration"}</div>
        </div>
        <div class="dd-box">
          <h4>Bearish Signals</h4>
          <div class="content">{"<br>".join(["• " + s for s in s_signals[:4]]) if s_signals else "Multiple bearish indicators"}</div>
        </div>
        <div class="dd-box">
          <h4>Instrument</h4>
          <div class="content" style="text-align:center;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:600;color:var(--orange);margin-bottom:0.25rem;">{s_instrument.upper()}</div>
            <div style="font-size:0.8rem;color:var(--text-muted);">{s_timeframe} · {s_pos_size} size</div>
          </div>
        </div>
      </div>

      <div class="dd-action" style="border-top:none;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(135deg,#f85149 0%,#d29922 100%);"></div>
        <h4 style="color:var(--red);">Short Action Plan</h4>
        <div class="action-grid">
          <div class="action-item">
            <div class="label">Entry Zone</div>
            <div class="value" style="color:var(--red)">{s_entry}</div>
          </div>
          <div class="action-item">
            <div class="label">Cover Target</div>
            <div class="value" style="color:var(--green)">{s_cover}</div>
          </div>
          <div class="action-item">
            <div class="label">Stop Loss</div>
            <div class="value" style="color:var(--orange)">{s_stop_loss}</div>
          </div>
          <div class="action-item">
            <div class="label">Position</div>
            <div class="value">{s_pos_size.upper()}</div>
          </div>
          <div class="action-item">
            <div class="label">Timeframe</div>
            <div class="value">{s_timeframe}</div>
          </div>
        </div>
      </div>

      <!-- If Wrong Section -->
      <div class="dd-if-wrong">
        <h4>If Wrong — When to Cover</h4>
        <div class="if-wrong-grid">
          <div class="warning-signs">
            <div class="warning-header">Warning Signs</div>
            <ul>{"".join([f"<li>{w}</li>" for w in s_warnings[:3]]) if s_warnings else "<li>Monitor for reversal signals</li>"}
            </ul>
          </div>
          <div class="exit-triggers">
            <div class="trigger-header">Cover Triggers</div>
            <ul>{"".join([f"<li>{t}</li>" for t in s_exit_triggers[:2]]) if s_exit_triggers else "<li>Break above key resistance</li>"}
            </ul>
            <div class="max-loss">
              <span class="loss-label">Max Loss:</span>
              <span class="loss-value">{s_max_loss}</span>
            </div>
          </div>
        </div>
        <div class="invalidation">
          <strong>Thesis Invalidation:</strong> {s_invalidation}
        </div>
      </div>

      <div class="dd-scores">
'''
        for k, v in s_scores.items():
            html += f'<span class="score-pill"><span class="score-name">{k}:</span> <span class="score-val">{v}</span></span>'
        html += '''
      </div>
    </div>
  </div>
'''
    html += '</div>'

# Pair Trades Section
if pair_trades:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(99,179,237,0.2);color:var(--accent);">⇄</span>
    Pair Trades — Long/Short Combos
  </div>
  <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem;position:relative;z-index:1;">
    Market-neutral strategies pairing a strong long with a weak short in the same sector. Reduces directional risk while capturing relative value.
  </p>
'''
    for pt in pair_trades[:4]:
        pt_name = pt.get("pair_name", "Pair Trade")
        pt_sector = pt.get("sector", "")
        pt_rationale = pt.get("rationale", "")
        pt_spread = pt.get("spread_thesis", "")
        pt_risk = pt.get("risk", "")
        pt_corr = pt.get("correlation", "medium")
        pt_tf = pt.get("timeframe", "2-4 weeks")
        pt_net = pt.get("net_exposure", "market-neutral")

        long_leg = pt.get("long_leg", {})
        short_leg = pt.get("short_leg", {})

        l_ticker = long_leg.get("ticker", "???")
        l_company = long_leg.get("company", "")
        l_why = long_leg.get("why_long", "")
        l_entry = long_leg.get("entry", "N/A")
        l_target = long_leg.get("target", "N/A")

        sh_ticker = short_leg.get("ticker", "???")
        sh_company = short_leg.get("company", "")
        sh_why = short_leg.get("why_short", "")
        sh_entry = short_leg.get("entry", "N/A")
        sh_cover = short_leg.get("cover_target", "N/A")

        html += f'''
  <div class="deep-dive" style="border-left:3px solid var(--accent);">
    <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(135deg,#3fb950 0%,#63b3ed 50%,#f85149 100%);"></div>
    <div class="dd-header">
      <div class="dd-ticker-group">
        <span class="dd-ticker" style="background:linear-gradient(135deg,var(--green) 0%,var(--accent) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{l_ticker}</span>
        <span style="color:var(--text-muted);font-size:1.2rem;margin:0 0.25rem;">⇄</span>
        <span class="dd-ticker" style="background:linear-gradient(135deg,var(--red) 0%,var(--orange) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{sh_ticker}</span>
        <span class="dd-company">{pt_sector}</span>
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <span class="badge badge-blue">{pt_net.upper()}</span>
        <span class="badge badge-muted">{pt_tf}</span>
      </div>
    </div>
    <div class="dd-body">
      <div style="font-size:0.95rem;margin-bottom:1rem;color:var(--text);font-weight:600;">{pt_name}</div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;margin-bottom:1.25rem;">
        <!-- Long Leg -->
        <div style="padding:1.25rem;background:linear-gradient(135deg,rgba(63,185,80,0.08) 0%,rgba(63,185,80,0.03) 100%);border:1px solid rgba(63,185,80,0.25);border-radius:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;font-weight:700;color:var(--green);">▲ {l_ticker}</span>
            <span class="badge badge-green">LONG</span>
          </div>
          <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;">{l_company}</div>
          <div style="font-size:0.85rem;line-height:1.6;margin-bottom:0.75rem;">{l_why}</div>
          <div style="display:flex;gap:1rem;font-size:0.8rem;">
            <span><span style="color:var(--text-muted);">Entry:</span> <span style="color:var(--green);font-family:'JetBrains Mono',monospace;">{l_entry}</span></span>
            <span><span style="color:var(--text-muted);">Target:</span> <span style="color:var(--accent);font-family:'JetBrains Mono',monospace;">{l_target}</span></span>
          </div>
        </div>

        <!-- Short Leg -->
        <div style="padding:1.25rem;background:linear-gradient(135deg,rgba(248,81,73,0.08) 0%,rgba(248,81,73,0.03) 100%);border:1px solid rgba(248,81,73,0.25);border-radius:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;font-weight:700;color:var(--red);">▼ {sh_ticker}</span>
            <span class="badge badge-red">SHORT</span>
          </div>
          <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;">{sh_company}</div>
          <div style="font-size:0.85rem;line-height:1.6;margin-bottom:0.75rem;">{sh_why}</div>
          <div style="display:flex;gap:1rem;font-size:0.8rem;">
            <span><span style="color:var(--text-muted);">Entry:</span> <span style="color:var(--red);font-family:'JetBrains Mono',monospace;">{sh_entry}</span></span>
            <span><span style="color:var(--text-muted);">Cover:</span> <span style="color:var(--green);font-family:'JetBrains Mono',monospace;">{sh_cover}</span></span>
          </div>
        </div>
      </div>

      <div class="dd-grid">
        <div class="dd-box">
          <h4>Spread Thesis</h4>
          <div class="content">{pt_spread}</div>
        </div>
        <div class="dd-box">
          <h4>Pair Risk</h4>
          <div class="content red">{pt_risk}</div>
        </div>
        <div class="dd-box">
          <h4>Rationale</h4>
          <div class="content">{pt_rationale}</div>
        </div>
      </div>
    </div>
  </div>
'''
    html += '</div>'

# Avoid List
if avoid_list:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(248,81,73,0.2);color:var(--red);">⚠</span>
    Avoid List — Proceed with Caution
  </div>
  <div class="avoid-grid">
'''
    for item in avoid_list[:6]:
        html += f'''
    <div class="avoid-card">
      <div class="ticker">{item.get("ticker", "")}</div>
      <div class="reason">{item.get("reason", "")}</div>
      <div class="risk-type">{item.get("risk_type", "")}</div>
    </div>
'''
    html += '''
  </div>
</div>
'''

# Market Risks
if market_risks:
    html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(210,153,34,0.2);color:var(--orange);">⚡</span>
    Market Risks to Monitor
  </div>
  <div class="risk-list">
'''
    for risk in market_risks[:5]:
        sev = risk.get("severity", "low")
        sev_c = risk_color(sev)
        html += f'''
    <div class="risk-item">
      <div class="risk-severity" style="background:{sev_c}"></div>
      <div class="risk-content">
        <div class="risk-text">{risk.get("risk", "")}</div>
        <div class="risk-hedge"><strong>Hedge:</strong> {risk.get("hedge", "N/A")}</div>
      </div>
    </div>
'''
    html += '''
  </div>
</div>
'''

# Trading Plan
premarket = trading_plan.get("premarket_focus", [])
best_setups = trading_plan.get("best_setups", [])
key_lvls = trading_plan.get("key_levels", {})
avoid_times = trading_plan.get("avoid_times", "")
risk_limit = trading_plan.get("risk_limit", "")

html += '''
<div class="section">
  <div class="section-title">
    <span class="icon" style="background:rgba(57,210,192,0.2);color:var(--cyan);">✓</span>
    Trading Plan for Today
  </div>
  <div class="plan-grid">
    <div class="plan-box">
      <h4>Pre-Market Focus</h4>
      <ul>
'''
for item in premarket[:5]:
    html += f'<li>{item}</li>'

html += '''
      </ul>
    </div>
    <div class="plan-box">
      <h4>Best Setups</h4>
      <ul>
'''
for setup in best_setups[:5]:
    html += f'<li>{setup}</li>'

html += '''
      </ul>
    </div>
    <div class="plan-box">
      <h4>Key Index Levels</h4>
      <div class="key-levels-grid">
'''
for sym, lvls in key_lvls.items():
    sup = lvls.get("support", "N/A")
    res = lvls.get("resistance", "N/A")
    html += f'''
        <div class="key-level">
          <div class="sym">{sym}</div>
          <div class="levels"><span class="sup">S: {sup}</span> | <span class="res">R: {res}</span></div>
        </div>
'''

html += f'''
      </div>
    </div>
    <div class="plan-box">
      <h4>Risk Management</h4>
      <ul>
        <li><strong>Avoid:</strong> {avoid_times if avoid_times else "No specific times to avoid"}</li>
        <li><strong>Risk Limit:</strong> {risk_limit if risk_limit else "Standard position sizing"}</li>
      </ul>
    </div>
  </div>
</div>
'''

raw_data_note = f'<br>Raw scanner data: {raw_data_dir}' if raw_data_dir else ''
files_used = len(raw_data_summary.get("files_created", [])) if raw_data_summary else 0
files_note = f' ({files_used} data files analyzed)' if files_used else ''
html += f'''
<div class="footer">
  Generated by trending-stocks + Gemini AI — {date_str} {time_str}{files_note}{raw_data_note}
</div>

</body>
</html>
'''

# Write HTML file
with open("$OUTPUT_HTML", "w") as f:
    f.write(html)

print("HTML report generated successfully")
PYTHON_SCRIPT

if [[ $? -eq 0 ]]; then
    # Extract raw_data_dir from report if available
    RAW_DATA_DIR=$(python3 -c "import json; print(json.load(open('$REPORT_FILE')).get('raw_data_dir', 'N/A'))" 2>/dev/null || echo "N/A")

    echo ""
    echo -e "${GREEN}=============================================${NC}"
    echo -e "${GREEN}Analysis complete!${NC}"
    echo -e "${GREEN}HTML Report: $OUTPUT_HTML${NC}"
    echo -e "${GREEN}JSON Data:   $OUTPUT_JSON${NC}"
    if [[ "$RAW_DATA_DIR" != "N/A" && "$RAW_DATA_DIR" != "None" ]]; then
        echo -e "${YELLOW}Raw Data:    $RAW_DATA_DIR${NC}"
    fi
    echo -e "${GREEN}=============================================${NC}"

    # Open in browser
    if command -v open &> /dev/null; then
        open "$OUTPUT_HTML"
    fi
else
    echo -e "${RED}Failed to generate HTML report${NC}"
    exit 1
fi
