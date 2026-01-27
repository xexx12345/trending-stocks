# Trending Stocks Scanner - Usage Guide

## Quick Start

```bash
cd /Users/sc/Documents/trending-stocks

# Activate virtual environment (required)
source venv/bin/activate

# Run full scan
./run.sh

# Run scan + Gemini AI analysis
./run.sh --analyze
```

## Commands

### Main Scanner

```bash
# Full scan (momentum + reddit + news + sectors)
python main.py

# Show top 20 results instead of default 10
python main.py --top 20

# Output as JSON to terminal
python main.py --json

# Run quietly (no terminal output, just save to file)
python main.py --quiet

# Custom output file location
python main.py --output /path/to/output.json
```

### Individual Sources

```bash
# Momentum scan only (yfinance)
python main.py --source momentum

# Reddit scan only (requires API keys in .env)
python main.py --source reddit

# News scan only (Yahoo Finance)
python main.py --source news

# Sector scan only (ETF performance)
python main.py --source finviz
```

### Using run.sh (Recommended)

```bash
# Full scan
./run.sh

# Full scan + Gemini analysis
./run.sh --analyze
./run.sh -a

# Individual source
./run.sh momentum
./run.sh reddit
./run.sh news
./run.sh finviz
```

### Gemini AI Analysis

```bash
# Run analysis on latest scan results
./analyze_with_gemini.sh

# Run analysis on specific report file
./analyze_with_gemini.sh /path/to/report.json
```

## Output Files

| File | Description |
|------|-------------|
| `output/trending_report.json` | Raw scan data (JSON) |
| `output/analysis_YYYY-MM-DD.md` | Gemini AI analysis (dated) |

## Environment Variables

Set in `.env` file or export manually:

```bash
# Reddit API (required for Reddit scanning)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=YourApp/1.0
```

## Configuration

Edit `config.yaml` to adjust:

```yaml
sources:
  momentum:
    enabled: true
    weight: 0.4      # Weight in combined score
  reddit:
    enabled: true
    weight: 0.3
    subreddits:      # Subreddits to scan
      - wallstreetbets
      - stocks
      - investing
      - options
  news:
    enabled: true
    weight: 0.3

output:
  top_n: 10          # Default number of results
  format: terminal   # terminal, csv, json
```

## Example Workflow

```bash
# Morning routine
cd /Users/sc/Documents/trending-stocks
source venv/bin/activate
./run.sh --analyze

# Check the analysis
cat output/analysis_$(date +%Y-%m-%d).md
```
