# Product Requirements Document: Trending Stocks Scanner

## Problem Statement

Manually checking multiple sources each morning for trending stocks is time-consuming. A consolidated tool that aggregates momentum data, social sentiment, and news mentions would enable faster, more informed trading decisions.

## Goals

- Provide a single morning report of trending stocks
- Aggregate data from multiple independent sources
- Rank stocks by overall "trending" score
- Deliver results in under 2 minutes

---

## Data Sources

### 1. Momentum Scanner

**Description:** Identify stocks exhibiting positive technical momentum.

**Metrics to track:**
- Price change (1-day, 5-day, 1-month)
- Volume spike vs 20-day average
- RSI (Relative Strength Index) > 50 trending up
- Breaking above 20/50 day moving averages
- Sector performance from Finviz heatmap

**Data source options:**
- Finviz screener/heatmap (scraping or API)
- Yahoo Finance API
- Alpha Vantage API

### 2. Reddit Mentions

**Description:** Track stocks being discussed on investing subreddits.

**Subreddits to monitor:**
- r/wallstreetbets
- r/stocks
- r/investing
- r/options

**Metrics to track:**
- Mention count (last 24h)
- Mention velocity (increase vs previous day)
- Sentiment score (bullish/bearish/neutral)
- Comment engagement on stock-related posts

**Data source options:**
- Reddit API (PRAW)
- Pushshift API (historical)

### 3. News Mentions

**Description:** Identify stocks appearing in financial news.

**Sources to monitor:**
- Yahoo Finance
- MarketWatch
- Bloomberg (if accessible)
- Google News (finance section)
- SEC filings (8-K, earnings)

**Metrics to track:**
- Article count (last 24h)
- Headline sentiment
- News category (earnings, analyst upgrade, M&A, etc.)

**Data source options:**
- NewsAPI
- Finnhub news API
- RSS feeds
- Google News scraping

---

## Output Format

### Daily Report Structure

```
===========================================
TRENDING STOCKS REPORT - [DATE]
===========================================

TOP 10 OVERALL TRENDING
-----------------------
Rank | Ticker | Score | Momentum | Reddit | News | Summary
1    | NVDA   | 92    | +++      | +++    | ++   | Earnings beat, WSB buzz
2    | TSLA   | 87    | ++       | +++    | +++  | New model announcement
...

SECTOR MOMENTUM (Finviz Heatmap)
--------------------------------
1. Technology: +2.3% (month)
2. Healthcare: +1.8% (month)
3. Energy: -0.5% (month)

MOMENTUM LEADERS
----------------
[Top 5 stocks by technical momentum]

REDDIT BUZZ
-----------
[Top 5 most mentioned stocks with sentiment]

NEWS MOVERS
-----------
[Top 5 stocks with most news coverage]

===========================================
```

---

## Success Criteria & Test Cases

### TC-001: Momentum Scanner

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-001-1 | Fetch daily price data | Returns valid OHLCV data for 500+ stocks |
| TC-001-2 | Calculate momentum score | Score between 0-100 for each stock |
| TC-001-3 | Volume spike detection | Flags stocks with volume > 2x 20-day avg |
| TC-001-4 | Moving average crossover | Correctly identifies 20/50 MA crosses |
| TC-001-5 | Finviz heatmap parsing | Returns sector performance % for all 11 sectors |
| TC-001-6 | Data freshness | Data no older than market close of previous trading day |

### TC-002: Reddit Scanner

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-002-1 | API authentication | Successfully authenticates with Reddit API |
| TC-002-2 | Fetch posts | Retrieves posts from last 24h from all target subreddits |
| TC-002-3 | Ticker extraction | Correctly parses $TICKER and company names from text |
| TC-002-4 | Mention counting | Accurately counts unique mentions per ticker |
| TC-002-5 | Sentiment analysis | Classifies posts as bullish/bearish/neutral with >70% accuracy |
| TC-002-6 | Rate limit handling | Gracefully handles Reddit API rate limits |

### TC-003: News Scanner

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-003-1 | Fetch news articles | Retrieves articles from at least 2 news sources |
| TC-003-2 | Ticker extraction | Correctly identifies ticker symbols in headlines/body |
| TC-003-3 | Article deduplication | Same story from multiple sources counted once |
| TC-003-4 | Sentiment scoring | Headlines scored as positive/negative/neutral |
| TC-003-5 | Category tagging | Articles tagged (earnings, analyst, M&A, etc.) |
| TC-003-6 | Data freshness | Only includes articles from last 24h |

### TC-004: Aggregation & Scoring

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-004-1 | Combined scoring | Produces single 0-100 score from all sources |
| TC-004-2 | Source weighting | Configurable weights for each data source |
| TC-004-3 | Ranking | Returns top N stocks sorted by combined score |
| TC-004-4 | Duplicate handling | Same ticker from different sources merged correctly |
| TC-004-5 | Missing data handling | Gracefully handles missing data from any single source |

### TC-005: Performance & Reliability

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-005-1 | Execution time | Full scan completes in < 2 minutes |
| TC-005-2 | Error recovery | Continues if one data source fails |
| TC-005-3 | Caching | Caches API responses to reduce redundant calls |
| TC-005-4 | Logging | All API calls and errors logged with timestamps |
| TC-005-5 | Offline mode | Can display last cached results if APIs unavailable |

### TC-006: Output & Usability

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-006-1 | Report generation | Produces formatted report matching spec |
| TC-006-2 | Export formats | Supports terminal output + optional CSV/JSON export |
| TC-006-3 | Filtering | Can filter by sector, min score, or source |
| TC-006-4 | Historical comparison | Shows change vs previous day's trending list |

---

## Technical Requirements

### Dependencies
- Python 3.9+
- requests / httpx (HTTP client)
- praw (Reddit API)
- pandas (data manipulation)
- beautifulsoup4 (web scraping)
- textblob or nltk (sentiment analysis)

### API Keys Required
- Reddit API credentials (free)
- NewsAPI key (free tier: 100 requests/day)
- Alpha Vantage or Finnhub (free tier available)

### Configuration
```yaml
# config.yaml
sources:
  momentum:
    enabled: true
    weight: 0.4
  reddit:
    enabled: true
    weight: 0.3
    subreddits: [wallstreetbets, stocks, investing]
  news:
    enabled: true
    weight: 0.3

output:
  top_n: 10
  format: terminal  # terminal, csv, json

cache:
  enabled: true
  ttl_minutes: 60
```

---

## LLM Analysis & Assessment

### 4. Gemini LLM Analysis

**Description:** Use Gemini CLI to analyze aggregated data and provide actionable insights.

**Assessment Criteria:**
- **Conviction Score (1-10):** How confident should you be in this trend?
- **Risk Assessment:** Potential downside catalysts or red flags
- **Catalyst Identification:** What's driving the trend (earnings, macro, sentiment)?
- **Timeframe Suggestion:** Day trade, swing (1-5 days), or position (weeks)?
- **Correlation Check:** Are multiple trending stocks correlated (same sector/theme)?
- **Contrarian Signals:** Any signs this is overcrowded or due for reversal?

**LLM Prompt Template:**
```
Analyze these trending stocks and provide:
1. Top 3 highest conviction plays with reasoning
2. Any red flags or stocks to avoid
3. Sector/theme correlations
4. Overall market sentiment assessment
5. Suggested watchlist for today (max 5 tickers)

Data:
{trending_stocks_json}
```

### TC-007: LLM Analysis

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| TC-007-1 | Gemini CLI invocation | Successfully calls gemini CLI with report data |
| TC-007-2 | Response parsing | Extracts structured insights from LLM response |
| TC-007-3 | Timeout handling | Gracefully handles slow/failed LLM responses (30s timeout) |
| TC-007-4 | Output integration | LLM summary appended to final report |
| TC-007-5 | Fallback behavior | Report still generated if LLM analysis fails |

---

## Bash Script: analyze_with_gemini.sh

```bash
#!/bin/bash
#
# analyze_with_gemini.sh - Analyze trending stocks report with Gemini
#
# Usage: ./analyze_with_gemini.sh [report_file]
#
# Requires: gemini CLI installed and configured
#

set -e

REPORT_FILE="${1:-output/trending_report.json}"
TIMEOUT=30

# Check if report file exists
if [[ ! -f "$REPORT_FILE" ]]; then
    echo "Error: Report file not found: $REPORT_FILE"
    echo "Run the trending stocks scanner first: python main.py"
    exit 1
fi

# Check if gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo "Error: gemini CLI not found. Install it first."
    exit 1
fi

echo "============================================="
echo "GEMINI AI ANALYSIS"
echo "============================================="
echo ""

# Build the prompt
PROMPT="You are a trading analyst. Analyze this trending stocks data and provide:

1. TOP 3 HIGHEST CONVICTION PLAYS
   - Ticker, reasoning, suggested entry approach

2. RED FLAGS / AVOID LIST
   - Any stocks that look like traps or overcrowded trades

3. THEME ANALYSIS
   - What sectors/themes are hot today?
   - Any correlations between trending stocks?

4. MARKET SENTIMENT
   - Overall bullish/bearish/neutral assessment
   - Key risk factors to watch

5. TODAY'S WATCHLIST
   - Your top 5 tickers to watch with brief rationale

Be concise and actionable. This is for a morning trading review.

DATA:
$(cat "$REPORT_FILE")"

# Call Gemini CLI with timeout
if timeout "$TIMEOUT" gemini "$PROMPT" 2>/dev/null; then
    echo ""
    echo "============================================="
    echo "Analysis complete."
else
    EXIT_CODE=$?
    if [[ $EXIT_CODE -eq 124 ]]; then
        echo "Warning: Gemini analysis timed out after ${TIMEOUT}s"
    else
        echo "Warning: Gemini analysis failed (exit code: $EXIT_CODE)"
    fi
    echo "Continuing without AI analysis..."
fi
```

---

## Out of Scope (v1)

- Real-time streaming updates
- Trading execution / alerts
- Options flow data
- Institutional ownership tracking
- Backtesting trending signals
- Mobile app / web UI

---

## Open Questions

1. Should we include crypto alongside stocks?
2. Preferred sentiment analysis library (TextBlob vs VADER vs API)?
3. Should the tool run on a schedule (cron) or manual trigger only?
4. Any specific tickers to always include/exclude?

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-01-26 | - | Initial draft |
| 0.2 | 2026-01-26 | - | Added LLM analysis section with Gemini CLI integration |
