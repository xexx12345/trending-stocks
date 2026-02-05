#!/bin/bash
#
# analyze_hidden_gems.sh - Deep equity research report on hidden gems / small caps
#
# Generates institutional-quality buy-side research reports using Gemini
#
# Usage: ./analyze_hidden_gems.sh [report_file]
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="${1:-$SCRIPT_DIR/output/trending_report.json}"
RAW_DIR="$SCRIPT_DIR/output/raw"
DATE_STR=$(date +%Y-%m-%d)
TIME_STR=$(date +%H:%M)
OUTPUT_HTML="$SCRIPT_DIR/output/equity_research_${DATE_STR}.html"
OUTPUT_JSON="$SCRIPT_DIR/output/equity_research_${DATE_STR}.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       EQUITY RESEARCH REPORT - HIDDEN GEMS ANALYSIS       ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
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
    echo -e "${RED}Error: No raw data folder found. Run: python main.py${NC}"
    exit 1
fi
echo -e "${GREEN}Using raw data from: $LATEST_RAW_DIR${NC}"

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
    echo -e "${RED}Error: gemini CLI not found${NC}"
    exit 1
fi

# Build the research data focusing on hidden gems
echo -e "${YELLOW}Identifying hidden gem candidates...${NC}"

RESEARCH_DATA=$(python3 << 'PYEOF'
import json
from pathlib import Path

raw_dir = Path("$LATEST_RAW_DIR".replace("$LATEST_RAW_DIR", """$LATEST_RAW_DIR"""))
report_file = Path("$REPORT_FILE".replace("$REPORT_FILE", """$REPORT_FILE"""))

# Load all raw data
data = {}

# Load combined scores
combined_file = raw_dir / "combined.json"
if combined_file.exists():
    with open(combined_file) as f:
        data['combined'] = json.load(f)

# Load momentum data
momentum_file = raw_dir / "momentum.json"
if momentum_file.exists():
    with open(momentum_file) as f:
        data['momentum'] = json.load(f)

# Load other sources
for source in ['reddit', 'news', 'short_interest', 'options_activity', 'insider_trading', 'perplexity', 'google_trends', 'finviz_signals']:
    file_path = raw_dir / f"{source}.json"
    if file_path.exists():
        try:
            with open(file_path) as f:
                data[source] = json.load(f)
        except:
            pass

# Identify hidden gems: stocks NOT in top 10 combined but showing interesting signals
combined = data.get('combined', [])
top_10_tickers = set(s['ticker'] for s in combined[:10]) if combined else set()

# Find candidates from various sources
hidden_gem_candidates = {}

# From momentum: high score but not top 10
for stock in data.get('momentum', [])[10:50]:
    ticker = stock.get('ticker', '')
    if ticker and ticker not in top_10_tickers:
        if ticker not in hidden_gem_candidates:
            hidden_gem_candidates[ticker] = {'ticker': ticker, 'signals': [], 'data': {}}
        hidden_gem_candidates[ticker]['signals'].append(f"momentum_score: {stock.get('score', 0)}")
        hidden_gem_candidates[ticker]['data']['momentum'] = stock

# From short interest: squeeze candidates
for stock in data.get('short_interest', []):
    ticker = stock.get('ticker', '')
    if ticker and ticker not in top_10_tickers and stock.get('squeeze_risk') in ('high', 'medium'):
        if ticker not in hidden_gem_candidates:
            hidden_gem_candidates[ticker] = {'ticker': ticker, 'signals': [], 'data': {}}
        hidden_gem_candidates[ticker]['signals'].append(f"squeeze_risk: {stock.get('squeeze_risk')}, short_float: {stock.get('short_float')}%")
        hidden_gem_candidates[ticker]['data']['short_interest'] = stock

# From options: unusual activity
for stock in data.get('options_activity', []):
    ticker = stock.get('ticker', '')
    if ticker and ticker not in top_10_tickers and stock.get('signal') in ('bullish_sweep', 'bearish_sweep'):
        if ticker not in hidden_gem_candidates:
            hidden_gem_candidates[ticker] = {'ticker': ticker, 'signals': [], 'data': {}}
        hidden_gem_candidates[ticker]['signals'].append(f"options_signal: {stock.get('signal')}, v_oi: {stock.get('volume_oi_ratio')}")
        hidden_gem_candidates[ticker]['data']['options'] = stock

# From insider trading: insider buys
for stock in data.get('insider_trading', []):
    ticker = stock.get('ticker', '')
    if ticker and ticker not in top_10_tickers and stock.get('is_buy'):
        if ticker not in hidden_gem_candidates:
            hidden_gem_candidates[ticker] = {'ticker': ticker, 'signals': [], 'data': {}}
        hidden_gem_candidates[ticker]['signals'].append(f"insider_buy: ${stock.get('transaction_value', 0):,.0f} by {stock.get('role', 'insider')}")
        hidden_gem_candidates[ticker]['data']['insider'] = stock

# From reddit: high mentions but not mainstream
for stock in data.get('reddit', []):
    ticker = stock.get('ticker', '')
    if ticker and ticker not in top_10_tickers and stock.get('mentions', 0) > 5:
        if ticker not in hidden_gem_candidates:
            hidden_gem_candidates[ticker] = {'ticker': ticker, 'signals': [], 'data': {}}
        hidden_gem_candidates[ticker]['signals'].append(f"reddit_mentions: {stock.get('mentions')}, sentiment: {stock.get('sentiment')}")
        hidden_gem_candidates[ticker]['data']['reddit'] = stock

# From Google Trends: breakouts
for stock in data.get('google_trends', []):
    ticker = stock.get('ticker', '')
    if ticker and ticker not in top_10_tickers and stock.get('is_breakout'):
        if ticker not in hidden_gem_candidates:
            hidden_gem_candidates[ticker] = {'ticker': ticker, 'signals': [], 'data': {}}
        hidden_gem_candidates[ticker]['signals'].append(f"google_breakout: trend_value {stock.get('trend_value')}")
        hidden_gem_candidates[ticker]['data']['google_trends'] = stock

# Score candidates by number of signals
for ticker, info in hidden_gem_candidates.items():
    info['signal_count'] = len(info['signals'])

# Sort by signal count and take top 10
top_candidates = sorted(hidden_gem_candidates.values(), key=lambda x: x['signal_count'], reverse=True)[:10]

output = {
    'date': """$DATE_STR""",
    'top_10_excluded': list(top_10_tickers),
    'hidden_gem_candidates': top_candidates,
    'all_raw_data': {
        'momentum_sample': data.get('momentum', [])[:30],
        'short_interest': data.get('short_interest', [])[:20],
        'options_activity': data.get('options_activity', [])[:20],
        'insider_trading': data.get('insider_trading', [])[:20],
        'reddit': data.get('reddit', [])[:20],
        'google_trends': data.get('google_trends', [])[:20],
    }
}

print(json.dumps(output, indent=2, default=str))
PYEOF
)

# Replace shell variables in Python output
RESEARCH_DATA=$(echo "$RESEARCH_DATA" | sed "s|\$LATEST_RAW_DIR|$LATEST_RAW_DIR|g" | sed "s|\$REPORT_FILE|$REPORT_FILE|g" | sed "s|\$DATE_STR|$DATE_STR|g")

CANDIDATE_COUNT=$(echo "$RESEARCH_DATA" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('hidden_gem_candidates', [])))" 2>/dev/null || echo "0")
echo -e "${GREEN}Found $CANDIDATE_COUNT hidden gem candidates${NC}"
echo ""

# Build the equity research prompt
read -r -d '' PROMPT << 'EOF'
You are a senior buy-side equity research analyst at a top-tier hedge fund. Your job is to produce institutional-quality research reports that would be presented to portfolio managers for investment decisions.

Analyze the hidden gem candidates provided and produce a DETAILED EQUITY RESEARCH REPORT in JSON format.

IMPORTANT: Your response must be ONLY valid JSON, no markdown, no explanation outside the JSON.

For each stock, conduct deep due diligence as if you were recommending a real investment. Be specific, use real market knowledge, and provide actionable insights.

Return this exact JSON structure:

{
  "report_metadata": {
    "title": "Hidden Gems Equity Research Report",
    "date": "YYYY-MM-DD",
    "analyst": "AI Research Desk",
    "report_type": "Small/Mid-Cap Opportunities",
    "investment_horizon": "3-12 months"
  },
  "executive_summary": {
    "market_context": "2-3 sentences on current market environment for small caps",
    "key_themes": ["theme1", "theme2", "theme3"],
    "top_conviction_pick": {
      "ticker": "SYMBOL",
      "one_liner": "Single sentence pitch"
    },
    "total_candidates_reviewed": 0,
    "actionable_ideas": 0
  },
  "detailed_research": [
    {
      "ticker": "SYMBOL",
      "company_name": "Full Company Name",
      "sector": "Sector",
      "industry": "Specific Industry",
      "market_cap_estimate": "small-cap ($300M-$2B) | mid-cap ($2B-$10B) | micro-cap (<$300M)",

      "investment_rating": {
        "rating": "STRONG BUY | BUY | ACCUMULATE | HOLD | REDUCE | SELL",
        "conviction": "HIGH | MEDIUM | LOW",
        "risk_rating": "HIGH | MEDIUM | LOW",
        "suitable_for": "aggressive growth | growth | balanced | income"
      },

      "company_overview": {
        "business_description": "3-4 sentences describing what the company does, its products/services, and market position",
        "competitive_position": "2-3 sentences on competitive advantages or moat",
        "key_customers_markets": "Who are the customers, what markets do they serve",
        "management_quality": "Brief assessment of management if known"
      },

      "investment_thesis": {
        "primary_thesis": "2-3 sentence core investment thesis - why buy this stock NOW",
        "thesis_pillars": [
          {
            "pillar": "Growth Driver 1",
            "detail": "Specific explanation with data points if available"
          },
          {
            "pillar": "Growth Driver 2",
            "detail": "Specific explanation"
          },
          {
            "pillar": "Growth Driver 3",
            "detail": "Specific explanation"
          }
        ],
        "variant_perception": "What is the market missing? Why is this mispriced?"
      },

      "catalyst_timeline": [
        {
          "catalyst": "Specific catalyst event",
          "expected_timing": "Q1 2026 | Near-term | 3-6 months | etc",
          "potential_impact": "HIGH | MEDIUM | LOW",
          "description": "How this catalyst could move the stock"
        }
      ],

      "fundamental_analysis": {
        "revenue_growth": "Assessment of revenue trajectory",
        "margin_profile": "Gross/operating margin trends",
        "balance_sheet": "Debt levels, cash position, financial health",
        "cash_flow": "FCF generation capability",
        "key_metrics": [
          {"metric": "Metric Name", "value": "Value", "assessment": "Good/Concerning/Neutral"}
        ]
      },

      "technical_analysis": {
        "trend": "Primary trend direction and strength",
        "momentum_signals": "What the momentum data shows",
        "volume_analysis": "Volume patterns and what they indicate",
        "key_levels": {
          "current_price_estimate": "approximate current price or range",
          "support_1": "First support level",
          "support_2": "Second support level",
          "resistance_1": "First resistance level",
          "resistance_2": "Second resistance level"
        },
        "chart_pattern": "Any notable patterns forming"
      },

      "signal_analysis": {
        "signals_detected": ["list of signals from our data"],
        "signal_interpretation": "What these signals collectively suggest",
        "smart_money_activity": "Any institutional/insider activity noted",
        "retail_sentiment": "Reddit/social sentiment if available"
      },

      "valuation": {
        "valuation_approach": "How should this company be valued",
        "current_valuation_assessment": "Cheap | Fair | Expensive relative to peers/growth",
        "upside_scenario": {
          "target_price": "$XX or +XX%",
          "assumptions": "What needs to happen",
          "probability": "XX%"
        },
        "base_scenario": {
          "target_price": "$XX or +XX%",
          "assumptions": "Most likely outcome",
          "probability": "XX%"
        },
        "downside_scenario": {
          "target_price": "$XX or -XX%",
          "assumptions": "What could go wrong",
          "probability": "XX%"
        }
      },

      "risk_factors": [
        {
          "risk": "Specific risk",
          "severity": "HIGH | MEDIUM | LOW",
          "probability": "HIGH | MEDIUM | LOW",
          "mitigation": "How to monitor or hedge this risk"
        }
      ],

      "trade_structure": {
        "entry_strategy": "How to build a position",
        "position_sizing": "Suggested allocation (% of portfolio)",
        "entry_zone": "Price range for entry",
        "stop_loss": "Where to cut losses",
        "profit_targets": [
          {"target": "Target 1", "action": "Take 1/3 profits"},
          {"target": "Target 2", "action": "Take 1/3 profits"},
          {"target": "Target 3", "action": "Let remainder run with trailing stop"}
        ],
        "time_horizon": "Expected holding period",
        "options_strategy": "If applicable, any options plays to consider"
      },

      "monitoring_checklist": [
        "Key metric or event to watch #1",
        "Key metric or event to watch #2",
        "Key metric or event to watch #3"
      ],

      "bottom_line": "2-3 sentence summary: Should you buy this stock and why?"
    }
  ],
  "portfolio_construction": {
    "recommended_allocation": "How to allocate across these ideas",
    "correlation_notes": "Any correlation between picks to be aware of",
    "sector_exposure": "Resulting sector tilts",
    "risk_budget": "How much risk capital to dedicate to these ideas"
  },
  "appendix": {
    "methodology": "Brief note on how candidates were identified",
    "data_sources": "What data was analyzed",
    "disclaimers": "Standard research disclaimers"
  }
}

RULES:
1. Provide detailed_research for the TOP 5 most compelling hidden gem candidates
2. Be specific and actionable - this is for real investment decisions
3. Use your knowledge of these companies and sectors to provide real insights
4. If you don't know specific details about a company, make reasonable inferences based on sector/industry
5. Focus on small and mid-cap names - avoid mega-caps (AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA)
6. The variant_perception is crucial - explain what the market is missing
7. Catalyst timeline should include specific, near-term catalysts
8. Be honest about risks - institutional investors want to know what can go wrong
9. Trade structure should be specific enough to execute
10. For signal_analysis, interpret what our momentum/options/insider/reddit data means

HIDDEN GEM CANDIDATES DATA:
EOF

FULL_PROMPT="$PROMPT

$RESEARCH_DATA"

echo -e "${YELLOW}Generating equity research report via Gemini...${NC}"
echo -e "${YELLOW}(This may take 30-60 seconds for detailed analysis)${NC}"
echo ""

# Call Gemini
ANALYSIS=$(echo "$FULL_PROMPT" | "$GEMINI_CMD" --model gemini-3-pro-preview 2>/dev/null)
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 || -z "$ANALYSIS" ]]; then
    echo -e "${RED}Gemini analysis failed (exit code: $EXIT_CODE)${NC}"
    exit 1
fi

# Clean JSON response
CLEAN_JSON=$(echo "$ANALYSIS" | python3 -c '
import sys
import re

text = sys.stdin.read()
text = re.sub(r"^```json\s*\n?", "", text, flags=re.MULTILINE)
text = re.sub(r"^```\s*\n?", "", text, flags=re.MULTILINE)
text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
text = text.strip()

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
    exit 1
fi

# Save JSON
echo "$CLEAN_JSON" > "$OUTPUT_JSON"
echo -e "${GREEN}JSON saved to: $OUTPUT_JSON${NC}"

# Generate HTML report
echo -e "${YELLOW}Generating HTML report...${NC}"

python3 << PYTHON_SCRIPT
import json
from pathlib import Path
from datetime import datetime

with open("$OUTPUT_JSON", "r") as f:
    data = json.load(f)

date_str = "$DATE_STR"
time_str = "$TIME_STR"

def rating_color(rating):
    r = rating.upper() if rating else ""
    if "STRONG BUY" in r: return "#00d4aa"
    if "BUY" in r or "ACCUMULATE" in r: return "#4ade80"
    if "HOLD" in r: return "#fbbf24"
    if "REDUCE" in r: return "#fb923c"
    if "SELL" in r: return "#f87171"
    return "#94a3b8"

def rating_bg(rating):
    r = rating.upper() if rating else ""
    if "STRONG BUY" in r: return "rgba(0,212,170,0.15)"
    if "BUY" in r or "ACCUMULATE" in r: return "rgba(74,222,128,0.15)"
    if "HOLD" in r: return "rgba(251,191,36,0.15)"
    if "REDUCE" in r: return "rgba(251,146,60,0.15)"
    if "SELL" in r: return "rgba(248,113,113,0.15)"
    return "rgba(148,163,184,0.1)"

def risk_color(level):
    l = (level or "").upper()
    if "HIGH" in l: return "#f87171"
    if "MEDIUM" in l: return "#fbbf24"
    return "#4ade80"

def conviction_badge(conv):
    c = (conv or "").upper()
    if "HIGH" in c: return '<span class="badge high">HIGH CONVICTION</span>'
    if "MEDIUM" in c: return '<span class="badge medium">MEDIUM CONVICTION</span>'
    return '<span class="badge low">LOW CONVICTION</span>'

meta = data.get("report_metadata", {})
exec_sum = data.get("executive_summary", {})
research = data.get("detailed_research", [])
portfolio = data.get("portfolio_construction", {})
appendix = data.get("appendix", {})

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Equity Research Report - {date_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0f172a;
    --bg-card: #1e293b;
    --bg-elevated: #334155;
    --border: #475569;
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --text-dim: #64748b;
    --accent: #38bdf8;
    --accent-2: #818cf8;
    --green: #4ade80;
    --green-dim: rgba(74,222,128,0.2);
    --red: #f87171;
    --red-dim: rgba(248,113,113,0.2);
    --yellow: #fbbf24;
    --yellow-dim: rgba(251,191,36,0.2);
    --teal: #2dd4bf;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, sans-serif;
    line-height: 1.6;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }}

  .header {{
    border-bottom: 1px solid var(--border);
    padding-bottom: 2rem;
    margin-bottom: 2rem;
  }}

  .header-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
  }}

  .report-type {{
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
  }}

  h1 {{
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
  }}

  .header-meta {{
    font-size: 0.85rem;
    color: var(--text-muted);
  }}

  .header-stats {{
    text-align: right;
  }}

  .stat-box {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
  }}

  .stat-label {{
    font-size: 0.65rem;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  .stat-value {{
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--accent);
  }}

  .section {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }}

  .section-title {{
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}

  .section-title .icon {{
    width: 24px;
    height: 24px;
    background: var(--accent);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
  }}

  .exec-grid {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1.5rem;
  }}

  .conviction-pick {{
    background: linear-gradient(135deg, rgba(56,189,248,0.1) 0%, rgba(129,140,248,0.1) 100%);
    border: 1px solid rgba(56,189,248,0.3);
    border-radius: 10px;
    padding: 1rem 1.25rem;
  }}

  .conviction-ticker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--accent);
  }}

  .themes-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1rem;
  }}

  .theme-tag {{
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
  }}

  /* Research Cards */
  .research-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 2rem;
    overflow: hidden;
  }}

  .research-header {{
    background: linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-card) 100%);
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .ticker-info {{
    display: flex;
    align-items: center;
    gap: 1rem;
  }}

  .ticker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.75rem;
    font-weight: 700;
  }}

  .company-info {{
    display: flex;
    flex-direction: column;
  }}

  .company-name {{
    font-size: 1rem;
    font-weight: 600;
  }}

  .company-meta {{
    font-size: 0.8rem;
    color: var(--text-muted);
  }}

  .rating-box {{
    text-align: center;
    padding: 0.75rem 1.25rem;
    border-radius: 8px;
  }}

  .rating {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    font-weight: 700;
  }}

  .badge {{
    display: inline-block;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.25rem;
  }}

  .badge.high {{ background: var(--green-dim); color: var(--green); }}
  .badge.medium {{ background: var(--yellow-dim); color: var(--yellow); }}
  .badge.low {{ background: rgba(148,163,184,0.2); color: var(--text-muted); }}

  .research-body {{
    padding: 1.5rem;
  }}

  .research-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
    margin-bottom: 1.5rem;
  }}

  .research-box {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
  }}

  .research-box.full {{
    grid-column: 1 / -1;
  }}

  .research-box h4 {{
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
  }}

  .research-box p {{
    font-size: 0.85rem;
    line-height: 1.7;
    color: var(--text-muted);
  }}

  .thesis-pillars {{
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }}

  .pillar {{
    background: var(--bg-elevated);
    border-radius: 6px;
    padding: 0.75rem;
  }}

  .pillar-title {{
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 0.25rem;
  }}

  .pillar-detail {{
    font-size: 0.8rem;
    color: var(--text-muted);
  }}

  .catalyst-timeline {{
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }}

  .catalyst {{
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(71,85,105,0.5);
  }}

  .catalyst:last-child {{
    border-bottom: none;
  }}

  .catalyst-timing {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--teal);
    background: rgba(45,212,191,0.1);
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    white-space: nowrap;
  }}

  .catalyst-content {{
    flex: 1;
  }}

  .catalyst-name {{
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 0.1rem;
  }}

  .catalyst-desc {{
    font-size: 0.75rem;
    color: var(--text-muted);
  }}

  .scenario-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }}

  .scenario {{
    background: var(--bg-elevated);
    border-radius: 6px;
    padding: 0.75rem;
    text-align: center;
  }}

  .scenario.bull {{ border-top: 3px solid var(--green); }}
  .scenario.base {{ border-top: 3px solid var(--yellow); }}
  .scenario.bear {{ border-top: 3px solid var(--red); }}

  .scenario-label {{
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.25rem;
  }}

  .scenario.bull .scenario-label {{ color: var(--green); }}
  .scenario.base .scenario-label {{ color: var(--yellow); }}
  .scenario.bear .scenario-label {{ color: var(--red); }}

  .scenario-target {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 700;
  }}

  .scenario-prob {{
    font-size: 0.7rem;
    color: var(--text-muted);
  }}

  .risk-list {{
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }}

  .risk-item {{
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.8rem;
  }}

  .risk-severity {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-top: 0.4rem;
    flex-shrink: 0;
  }}

  .trade-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin-bottom: 1rem;
  }}

  .trade-item {{
    background: var(--bg-elevated);
    border-radius: 6px;
    padding: 0.75rem;
    text-align: center;
  }}

  .trade-label {{
    font-size: 0.6rem;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  .trade-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
    font-weight: 600;
    margin-top: 0.25rem;
  }}

  .trade-value.entry {{ color: var(--accent); }}
  .trade-value.stop {{ color: var(--red); }}
  .trade-value.target {{ color: var(--green); }}

  .bottom-line {{
    background: linear-gradient(135deg, rgba(56,189,248,0.1) 0%, rgba(129,140,248,0.05) 100%);
    border: 1px solid rgba(56,189,248,0.2);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-top: 1rem;
  }}

  .bottom-line-label {{
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.5rem;
  }}

  .bottom-line p {{
    font-size: 0.9rem;
    line-height: 1.6;
  }}

  .footer {{
    text-align: center;
    padding: 2rem 0;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
    font-size: 0.75rem;
    color: var(--text-dim);
  }}

  .disclaimer {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    margin-top: 1rem;
    font-size: 0.7rem;
    color: var(--text-dim);
    line-height: 1.5;
  }}

  @media (max-width: 768px) {{
    body {{ padding: 1rem; }}
    .exec-grid, .research-grid {{ grid-template-columns: 1fr; }}
    .scenario-grid, .trade-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .header-top {{ flex-direction: column; gap: 1rem; }}
    .header-stats {{ text-align: left; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <div class="report-type">{meta.get("report_type", "Equity Research")}</div>
      <h1>{meta.get("title", "Hidden Gems Research Report")}</h1>
      <div class="header-meta">
        {meta.get("date", date_str)} · {meta.get("analyst", "AI Research Desk")} · Investment Horizon: {meta.get("investment_horizon", "3-12 months")}
      </div>
    </div>
    <div class="header-stats">
      <div class="stat-box">
        <div class="stat-label">Candidates Reviewed</div>
        <div class="stat-value">{exec_sum.get("total_candidates_reviewed", len(research))}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Actionable Ideas</div>
        <div class="stat-value">{exec_sum.get("actionable_ideas", len(research))}</div>
      </div>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">
    <span class="icon">📊</span>
    Executive Summary
  </div>
  <div class="exec-grid">
    <div>
      <p style="font-size:0.9rem;line-height:1.7;margin-bottom:1rem;">{exec_sum.get("market_context", "")}</p>
      <div class="themes-list">
'''

for theme in exec_sum.get("key_themes", []):
    html += f'<span class="theme-tag">{theme}</span>'

top_pick = exec_sum.get("top_conviction_pick", {})
html += f'''
      </div>
    </div>
    <div class="conviction-pick">
      <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">Top Conviction Pick</div>
      <div class="conviction-ticker">{top_pick.get("ticker", "N/A")}</div>
      <div style="font-size:0.85rem;color:var(--text-muted);margin-top:0.5rem;">{top_pick.get("one_liner", "")}</div>
    </div>
  </div>
</div>
'''

# Detailed Research Section
for stock in research[:5]:
    ticker = stock.get("ticker", "???")
    company = stock.get("company_name", "")
    sector = stock.get("sector", "")
    industry = stock.get("industry", "")
    market_cap = stock.get("market_cap_estimate", "")

    inv_rating = stock.get("investment_rating", {})
    rating = inv_rating.get("rating", "HOLD")
    conviction = inv_rating.get("conviction", "MEDIUM")
    risk_rating = inv_rating.get("risk_rating", "MEDIUM")

    overview = stock.get("company_overview", {})
    thesis = stock.get("investment_thesis", {})
    catalysts = stock.get("catalyst_timeline", [])
    fundamental = stock.get("fundamental_analysis", {})
    technical = stock.get("technical_analysis", {})
    signals = stock.get("signal_analysis", {})
    valuation = stock.get("valuation", {})
    risks = stock.get("risk_factors", [])
    trade = stock.get("trade_structure", {})
    monitoring = stock.get("monitoring_checklist", [])
    bottom_line = stock.get("bottom_line", "")

    r_color = rating_color(rating)
    r_bg = rating_bg(rating)

    html += f'''
<div class="research-card">
  <div class="research-header">
    <div class="ticker-info">
      <div class="ticker" style="color:{r_color}">{ticker}</div>
      <div class="company-info">
        <div class="company-name">{company}</div>
        <div class="company-meta">{sector} · {industry} · {market_cap}</div>
      </div>
    </div>
    <div class="rating-box" style="background:{r_bg}">
      <div class="rating" style="color:{r_color}">{rating}</div>
      {conviction_badge(conviction)}
    </div>
  </div>

  <div class="research-body">
    <div class="research-grid">
      <div class="research-box full">
        <h4>Company Overview</h4>
        <p>{overview.get("business_description", "")}</p>
        <p style="margin-top:0.5rem;"><strong>Competitive Position:</strong> {overview.get("competitive_position", "")}</p>
      </div>

      <div class="research-box full">
        <h4>Investment Thesis</h4>
        <p style="font-size:0.95rem;color:var(--text);margin-bottom:1rem;"><strong>{thesis.get("primary_thesis", "")}</strong></p>
        <div class="thesis-pillars">
'''

    for pillar in thesis.get("thesis_pillars", [])[:3]:
        html += f'''
          <div class="pillar">
            <div class="pillar-title">{pillar.get("pillar", "")}</div>
            <div class="pillar-detail">{pillar.get("detail", "")}</div>
          </div>
'''

    html += f'''
        </div>
        <p style="margin-top:1rem;padding:0.75rem;background:rgba(56,189,248,0.1);border-radius:6px;font-size:0.85rem;">
          <strong style="color:var(--accent);">Variant Perception:</strong> {thesis.get("variant_perception", "")}
        </p>
      </div>

      <div class="research-box">
        <h4>Catalyst Timeline</h4>
        <div class="catalyst-timeline">
'''

    for cat in catalysts[:4]:
        html += f'''
          <div class="catalyst">
            <span class="catalyst-timing">{cat.get("expected_timing", "")}</span>
            <div class="catalyst-content">
              <div class="catalyst-name">{cat.get("catalyst", "")}</div>
              <div class="catalyst-desc">{cat.get("description", "")}</div>
            </div>
          </div>
'''

    html += f'''
        </div>
      </div>

      <div class="research-box">
        <h4>Signal Analysis</h4>
        <p><strong>Signals Detected:</strong></p>
        <ul style="font-size:0.8rem;color:var(--text-muted);margin:0.5rem 0;padding-left:1rem;">
'''

    for sig in signals.get("signals_detected", [])[:4]:
        html += f'<li>{sig}</li>'

    html += f'''
        </ul>
        <p style="margin-top:0.75rem;"><strong>Interpretation:</strong> {signals.get("signal_interpretation", "")}</p>
      </div>

      <div class="research-box">
        <h4>Technical Levels</h4>
        <p><strong>Trend:</strong> {technical.get("trend", "")}</p>
        <p><strong>Momentum:</strong> {technical.get("momentum_signals", "")}</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-top:0.75rem;">
          <div style="font-size:0.75rem;"><span style="color:var(--green);">Support:</span> {technical.get("key_levels", {}).get("support_1", "N/A")}</div>
          <div style="font-size:0.75rem;"><span style="color:var(--red);">Resistance:</span> {technical.get("key_levels", {}).get("resistance_1", "N/A")}</div>
        </div>
      </div>

      <div class="research-box">
        <h4>Valuation Scenarios</h4>
        <div class="scenario-grid">
          <div class="scenario bull">
            <div class="scenario-label">Bull Case</div>
            <div class="scenario-target">{valuation.get("upside_scenario", {}).get("target_price", "N/A")}</div>
            <div class="scenario-prob">{valuation.get("upside_scenario", {}).get("probability", "")} prob</div>
          </div>
          <div class="scenario base">
            <div class="scenario-label">Base Case</div>
            <div class="scenario-target">{valuation.get("base_scenario", {}).get("target_price", "N/A")}</div>
            <div class="scenario-prob">{valuation.get("base_scenario", {}).get("probability", "")} prob</div>
          </div>
          <div class="scenario bear">
            <div class="scenario-label">Bear Case</div>
            <div class="scenario-target">{valuation.get("downside_scenario", {}).get("target_price", "N/A")}</div>
            <div class="scenario-prob">{valuation.get("downside_scenario", {}).get("probability", "")} prob</div>
          </div>
        </div>
      </div>

      <div class="research-box">
        <h4>Key Risk Factors</h4>
        <div class="risk-list">
'''

    for risk in risks[:4]:
        sev = risk.get("severity", "MEDIUM")
        sev_c = risk_color(sev)
        html += f'''
          <div class="risk-item">
            <div class="risk-severity" style="background:{sev_c}"></div>
            <div>
              <strong>{risk.get("risk", "")}</strong>
              <div style="font-size:0.75rem;color:var(--text-dim);">Mitigation: {risk.get("mitigation", "")}</div>
            </div>
          </div>
'''

    html += f'''
        </div>
      </div>

      <div class="research-box full">
        <h4>Trade Structure</h4>
        <div class="trade-grid">
          <div class="trade-item">
            <div class="trade-label">Entry Zone</div>
            <div class="trade-value entry">{trade.get("entry_zone", "N/A")}</div>
          </div>
          <div class="trade-item">
            <div class="trade-label">Stop Loss</div>
            <div class="trade-value stop">{trade.get("stop_loss", "N/A")}</div>
          </div>
          <div class="trade-item">
            <div class="trade-label">Position Size</div>
            <div class="trade-value">{trade.get("position_sizing", "N/A")}</div>
          </div>
          <div class="trade-item">
            <div class="trade-label">Time Horizon</div>
            <div class="trade-value">{trade.get("time_horizon", "N/A")}</div>
          </div>
        </div>
        <p style="font-size:0.8rem;color:var(--text-muted);"><strong>Entry Strategy:</strong> {trade.get("entry_strategy", "")}</p>
      </div>
    </div>

    <div class="bottom-line">
      <div class="bottom-line-label">Bottom Line</div>
      <p>{bottom_line}</p>
    </div>
  </div>
</div>
'''

# Portfolio Construction
html += f'''
<div class="section">
  <div class="section-title">
    <span class="icon">📁</span>
    Portfolio Construction Notes
  </div>
  <div class="research-grid">
    <div class="research-box">
      <h4>Recommended Allocation</h4>
      <p>{portfolio.get("recommended_allocation", "")}</p>
    </div>
    <div class="research-box">
      <h4>Risk Budget</h4>
      <p>{portfolio.get("risk_budget", "")}</p>
    </div>
    <div class="research-box">
      <h4>Correlation Notes</h4>
      <p>{portfolio.get("correlation_notes", "")}</p>
    </div>
    <div class="research-box">
      <h4>Sector Exposure</h4>
      <p>{portfolio.get("sector_exposure", "")}</p>
    </div>
  </div>
</div>

<div class="disclaimer">
  <strong>Disclaimer:</strong> {appendix.get("disclaimers", "This report is generated by AI for informational purposes only and does not constitute investment advice. Past performance is not indicative of future results. Always conduct your own due diligence before making investment decisions.")}
</div>

<div class="footer">
  Equity Research Report · Generated {date_str} {time_str} · AI Research Desk via Gemini
</div>

</body>
</html>
'''

with open("$OUTPUT_HTML", "w") as f:
    f.write(html)

print("Equity research report generated successfully")
PYTHON_SCRIPT

if [[ $? -eq 0 ]]; then
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║              EQUITY RESEARCH REPORT COMPLETE              ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${GREEN}HTML Report:${NC} $OUTPUT_HTML"
    echo -e "  ${GREEN}JSON Data:${NC}   $OUTPUT_JSON"
    echo -e "  ${GREEN}Raw Data:${NC}    $LATEST_RAW_DIR"
    echo ""

    # Open in browser
    if command -v open &> /dev/null; then
        open "$OUTPUT_HTML"
    fi
else
    echo -e "${RED}Failed to generate HTML report${NC}"
    exit 1
fi
