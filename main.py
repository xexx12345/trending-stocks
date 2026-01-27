#!/usr/bin/env python3
"""
Trending Stocks Scanner - Main entry point

Aggregates data from multiple sources to identify trending stocks:
- Technical momentum (price action, volume, RSI)
- Reddit mentions (WSB, stocks, investing)
- News coverage
- Finviz sector heatmap

Usage:
    python main.py                    # Run full scan
    python main.py --source momentum  # Run specific source only
    python main.py --top 20           # Show top 20 results
    python main.py --json             # Output as JSON
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from scanners.momentum import scan_momentum, format_momentum_indicator
from scanners.reddit import scan_reddit, format_reddit_indicator
from scanners.news import scan_news, format_news_indicator
from scanners.finviz import scrape_sector_performance, scrape_top_gainers, get_sector_etf_performance
from utils.scoring import aggregate_scores, format_score_indicator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent / 'config.yaml'
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_section(title: str):
    """Print a section header."""
    print(f"\n{title}")
    print("-" * 50)


def run_scan(args, config: dict) -> dict:
    """Run the trending stocks scan and return results."""
    results = {
        'timestamp': datetime.now().isoformat(),
        'momentum': [],
        'reddit': [],
        'news': [],
        'sectors': [],
        'combined': []
    }

    source = args.source if hasattr(args, 'source') else None

    # Run momentum scan
    if source in (None, 'momentum'):
        logger.info("Running momentum scan...")
        try:
            results['momentum'] = scan_momentum()
        except Exception as e:
            logger.error(f"Momentum scan failed: {e}")

    # Run Reddit scan
    if source in (None, 'reddit'):
        logger.info("Running Reddit scan...")
        try:
            subreddits = config.get('sources', {}).get('reddit', {}).get('subreddits')
            results['reddit'] = scan_reddit(subreddits)
        except Exception as e:
            logger.error(f"Reddit scan failed: {e}")

    # Run news scan
    if source in (None, 'news'):
        logger.info("Running news scan...")
        try:
            results['news'] = scan_news()
        except Exception as e:
            logger.error(f"News scan failed: {e}")

    # Run Finviz sector scan (with ETF fallback)
    if source in (None, 'finviz'):
        logger.info("Running sector scan...")
        try:
            results['sectors'] = scrape_sector_performance()
            # Fallback to ETF data if scraping didn't work well
            if len(results['sectors']) < 5:
                logger.info("Finviz scraping limited, using ETF data...")
                results['sectors'] = get_sector_etf_performance()
        except Exception as e:
            logger.error(f"Sector scan failed: {e}")
            # Try ETF fallback
            try:
                results['sectors'] = get_sector_etf_performance()
            except:
                pass

    # Aggregate scores
    if source is None:
        weights = {
            'momentum': config.get('sources', {}).get('momentum', {}).get('weight', 0.4),
            'reddit': config.get('sources', {}).get('reddit', {}).get('weight', 0.3),
            'news': config.get('sources', {}).get('news', {}).get('weight', 0.3),
        }
        results['combined'] = aggregate_scores(
            results['momentum'],
            results['reddit'],
            results['news'],
            weights
        )

    return results


def print_report(results: dict, top_n: int = 10):
    """Print formatted report to terminal."""
    timestamp = datetime.fromisoformat(results['timestamp'])
    print_header(f"TRENDING STOCKS REPORT - {timestamp.strftime('%Y-%m-%d %H:%M')}")

    # Combined rankings
    if results['combined']:
        print_section("TOP TRENDING STOCKS (Combined Score)")
        print(f"{'Rank':<5} {'Ticker':<7} {'Score':<7} {'Mom':<5} {'Reddit':<7} {'News':<5} {'Summary'}")
        print("-" * 80)

        for i, stock in enumerate(results['combined'][:top_n], 1):
            mom_ind = format_score_indicator(stock['momentum_score'])
            red_ind = format_score_indicator(stock['reddit_score'])
            news_ind = format_score_indicator(stock['news_score'])
            summary = stock['summary'][:35] + "..." if len(stock['summary']) > 35 else stock['summary']

            print(f"{i:<5} {stock['ticker']:<7} {stock['combined_score']:<7.1f} "
                  f"{mom_ind:<5} {red_ind:<7} {news_ind:<5} {summary}")

    # Sector performance
    if results['sectors']:
        print_section("SECTOR MOMENTUM (1 Month)")
        for i, sector in enumerate(results['sectors'][:6], 1):
            trend = "+" if sector['perf_1m'] >= 0 else ""
            print(f"{i}. {sector['sector']:<25} {trend}{sector['perf_1m']:.2f}%")

    # Momentum leaders
    if results['momentum']:
        print_section("MOMENTUM LEADERS")
        for i, stock in enumerate(results['momentum'][:5], 1):
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"1M: {stock['change_1m']:+6.2f}% | Vol: {stock['volume_ratio']:.1f}x")

    # Reddit buzz
    if results['reddit']:
        print_section("REDDIT BUZZ")
        for i, stock in enumerate(results['reddit'][:5], 1):
            subs = ', '.join(stock.get('subreddits', [])[:2])
            print(f"{i}. {stock['ticker']:<6} | Mentions: {stock['mentions']:3} | "
                  f"Sentiment: {stock['sentiment']:<8} | {subs}")

    # News movers
    if results['news']:
        print_section("NEWS MOVERS")
        for i, stock in enumerate(results['news'][:5], 1):
            cat = stock.get('top_category', 'general')
            print(f"{i}. {stock['ticker']:<6} | Articles: {stock['article_count']:2} | "
                  f"Sentiment: {stock['sentiment']:<8} | {cat}")

    print("\n" + "=" * 60)
    print(" Report complete. Run analyze_with_gemini.sh for AI insights.")
    print("=" * 60 + "\n")


def save_json(results: dict, output_path: str):
    """Save results to JSON file."""
    # Remove verbose data for cleaner output
    clean_results = {
        'timestamp': results['timestamp'],
        'combined': [
            {
                'ticker': r['ticker'],
                'combined_score': r['combined_score'],
                'momentum_score': r['momentum_score'],
                'reddit_score': r['reddit_score'],
                'news_score': r['news_score'],
                'sources': r['sources'],
                'summary': r['summary']
            }
            for r in results['combined'][:20]
        ],
        'sectors': results['sectors'][:11],
        'top_momentum': [
            {'ticker': r['ticker'], 'score': r['score'], 'change_1m': r['change_1m']}
            for r in results['momentum'][:10]
        ],
        'top_reddit': [
            {'ticker': r['ticker'], 'mentions': r['mentions'], 'sentiment': r['sentiment']}
            for r in results['reddit'][:10]
        ],
        'top_news': [
            {'ticker': r['ticker'], 'articles': r['article_count'], 'sentiment': r['sentiment']}
            for r in results['news'][:10]
        ]
    }

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(clean_results, f, indent=2)

    logger.info(f"Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Trending Stocks Scanner')
    parser.add_argument('--source', choices=['momentum', 'reddit', 'news', 'finviz'],
                        help='Run specific source only')
    parser.add_argument('--top', type=int, default=10, help='Number of top results to show')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', default='output/trending_report.json',
                        help='JSON output file path')
    parser.add_argument('--quiet', action='store_true', help='Suppress terminal output')

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Run scan
    logger.info("Starting trending stocks scan...")
    results = run_scan(args, config)

    # Save JSON output
    save_json(results, args.output)

    # Print report
    if not args.quiet:
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print_report(results, args.top)

    logger.info("Scan complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
