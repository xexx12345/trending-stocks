#!/usr/bin/env python3
"""
Trending Stocks Scanner - Main entry point

Discovery-first pipeline:
  Phase 1 - DISCOVER: themes, reddit, news, finviz → raw tickers
  Phase 2 - COLLECT:  union all discovered tickers + baseline watchlist
  Phase 3 - ENRICH:   run momentum on full pool
  Phase 4 - SCORE:    combine all 4 sources with theme + multi-source bonuses

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

from scanners.themes import scan_themes, get_theme_tickers
from scanners.momentum import scan_momentum, format_momentum_indicator
from scanners.reddit import scan_reddit, format_reddit_indicator
from scanners.news import scan_news, format_news_indicator
from scanners.finviz import (
    scrape_sector_performance, get_sector_etf_performance, scan_finviz_signals,
    compute_finviz_scores, get_finviz_tickers,
)
from scanners.google_trends import scan_google_trends
from scanners.short_interest import scan_short_interest
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
        'themes': [],
        'theme_tickers': [],
        'momentum': [],
        'reddit': [],
        'news': [],
        'sectors': [],
        'finviz_signals': {},
        'finviz_scores': {},
        'google_trends': [],
        'short_interest': [],
        'combined': [],
        'discovery_stats': {},
    }

    source = args.source if hasattr(args, 'source') else None

    # ── PHASE 1: DISCOVER ──────────────────────────────────────────
    # Run themes, reddit, news, finviz to collect raw tickers.

    hot_themes = []
    theme_tickers = []
    discovered = {
        'themes': set(),
        'reddit': set(),
        'news': set(),
        'finviz': set(),
        'google_trends': set(),
    }

    # 1a. Theme scan
    if source in (None, 'themes'):
        logger.info("Phase 1a: Running thematic ETF scan...")
        try:
            theme_data = scan_themes()
            hot_themes = theme_data['hot_themes']
            theme_tickers = theme_data['theme_tickers']
            results['themes'] = hot_themes
            results['theme_tickers'] = theme_tickers
            discovered['themes'] = set(theme_tickers)
        except Exception as e:
            logger.error(f"Theme scan failed: {e}")

    # 1b. Reddit scan
    if source in (None, 'reddit'):
        logger.info("Phase 1b: Running Reddit scan...")
        try:
            subreddits = config.get('sources', {}).get('reddit', {}).get('subreddits')
            results['reddit'] = scan_reddit(subreddits)
            discovered['reddit'] = {r['ticker'] for r in results['reddit']}
        except Exception as e:
            logger.error(f"Reddit scan failed: {e}")

    # 1c. News scan
    if source in (None, 'news'):
        logger.info("Phase 1c: Running news scan...")
        try:
            results['news'] = scan_news(theme_tickers=theme_tickers or None)
            discovered['news'] = {r['ticker'] for r in results['news']}
        except Exception as e:
            logger.error(f"News scan failed: {e}")

    # 1d. Finviz signals scan
    if source in (None, 'finviz'):
        logger.info("Phase 1d: Running sector scan...")
        try:
            results['sectors'] = scrape_sector_performance()
            if len(results['sectors']) < 5:
                logger.info("Finviz scraping limited, using ETF data...")
                results['sectors'] = get_sector_etf_performance()
        except Exception as e:
            logger.error(f"Sector scan failed: {e}")
            try:
                results['sectors'] = get_sector_etf_performance()
            except Exception:
                pass

        logger.info("Phase 1d: Running Finviz stock signals scan...")
        try:
            results['finviz_signals'] = scan_finviz_signals(hot_themes=hot_themes or None)
            discovered['finviz'] = get_finviz_tickers(results['finviz_signals'])
        except Exception as e:
            logger.error(f"Finviz signals scan failed: {e}")

    # 1e. Google Trends scan
    if source in (None, 'google_trends'):
        logger.info("Phase 1e: Running Google Trends scan...")
        try:
            trends_config = config.get('sources', {}).get('google_trends', {})
            keywords = trends_config.get('keywords')
            results['google_trends'] = scan_google_trends(keywords=keywords)
            discovered['google_trends'] = {r['ticker'] for r in results['google_trends']}
        except Exception as e:
            logger.error(f"Google Trends scan failed: {e}")

    # ── PHASE 2: COLLECT ────────────────────────────────────────────
    # Union all discovered tickers. BASELINE_WATCHLIST is merged inside momentum.
    all_discovered = (
        discovered['themes'] | discovered['reddit'] | discovered['news'] |
        discovered['finviz'] | discovered['google_trends']
    )

    results['discovery_stats'] = {
        'themes': len(discovered['themes']),
        'reddit': len(discovered['reddit']),
        'news': len(discovered['news']),
        'finviz': len(discovered['finviz']),
        'google_trends': len(discovered['google_trends']),
        'total_unique': len(all_discovered),
    }

    if source is None:
        logger.info(f"Phase 2: Collected {len(all_discovered)} unique tickers from discovery "
                     f"(themes={len(discovered['themes'])}, reddit={len(discovered['reddit'])}, "
                     f"news={len(discovered['news'])}, finviz={len(discovered['finviz'])}, "
                     f"google_trends={len(discovered['google_trends'])})")

    # ── PHASE 3: ENRICH ────────────────────────────────────────────
    # Run momentum on full discovered pool (+ baseline watchlist).
    if source in (None, 'momentum'):
        discovered_list = list(all_discovered) if all_discovered else None
        logger.info(f"Phase 3a: Running momentum scan on {len(all_discovered) if all_discovered else 0} "
                     f"discovered tickers (+ baseline watchlist)...")
        try:
            results['momentum'] = scan_momentum(tickers=discovered_list)
        except Exception as e:
            logger.error(f"Momentum scan failed: {e}")

    # Run short interest enrichment on discovered tickers
    if source in (None, 'short_interest'):
        logger.info(f"Phase 3b: Running short interest scan on {len(all_discovered)} tickers...")
        try:
            short_config = config.get('sources', {}).get('short_interest', {})
            min_short_float = short_config.get('min_short_float', 5.0)
            results['short_interest'] = scan_short_interest(
                list(all_discovered),
                min_short_float=min_short_float
            )
        except Exception as e:
            logger.error(f"Short interest scan failed: {e}")

    # ── PHASE 4: SCORE ──────────────────────────────────────────────
    # Combine all 6 sources.
    if source is None:
        # Compute finviz per-ticker scores
        finviz_scores = {}
        if results['finviz_signals']:
            finviz_scores = compute_finviz_scores(results['finviz_signals'])
            results['finviz_scores'] = finviz_scores

        weights = {
            'momentum': config.get('sources', {}).get('momentum', {}).get('weight', 0.30),
            'finviz': config.get('sources', {}).get('finviz', {}).get('weight', 0.20),
            'reddit': config.get('sources', {}).get('reddit', {}).get('weight', 0.15),
            'news': config.get('sources', {}).get('news', {}).get('weight', 0.15),
            'google_trends': config.get('sources', {}).get('google_trends', {}).get('weight', 0.10),
            'short_interest': config.get('sources', {}).get('short_interest', {}).get('weight', 0.10),
        }
        results['combined'] = aggregate_scores(
            results['momentum'],
            results['reddit'],
            results['news'],
            weights,
            theme_tickers=set(theme_tickers) if theme_tickers else None,
            finviz_data=finviz_scores,
            google_trends_data=results['google_trends'],
            short_interest_data=results['short_interest'],
        )

    return results


def print_report(results: dict, top_n: int = 10):
    """Print formatted report to terminal."""
    timestamp = datetime.fromisoformat(results['timestamp'])
    print_header(f"TRENDING STOCKS REPORT - {timestamp.strftime('%Y-%m-%d %H:%M')}")

    # Discovery stats
    stats = results.get('discovery_stats', {})
    if stats:
        print_section("DISCOVERY STATS")
        print(f"  Themes: {stats.get('themes', 0):3}  |  Reddit: {stats.get('reddit', 0):3}  |  "
              f"News: {stats.get('news', 0):3}  |  Finviz: {stats.get('finviz', 0):3}  |  "
              f"G.Trends: {stats.get('google_trends', 0):3}  |  Total unique: {stats.get('total_unique', 0)}")

    # Hot themes
    if results.get('themes'):
        print_section("HOT THEMES (Thematic ETF Momentum)")
        for theme in results['themes']:
            hot_marker = " *** HOT ***" if theme['is_hot'] else ""
            print(f"  {theme['theme'].upper()}{hot_marker}")
            print(f"    Avg 1M: {theme['avg_1m']:+.2f}%  |  Avg 1W: {theme['avg_1w']:+.2f}%")
            for etf in theme['etf_perf']:
                print(f"      {etf['etf']:6} ${etf['price']:>8.2f}  "
                      f"1D: {etf['perf_1d']:+6.2f}%  "
                      f"1W: {etf['perf_1w']:+6.2f}%  "
                      f"1M: {etf['perf_1m']:+6.2f}%")

        if results.get('theme_tickers'):
            print(f"\n  Theme tickers injected: {len(results['theme_tickers'])}")

    # Combined rankings
    if results['combined']:
        print_section("TOP TRENDING STOCKS (Combined Score)")
        print(f"{'Rank':<5} {'Ticker':<7} {'Score':<7} {'Mom':<5} {'Fvz':<5} {'Red':<5} {'News':<5} {'GTrnd':<6} {'Short':<6} {'Summary'}")
        print("-" * 100)

        for i, stock in enumerate(results['combined'][:top_n], 1):
            mom_ind = format_score_indicator(stock['momentum_score'])
            fvz_ind = format_score_indicator(stock['finviz_score'])
            red_ind = format_score_indicator(stock['reddit_score'])
            news_ind = format_score_indicator(stock['news_score'])
            trend_ind = format_score_indicator(stock.get('google_trends_score', 50))
            short_ind = format_score_indicator(stock.get('short_interest_score', 50))
            summary = stock['summary'][:30] + "..." if len(stock['summary']) > 30 else stock['summary']

            print(f"{i:<5} {stock['ticker']:<7} {stock['combined_score']:<7.1f} "
                  f"{mom_ind:<5} {fvz_ind:<5} {red_ind:<5} {news_ind:<5} {trend_ind:<6} {short_ind:<6} {summary}")

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

    # Google Trends
    if results.get('google_trends'):
        print_section("GOOGLE TRENDS")
        for i, stock in enumerate(results['google_trends'][:5], 1):
            breakout = " BREAKOUT" if stock.get('is_breakout') else ""
            term = stock.get('search_term', '')[:25]
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"Trend: {stock.get('trend_value', 0):3}{breakout} | {term}")

    # Short Interest / Squeeze Candidates
    if results.get('short_interest'):
        print_section("SHORT SQUEEZE CANDIDATES")
        for i, stock in enumerate(results['short_interest'][:5], 1):
            sf = f"{stock['short_float']:.1f}%" if stock.get('short_float') else "N/A"
            sr = f"{stock['short_ratio']:.1f}d" if stock.get('short_ratio') else "N/A"
            risk = stock.get('squeeze_risk', 'low').upper()
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"Short: {sf:<7} | DTC: {sr:<5} | Risk: {risk}")

    # Finviz signals
    finviz = results.get('finviz_signals', {})

    if finviz.get('top_gainers'):
        print_section("FINVIZ: TOP GAINERS")
        for i, stock in enumerate(finviz['top_gainers'][:5], 1):
            print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | {stock.get('sector', '')[:20]}")

    if finviz.get('top_losers'):
        print_section("FINVIZ: TOP LOSERS")
        for i, stock in enumerate(finviz['top_losers'][:5], 1):
            print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | {stock.get('sector', '')[:20]}")

    if finviz.get('unusual_volume'):
        print_section("FINVIZ: UNUSUAL VOLUME")
        for i, stock in enumerate(finviz['unusual_volume'][:5], 1):
            vol = stock.get('volume', 'N/A')
            print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | Vol: {vol}")

    if finviz.get('new_highs'):
        print_section("FINVIZ: NEW HIGHS")
        for i, stock in enumerate(finviz['new_highs'][:5], 1):
            print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | {stock.get('sector', '')[:20]}")

    if finviz.get('oversold'):
        print_section("FINVIZ: OVERSOLD (RSI < 30)")
        for i, stock in enumerate(finviz['oversold'][:5], 1):
            print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | {stock.get('sector', '')[:20]}")

    if finviz.get('overbought'):
        print_section("FINVIZ: OVERBOUGHT (RSI > 70)")
        for i, stock in enumerate(finviz['overbought'][:5], 1):
            print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | {stock.get('sector', '')[:20]}")

    # Industry movers from hot themes
    if finviz.get('industry_movers'):
        for theme_name, movers in finviz['industry_movers'].items():
            print_section(f"FINVIZ: {theme_name.upper()} INDUSTRY MOVERS")
            for i, stock in enumerate(movers[:5], 1):
                print(f"{i}. {stock['ticker']:<6} | {stock['change']:+6.2f}% | {stock.get('company', '')[:30]}")

    print("\n" + "=" * 60)
    print(" Report complete. Run analyze_with_gemini.sh for AI insights.")
    print("=" * 60 + "\n")


def save_json(results: dict, output_path: str):
    """Save results to JSON file."""
    # Build themes summary
    themes_summary = []
    for t in results.get('themes', []):
        themes_summary.append({
            'theme': t['theme'],
            'is_hot': t['is_hot'],
            'avg_1m': t['avg_1m'],
            'avg_1w': t['avg_1w'],
            'etf_perf': t['etf_perf'],
        })

    clean_results = {
        'timestamp': results['timestamp'],
        'discovery_stats': results.get('discovery_stats', {}),
        'hot_themes': themes_summary,
        'theme_tickers': results.get('theme_tickers', []),
        'combined': [
            {
                'ticker': r['ticker'],
                'combined_score': r['combined_score'],
                'momentum_score': r['momentum_score'],
                'finviz_score': r.get('finviz_score', 50),
                'reddit_score': r['reddit_score'],
                'news_score': r['news_score'],
                'google_trends_score': r.get('google_trends_score', 50),
                'short_interest_score': r.get('short_interest_score', 50),
                'short_float': r.get('short_float'),
                'squeeze_risk': r.get('squeeze_risk'),
                'is_breakout': r.get('is_breakout', False),
                'in_hot_theme': r.get('in_hot_theme', False),
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
        ],
        'top_google_trends': [
            {'ticker': r['ticker'], 'score': r['score'], 'trend_value': r.get('trend_value', 0),
             'is_breakout': r.get('is_breakout', False), 'search_term': r.get('search_term', '')}
            for r in results.get('google_trends', [])[:10]
        ],
        'top_short_interest': [
            {'ticker': r['ticker'], 'score': r['score'], 'short_float': r.get('short_float'),
             'short_ratio': r.get('short_ratio'), 'squeeze_risk': r.get('squeeze_risk', 'low')}
            for r in results.get('short_interest', [])[:10]
        ],
        'finviz_signals': {
            'top_gainers': [
                {'ticker': r['ticker'], 'change': r['change'], 'sector': r.get('sector', '')}
                for r in results.get('finviz_signals', {}).get('top_gainers', [])[:10]
            ],
            'top_losers': [
                {'ticker': r['ticker'], 'change': r['change'], 'sector': r.get('sector', '')}
                for r in results.get('finviz_signals', {}).get('top_losers', [])[:10]
            ],
            'unusual_volume': [
                {'ticker': r['ticker'], 'change': r['change'], 'volume': r.get('volume', '')}
                for r in results.get('finviz_signals', {}).get('unusual_volume', [])[:10]
            ],
            'new_highs': [
                {'ticker': r['ticker'], 'change': r['change'], 'sector': r.get('sector', '')}
                for r in results.get('finviz_signals', {}).get('new_highs', [])[:10]
            ],
            'oversold': [
                {'ticker': r['ticker'], 'change': r['change'], 'sector': r.get('sector', '')}
                for r in results.get('finviz_signals', {}).get('oversold', [])[:10]
            ],
            'overbought': [
                {'ticker': r['ticker'], 'change': r['change'], 'sector': r.get('sector', '')}
                for r in results.get('finviz_signals', {}).get('overbought', [])[:10]
            ],
            'industry_movers': {
                theme: [
                    {'ticker': r['ticker'], 'change': r['change'], 'company': r.get('company', '')}
                    for r in movers[:10]
                ]
                for theme, movers in results.get('finviz_signals', {}).get('industry_movers', {}).items()
            }
        }
    }

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(clean_results, f, indent=2)

    logger.info(f"Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Trending Stocks Scanner')
    parser.add_argument('--source', choices=['momentum', 'reddit', 'news', 'finviz', 'themes', 'google_trends', 'short_interest'],
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
