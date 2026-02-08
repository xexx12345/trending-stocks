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
import csv
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
from scanners.options_activity import scan_options_activity
from scanners.perplexity_news import scan_perplexity, get_perplexity_tickers
from scanners.insider_trading import scan_insider_activity, get_insider_tickers
from scanners.analyst_ratings import scan_analyst_ratings
from scanners.congress_trading import scan_congress_trading
from scanners.etf_flows import scan_etf_flows
from scanners.institutional_holdings import scan_institutional_holdings
from scanners.bearish_momentum import scan_bearish_momentum
from scanners.fundamentals import scan_fundamentals
from utils.scoring import aggregate_scores, aggregate_short_scores, format_score_indicator

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


def save_raw_data(results: dict, base_dir: str = 'output/raw') -> str:
    """
    Save raw scanner data to dated subfolders.

    Creates folder structure: output/raw/YYYY-MM-DD_HHMMSS/
    Each scanner's data is saved as a separate JSON file.

    Args:
        results: The full results dict from run_scan
        base_dir: Base directory for raw data output

    Returns:
        Path to the created folder
    """
    # Create dated subfolder
    timestamp = datetime.now()
    folder_name = timestamp.strftime('%Y-%m-%d_%H%M%S')
    raw_dir = Path(base_dir) / folder_name
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Helper to safely serialize data
    def safe_serialize(obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)

    # Save metadata
    metadata = {
        'timestamp': results.get('timestamp', timestamp.isoformat()),
        'discovery_stats': results.get('discovery_stats', {}),
        'folder': str(raw_dir),
    }
    with open(raw_dir / '_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2, default=safe_serialize)

    # Save each scanner's raw data
    scanners_to_save = {
        'themes': results.get('themes', []),
        'theme_tickers': results.get('theme_tickers', []),
        'momentum': results.get('momentum', []),
        'reddit': results.get('reddit', []),
        'news': results.get('news', []),
        'sectors': results.get('sectors', []),
        'finviz_signals': results.get('finviz_signals', {}),
        'finviz_scores': results.get('finviz_scores', {}),
        'google_trends': results.get('google_trends', []),
        'short_interest': results.get('short_interest', []),
        'options_activity': results.get('options_activity', []),
        'perplexity': results.get('perplexity', []),
        'insider_trading': results.get('insider_trading', []),
        'analyst_ratings': results.get('analyst_ratings', []),
        'congress_trading': results.get('congress_trading', []),
        'etf_flows': results.get('etf_flows', {}),
        'institutional_holdings': results.get('institutional_holdings', []),
        'combined': results.get('combined', []),
        'bearish_momentum': results.get('bearish_momentum', []),
        'fundamentals': results.get('fundamentals', []),
        'short_candidates': results.get('short_candidates', []),
    }

    for name, data in scanners_to_save.items():
        if data:  # Only save non-empty data
            file_path = raw_dir / f'{name}.json'
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, default=safe_serialize)
                logger.debug(f"Saved raw data: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to save {name}: {e}")

    # Create a summary file with counts
    summary = {
        'timestamp': timestamp.isoformat(),
        'data_counts': {name: len(data) if isinstance(data, list) else (len(data) if isinstance(data, dict) else 0)
                        for name, data in scanners_to_save.items()},
        'files_created': [f.name for f in raw_dir.glob('*.json')],
    }
    with open(raw_dir / '_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Raw data saved to: {raw_dir}")
    return str(raw_dir)


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
        'options_activity': [],
        'perplexity': [],
        'insider_trading': [],
        'analyst_ratings': [],
        'congress_trading': [],
        'etf_flows': {},
        'institutional_holdings': [],
        'combined': [],
        'bearish_momentum': [],
        'fundamentals': [],
        'short_candidates': [],
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
        'perplexity': set(),
        'insider_trading': set(),
        'analyst_ratings': set(),
        'congress_trading': set(),
        'institutional': set(),
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

    # 1f. Perplexity news scan (AI-powered discovery)
    if source in (None, 'perplexity'):
        perplexity_config = config.get('sources', {}).get('perplexity', {})
        if perplexity_config.get('enabled', True):
            logger.info("Phase 1f: Running Perplexity news scan...")
            try:
                results['perplexity'] = scan_perplexity()
                discovered['perplexity'] = {r['ticker'] for r in results['perplexity']}
            except Exception as e:
                logger.error(f"Perplexity scan failed: {e}")

    # 1g. Insider trading scan (SEC Form 4 filings)
    if source in (None, 'insider_trading'):
        insider_config = config.get('sources', {}).get('insider_trading', {})
        if insider_config.get('enabled', True):
            logger.info("Phase 1g: Running insider trading scan...")
            try:
                results['insider_trading'] = scan_insider_activity(days_back=7)
                discovered['insider_trading'] = {r['ticker'] for r in results['insider_trading'] if r.get('is_buy')}
            except Exception as e:
                logger.error(f"Insider trading scan failed: {e}")

    # 1h. Analyst ratings scan (upgrades/downgrades)
    if source in (None, 'analyst_ratings'):
        analyst_config = config.get('sources', {}).get('analyst_ratings', {})
        if analyst_config.get('enabled', True):
            logger.info("Phase 1h: Running analyst ratings scan...")
            try:
                results['analyst_ratings'] = scan_analyst_ratings(days_back=7)
                discovered['analyst_ratings'] = {r['ticker'] for r in results['analyst_ratings'] if r.get('score', 0) > 60}
            except Exception as e:
                logger.error(f"Analyst ratings scan failed: {e}")

    # 1i. Congressional trading scan (STOCK Act filings)
    if source in (None, 'congress_trading'):
        congress_config = config.get('sources', {}).get('congress_trading', {})
        if congress_config.get('enabled', True):
            logger.info("Phase 1i: Running congressional trading scan...")
            try:
                results['congress_trading'] = scan_congress_trading(days_back=30)
                discovered['congress_trading'] = {r['ticker'] for r in results['congress_trading'] if r.get('signal') == 'congress_buying'}
            except Exception as e:
                logger.error(f"Congressional trading scan failed: {e}")

    # 1j. Institutional holdings scan (13F filings)
    if source in (None, 'institutional_holdings'):
        inst_config = config.get('sources', {}).get('institutional_holdings', {})
        if inst_config.get('enabled', True):
            logger.info("Phase 1j: Running institutional holdings scan...")
            try:
                results['institutional_holdings'] = scan_institutional_holdings(min_funds=2)
                discovered['institutional'] = {r['ticker'] for r in results['institutional_holdings'] if r.get('signal') == 'institutional_accumulation'}
            except Exception as e:
                logger.error(f"Institutional holdings scan failed: {e}")

    # ── PHASE 2: COLLECT ────────────────────────────────────────────
    # Union all discovered tickers. BASELINE_WATCHLIST is merged inside momentum.
    all_discovered = (
        discovered['themes'] | discovered['reddit'] | discovered['news'] |
        discovered['finviz'] | discovered['google_trends'] |
        discovered['perplexity'] | discovered['insider_trading'] |
        discovered['analyst_ratings'] | discovered['congress_trading'] |
        discovered['institutional']
    )

    results['discovery_stats'] = {
        'themes': len(discovered['themes']),
        'reddit': len(discovered['reddit']),
        'news': len(discovered['news']),
        'finviz': len(discovered['finviz']),
        'google_trends': len(discovered['google_trends']),
        'perplexity': len(discovered['perplexity']),
        'insider_trading': len(discovered['insider_trading']),
        'analyst_ratings': len(discovered['analyst_ratings']),
        'congress_trading': len(discovered['congress_trading']),
        'institutional': len(discovered['institutional']),
        'total_unique': len(all_discovered),
    }

    if source is None:
        logger.info(f"Phase 2: Collected {len(all_discovered)} unique tickers from discovery "
                     f"(themes={len(discovered['themes'])}, reddit={len(discovered['reddit'])}, "
                     f"news={len(discovered['news'])}, finviz={len(discovered['finviz'])}, "
                     f"google_trends={len(discovered['google_trends'])}, "
                     f"perplexity={len(discovered['perplexity'])}, insider={len(discovered['insider_trading'])}, "
                     f"analyst={len(discovered['analyst_ratings'])}, congress={len(discovered['congress_trading'])}, "
                     f"institutional={len(discovered['institutional'])})")

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

    # Run options activity enrichment on discovered tickers
    if source in (None, 'options_activity'):
        options_config = config.get('sources', {}).get('options_activity', {})
        if options_config.get('enabled', True):
            logger.info(f"Phase 3c: Running options activity scan on {len(all_discovered)} tickers...")
            try:
                results['options_activity'] = scan_options_activity(
                    list(all_discovered),
                    min_score=50.0
                )
            except Exception as e:
                logger.error(f"Options activity scan failed: {e}")

    # Run ETF flows scan for sector rotation signals
    if source in (None, 'etf_flows'):
        etf_config = config.get('sources', {}).get('etf_flows', {})
        if etf_config.get('enabled', True):
            logger.info("Phase 3d: Running ETF flows scan...")
            try:
                results['etf_flows'] = scan_etf_flows()
            except Exception as e:
                logger.error(f"ETF flows scan failed: {e}")

    # ── PHASE 4: SCORE ──────────────────────────────────────────────
    # Combine all 9 sources.
    if source is None:
        # Compute finviz per-ticker scores
        finviz_scores = {}
        if results['finviz_signals']:
            finviz_scores = compute_finviz_scores(results['finviz_signals'])
            results['finviz_scores'] = finviz_scores

        weights = {
            'momentum': config.get('sources', {}).get('momentum', {}).get('weight', 0.20),
            'finviz': config.get('sources', {}).get('finviz', {}).get('weight', 0.12),
            'reddit': config.get('sources', {}).get('reddit', {}).get('weight', 0.10),
            'news': config.get('sources', {}).get('news', {}).get('weight', 0.10),
            'google_trends': config.get('sources', {}).get('google_trends', {}).get('weight', 0.06),
            'short_interest': config.get('sources', {}).get('short_interest', {}).get('weight', 0.06),
            'options_activity': config.get('sources', {}).get('options_activity', {}).get('weight', 0.08),
            'perplexity': config.get('sources', {}).get('perplexity', {}).get('weight', 0.06),
            'insider_trading': config.get('sources', {}).get('insider_trading', {}).get('weight', 0.05),
            'analyst_ratings': config.get('sources', {}).get('analyst_ratings', {}).get('weight', 0.06),
            'congress_trading': config.get('sources', {}).get('congress_trading', {}).get('weight', 0.05),
            'institutional': config.get('sources', {}).get('institutional_holdings', {}).get('weight', 0.06),
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
            options_data=results['options_activity'],
            perplexity_data=results['perplexity'],
            insider_data=results['insider_trading'],
            analyst_data=results['analyst_ratings'],
            congress_data=results['congress_trading'],
            institutional_data=results['institutional_holdings'],
            etf_flows_data=results['etf_flows'],
        )

    # ── PHASE 5: SHORT CANDIDATES ─────────────────────────────────
    short_config = config.get('short_candidates', {})
    if source is None and short_config.get('enabled', True):
        logger.info("Phase 5: Running short candidates pipeline...")

        # 5a. Bearish momentum (reuses existing Phase 3 momentum data)
        try:
            results['bearish_momentum'] = scan_bearish_momentum(results['momentum'])
        except Exception as e:
            logger.error(f"Bearish momentum scan failed: {e}")

        # 5b. Fundamentals scan (new yfinance calls)
        try:
            results['fundamentals'] = scan_fundamentals(list(all_discovered))
        except Exception as e:
            logger.error(f"Fundamentals scan failed: {e}")

        # 5c. Aggregate short scores
        short_weights = short_config.get('weights')
        short_min_score = short_config.get('min_score', 40)
        short_squeeze_penalty = short_config.get('squeeze_penalty', True)
        try:
            results['short_candidates'] = aggregate_short_scores(
                bearish_momentum_data=results['bearish_momentum'],
                fundamentals_data=results['fundamentals'],
                analyst_data=results['analyst_ratings'],
                options_data=results['options_activity'],
                insider_data=results['insider_trading'],
                institutional_data=results['institutional_holdings'],
                finviz_data=results.get('finviz_signals', {}),
                congress_data=results['congress_trading'],
                news_data=results['news'],
                short_interest_data=results['short_interest'],
                weights=short_weights,
                min_score=short_min_score,
                squeeze_penalty=short_squeeze_penalty,
            )
        except Exception as e:
            logger.error(f"Short candidates scoring failed: {e}")

    # Save raw data to dated subfolder
    save_raw = getattr(args, 'save_raw', True)
    if save_raw:
        raw_dir = save_raw_data(results)
        results['raw_data_dir'] = raw_dir

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
              f"G.Trends: {stats.get('google_trends', 0):3}")
        print(f"  Perplexity: {stats.get('perplexity', 0):3}  |  Insider: {stats.get('insider_trading', 0):3}  |  "
              f"Total unique: {stats.get('total_unique', 0)}")

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
        print(f"{'Rank':<5} {'Ticker':<7} {'Score':<7} {'Mom':<5} {'Fvz':<5} {'Red':<5} {'News':<5} {'Opts':<5} {'Insd':<5} {'Summary'}")
        print("-" * 100)

        for i, stock in enumerate(results['combined'][:top_n], 1):
            mom_ind = format_score_indicator(stock['momentum_score'])
            fvz_ind = format_score_indicator(stock['finviz_score'])
            red_ind = format_score_indicator(stock['reddit_score'])
            news_ind = format_score_indicator(stock['news_score'])
            opts_ind = format_score_indicator(stock.get('options_score', 50))
            insd_ind = format_score_indicator(stock.get('insider_score', 50))
            summary = stock['summary'][:30] + "..." if len(stock['summary']) > 30 else stock['summary']

            print(f"{i:<5} {stock['ticker']:<7} {stock['combined_score']:<7.1f} "
                  f"{mom_ind:<5} {fvz_ind:<5} {red_ind:<5} {news_ind:<5} {opts_ind:<5} {insd_ind:<5} {summary}")

    # Short candidates
    if results.get('short_candidates'):
        print_section("TOP SHORT CANDIDATES (Bearish Conviction)")
        print(f"{'Rank':<5} {'Ticker':<7} {'Score':<7} {'Signals':<35} {'Summary'}")
        print("-" * 100)

        for i, stock in enumerate(results['short_candidates'][:top_n], 1):
            signals_str = ', '.join(stock['bearish_signals'][:3])
            if len(signals_str) > 33:
                signals_str = signals_str[:30] + "..."
            summary = stock['short_summary'][:35]
            if len(stock['short_summary']) > 35:
                summary = summary[:32] + "..."
            squeeze = " [SQ!]" if stock.get('squeeze_warning') else ""
            print(f"{i:<5} {stock['ticker']:<7} {stock['short_score']:<7.1f} "
                  f"{signals_str:<35} {summary}{squeeze}")

    # Sector performance
    if results['sectors']:
        print_section("SECTOR MOMENTUM (1 Month)")
        for i, sector in enumerate(results['sectors'][:6], 1):
            trend = "+" if sector['perf_1m'] >= 0 else ""
            print(f"{i}. {sector['sector']:<25} {trend}{sector['perf_1m']:.2f}%")

    # Momentum leaders
    if results['momentum']:
        print_section("MOMENTUM LEADERS (Livermore-style)")
        for i, stock in enumerate(results['momentum'][:5], 1):
            quality = stock.get('trend_quality', 'n/a')
            accel = stock.get('acceleration', 0)
            rel = stock.get('relative_strength', 0)
            flags = stock.get('too_late_flags', [])
            flag_str = f" ⚠{','.join(flags)}" if flags else ""
            brk_str = " ★BRK" if stock.get('is_breakout') else ""
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"1M: {stock['change_1m']:+6.2f}% | Accel: {accel:+5.2f} | "
                  f"RelStr: {rel:+5.2f} | {quality}{brk_str}{flag_str}")

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

    # Options Activity
    if results.get('options_activity'):
        print_section("UNUSUAL OPTIONS ACTIVITY")
        for i, stock in enumerate(results['options_activity'][:5], 1):
            vol_oi = f"{stock['volume_oi_ratio']:.1f}x" if stock.get('volume_oi_ratio') else "N/A"
            pc_ratio = f"{stock['put_call_ratio']:.2f}" if stock.get('put_call_ratio') else "N/A"
            signal = stock.get('signal', 'neutral').upper()
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"V/OI: {vol_oi:<6} | P/C: {pc_ratio:<5} | {signal}")

    # Perplexity News
    if results.get('perplexity'):
        print_section("PERPLEXITY AI DISCOVERIES")
        for i, stock in enumerate(results['perplexity'][:5], 1):
            sentiment = stock.get('sentiment', 'neutral')[:8]
            catalyst = "CAT" if stock.get('has_catalyst') else ""
            mentions = stock.get('mention_count', 0)
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"Mentions: {mentions:<3} | {sentiment:<8} | {catalyst}")

    # Insider Trading
    if results.get('insider_trading'):
        print_section("INSIDER TRADING (Form 4)")
        for i, stock in enumerate(results['insider_trading'][:5], 1):
            action = "BUY" if stock.get('is_buy') else "SELL"
            value = f"${stock['transaction_value']:,.0f}" if stock.get('transaction_value') else "N/A"
            role = stock.get('role', '')[:10]
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"{action:<5} | {value:<12} | {role}")

    # Analyst Ratings
    if results.get('analyst_ratings'):
        print_section("ANALYST RATINGS (Upgrades/Downgrades)")
        for i, stock in enumerate(results['analyst_ratings'][:5], 1):
            action = stock.get('action', 'N/A')[:12]
            firm = stock.get('analyst_firm', '')[:15] if stock.get('analyst_firm') else ''
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"{action:<12} | {firm}")

    # Congressional Trading
    if results.get('congress_trading'):
        print_section("CONGRESSIONAL TRADING")
        for i, stock in enumerate(results['congress_trading'][:5], 1):
            signal = stock.get('signal', 'N/A')[:10]
            politicians = stock.get('politician_count', 0)
            buy_count = stock.get('buy_count', 0)
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"{signal:<10} | {politicians} politicians | {buy_count} buys")

    # Institutional Holdings
    if results.get('institutional_holdings'):
        print_section("INSTITUTIONAL HOLDINGS (13F)")
        for i, stock in enumerate(results['institutional_holdings'][:5], 1):
            signal = stock.get('signal', 'N/A')[:15]
            funds = stock.get('funds_buying', 0)
            notable = stock.get('notable_holders', [])[:2]
            notable_str = ', '.join(notable) if notable else ''
            print(f"{i}. {stock['ticker']:<6} | Score: {stock['score']:5.1f} | "
                  f"{signal:<15} | {funds} funds | {notable_str[:20]}")

    # ETF Flows
    if results.get('etf_flows'):
        etf_data = results['etf_flows']
        if etf_data.get('top_inflows'):
            print_section("ETF INFLOWS (Sector Rotation)")
            for i, etf in enumerate(etf_data['top_inflows'][:5], 1):
                vol_ratio = f"{etf.get('volume_ratio', 1.0):.1f}x" if etf.get('volume_ratio') else "N/A"
                print(f"{i}. {etf['etf']:<6} ({etf['sector']:<20}) | "
                      f"Score: {etf['flow_score']:5.1f} | 1D: {etf.get('change_1d', 0):+5.1f}% | Vol: {vol_ratio}")

        if etf_data.get('sentiment'):
            print(f"\n  Retail Sentiment (leveraged ETFs): {etf_data['sentiment'].upper()}")

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

    # ── ALL TICKERS CENSUS ─────────────────────────────────────
    if results.get('combined'):
        print_section("ALL DISCOVERED TICKERS (sorted by source count)")
        combined = results['combined']
        momentum_lookup = {d['ticker']: d for d in results.get('momentum', [])}

        # Group by source count for quick visual scanning
        by_sources = {}
        for r in combined:
            n = len(r.get('sources', []))
            by_sources.setdefault(n, []).append(r)

        for n_sources in sorted(by_sources.keys(), reverse=True):
            tickers = by_sources[n_sources]
            print(f"\n  [{n_sources} source{'s' if n_sources != 1 else ''}] ({len(tickers)} tickers)")
            for r in tickers:
                ticker = r['ticker']
                mom = momentum_lookup.get(ticker, {})
                quality = mom.get('trend_quality', '')
                score = r['combined_score']
                sources = ', '.join(r.get('sources', []))
                change = mom.get('change_1m')
                change_str = f"{change:+.1f}%" if change is not None else "n/a"
                brk = " BRK" if mom.get('is_breakout') else ""
                flags = mom.get('too_late_flags', [])
                warn = f" !{'|'.join(flags)}" if flags else ""
                q_str = f" [{quality}]" if quality else ""
                print(f"    {ticker:<6} score={score:5.1f}  1m={change_str:>7}{q_str:>16}{brk}{warn}  <- {sources}")

        total = len(combined)
        multi = sum(1 for r in combined if len(r.get('sources', [])) >= 2)
        strong = sum(1 for r in combined
                     if momentum_lookup.get(r['ticker'], {}).get('trend_quality') == 'strong_early')
        print(f"\n  Total: {total} tickers | {multi} multi-source | {strong} strong_early")
        print(f"  Full data: output/all_tickers.csv")

    print("\n" + "=" * 60)
    if results.get('raw_data_dir'):
        print(f" Raw data saved to: {results['raw_data_dir']}")
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
        'raw_data_dir': results.get('raw_data_dir'),
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
                'options_score': r.get('options_score', 50),
                'perplexity_score': r.get('perplexity_score', 50),
                'insider_score': r.get('insider_score', 50),
                'short_float': r.get('short_float'),
                'squeeze_risk': r.get('squeeze_risk'),
                'is_breakout': r.get('is_breakout', False),
                'in_hot_theme': r.get('in_hot_theme', False),
                'options_signal': r.get('options_signal'),
                'insider_is_buy': r.get('insider_is_buy'),
                'sources': r['sources'],
                'summary': r['summary']
            }
            for r in results['combined']  # All tickers, not truncated
        ],
        'short_candidates': [
            {
                'ticker': r['ticker'],
                'short_score': r['short_score'],
                'bearish_signals': r['bearish_signals'],
                'short_summary': r['short_summary'],
                'squeeze_warning': r.get('squeeze_warning', False),
                'bearish_momentum_score': r.get('bearish_momentum_score', 0),
                'fundamentals_score': r.get('fundamentals_score', 0),
                'analyst_short_score': r.get('analyst_short_score', 0),
                'options_short_score': r.get('options_short_score', 0),
                'insider_sell_score': r.get('insider_sell_score', 0),
                'institutional_dist_score': r.get('institutional_dist_score', 0),
                'finviz_bearish_score': r.get('finviz_bearish_score', 0),
                'congress_sell_score': r.get('congress_sell_score', 0),
                'negative_news_score': r.get('negative_news_score', 0),
            }
            for r in results.get('short_candidates', [])
        ],
        'sectors': results['sectors'][:11],
        'top_momentum': [
            {
                'ticker': r['ticker'], 'score': r['score'],
                'change_1m': r['change_1m'],
                'trend_quality': r.get('trend_quality', 'n/a'),
                'acceleration': r.get('acceleration', 0),
                'relative_strength': r.get('relative_strength', 0),
                'vol_direction_ratio': r.get('vol_direction_ratio', 1.0),
                'is_breakout': r.get('is_breakout', False),
                'too_late_flags': r.get('too_late_flags', []),
            }
            for r in results['momentum']
        ],
        'reddit': [
            {'ticker': r['ticker'], 'mentions': r['mentions'], 'sentiment': r['sentiment'],
             'score': r.get('score', 50)}
            for r in results['reddit']
        ],
        'news': [
            {'ticker': r['ticker'], 'articles': r['article_count'], 'sentiment': r['sentiment'],
             'score': r.get('score', 50)}
            for r in results['news']
        ],
        'google_trends': [
            {'ticker': r['ticker'], 'score': r['score'], 'trend_value': r.get('trend_value', 0),
             'is_breakout': r.get('is_breakout', False), 'search_term': r.get('search_term', '')}
            for r in results.get('google_trends', [])
        ],
        'short_interest': [
            {'ticker': r['ticker'], 'score': r['score'], 'short_float': r.get('short_float'),
             'short_ratio': r.get('short_ratio'), 'squeeze_risk': r.get('squeeze_risk', 'low')}
            for r in results.get('short_interest', [])
        ],
        'options_activity': [
            {'ticker': r['ticker'], 'score': r['score'], 'volume_oi_ratio': r.get('volume_oi_ratio'),
             'put_call_ratio': r.get('put_call_ratio'), 'signal': r.get('signal', 'neutral')}
            for r in results.get('options_activity', [])
        ],
        'perplexity': [
            {'ticker': r['ticker'], 'score': r['score'], 'mention_count': r.get('mention_count', 0),
             'sentiment': r.get('sentiment', 'neutral'), 'has_catalyst': r.get('has_catalyst', False)}
            for r in results.get('perplexity', [])
        ],
        'insider_trading': [
            {'ticker': r['ticker'], 'score': r['score'], 'is_buy': r.get('is_buy', False),
             'transaction_value': r.get('transaction_value', 0), 'role': r.get('role', '')}
            for r in results.get('insider_trading', [])
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


def save_all_tickers_csv(results: dict, output_path: str = 'output/all_tickers.csv'):
    """
    Save every discovered ticker to a single CSV — one row per ticker,
    columns for each source's score, momentum data, and discovery sources.

    Designed to be opened in a spreadsheet for sorting/filtering.
    Goal: never miss a ticker that multiple sources are flagging.
    """
    combined = results.get('combined', [])
    if not combined:
        logger.warning("No combined data to save to CSV")
        return

    # Build momentum lookup for extra Livermore fields
    momentum_lookup = {d['ticker']: d for d in results.get('momentum', [])}

    rows = []
    for r in combined:
        ticker = r['ticker']
        mom = momentum_lookup.get(ticker, {})
        sources = r.get('sources', [])

        row = {
            'ticker': ticker,
            'combined_score': r['combined_score'],
            'num_sources': len(sources),
            'sources': '|'.join(sources),
            'trend_quality': mom.get('trend_quality', ''),
            'price': mom.get('price', ''),
            'change_1d': mom.get('change_1d', ''),
            'change_5d': mom.get('change_5d', ''),
            'change_1m': mom.get('change_1m', ''),
            'acceleration': mom.get('acceleration', ''),
            'relative_strength': mom.get('relative_strength', ''),
            'vol_direction_ratio': mom.get('vol_direction_ratio', ''),
            'rsi': mom.get('rsi', ''),
            'is_breakout': mom.get('is_breakout', ''),
            'too_late_flags': '|'.join(mom.get('too_late_flags', [])),
            'volume_ratio': mom.get('volume_ratio', ''),
            'above_ma20': mom.get('above_ma20', ''),
            'above_ma50': mom.get('above_ma50', ''),
            'momentum_score': r.get('momentum_score', ''),
            'finviz_score': r.get('finviz_score', ''),
            'reddit_score': r.get('reddit_score', ''),
            'news_score': r.get('news_score', ''),
            'options_score': r.get('options_score', ''),
            'google_trends_score': r.get('google_trends_score', ''),
            'short_interest_score': r.get('short_interest_score', ''),
            'perplexity_score': r.get('perplexity_score', ''),
            'insider_score': r.get('insider_score', ''),
            'analyst_score': r.get('analyst_score', ''),
            'congress_score': r.get('congress_score', ''),
            'institutional_score': r.get('institutional_score', ''),
            'in_hot_theme': r.get('in_hot_theme', False),
            'short_float': r.get('short_float', ''),
            'squeeze_risk': r.get('squeeze_risk', ''),
            'options_signal': r.get('options_signal', ''),
            'summary': r.get('summary', ''),
        }
        rows.append(row)

    # Sort by combined_score descending (already sorted, but be explicit)
    rows.sort(key=lambda x: x['combined_score'], reverse=True)

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys()) if rows else []
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"All tickers CSV saved to {output_path} ({len(rows)} tickers)")


def main():
    parser = argparse.ArgumentParser(description='Trending Stocks Scanner')
    parser.add_argument('--source', choices=['momentum', 'reddit', 'news', 'finviz', 'themes', 'google_trends', 'short_interest', 'options_activity', 'perplexity', 'insider_trading'],
                        help='Run specific source only')
    parser.add_argument('--top', type=int, default=10, help='Number of top results to show')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', default='output/trending_report.json',
                        help='JSON output file path')
    parser.add_argument('--quiet', action='store_true', help='Suppress terminal output')
    parser.add_argument('--no-raw', dest='save_raw', action='store_false',
                        help='Disable saving raw scanner data')
    parser.set_defaults(save_raw=True)

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Run scan
    logger.info("Starting trending stocks scan...")
    results = run_scan(args, config)

    # Save JSON output
    save_json(results, args.output)

    # Save all-tickers CSV (every ticker, every source, for spreadsheet review)
    save_all_tickers_csv(results, 'output/all_tickers.csv')

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
