# Trending Stocks Scanner - Usage Guide

## Quick Start

```bash
cd /Users/sc/Documents/trending-stocks
source venv/bin/activate

# Run full pipeline (scanner + Gemini AI analysis)
./run_full_analysis.sh
```

## Commands

### Full Pipeline (Recommended)

```bash
# Full scan + Gemini analysis (opens HTML report in browser)
./run_full_analysis.sh

# Show top 20 results
./run_full_analysis.sh --top 20

# Scanner only, skip Gemini
./run_full_analysis.sh --skip-gemini

# Don't save raw data files
./run_full_analysis.sh --no-raw
```

### Scanner Only

```bash
# Full scan (all phases including shorts)
python3 main.py

# Show top 20 results
python3 main.py --top 20

# Output as JSON to terminal
python3 main.py --json

# Run quietly (no terminal output, just save to file)
python3 main.py --quiet

# Custom output file location
python3 main.py --output /path/to/output.json
```

### Gemini Analysis Only

```bash
# Analyze latest scan results
./analyze_with_gemini.sh

# Analyze specific report file
./analyze_with_gemini.sh /path/to/report.json
```

### Individual Sources

```bash
python3 main.py --source momentum
python3 main.py --source reddit
python3 main.py --source news
python3 main.py --source finviz
python3 main.py --source google_trends
python3 main.py --source short_interest
python3 main.py --source options_activity
python3 main.py --source perplexity
python3 main.py --source insider_trading
```

## Output Files

| File | Description |
|------|-------------|
| `output/trending_report.json` | Combined scan data — longs + shorts |
| `output/raw/YYYY-MM-DD_HHMMSS/` | Raw scanner JSON files (one per source) |
| `output/analysis_YYYY-MM-DD.html` | Gemini AI report (HTML, opens in browser) |
| `output/analysis_YYYY-MM-DD.json` | Gemini structured JSON output |

## Environment Variables

Set in `.env` file:

```bash
# Reddit API (required for Reddit scanning)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=YourApp/1.0

# Perplexity API (optional, ~$1/month)
PERPLEXITY_API_KEY=your_key
```

## Configuration

Edit `config.yaml` to adjust weights, enable/disable sources, and configure the short pipeline:

```yaml
sources:
  momentum:
    weight: 0.20
  reddit:
    weight: 0.10
    subreddits:
      - wallstreetbets
      - stocks
      - investing
      - options
  # ... 12 total sources

short_candidates:
  enabled: true
  top_n: 10
  weights:
    bearish_momentum: 0.25
    fundamentals: 0.15
    # ... 9 total sources
  squeeze_penalty: true
  min_score: 40
```

## Example Workflow

```bash
# Morning routine
cd /Users/sc/Documents/trending-stocks
source venv/bin/activate
./run_full_analysis.sh

# Report opens automatically in browser
# HTML at: output/analysis_YYYY-MM-DD.html
# Sections: Longs, Shorts, Pair Trades, Hidden Gems, Squeeze Watch, etc.
```
