"""
Finviz Scanner - Scrapes sector performance and stock signals from Finviz
Includes industry-specific screens for hot themes
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging
import re
import json

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def _scrape_finviz_screener(url: str, limit: int = 20) -> List[Dict]:
    """
    Shared helper to scrape a Finviz screener page.
    Extracts ticker, company, sector, change, and volume from screener results.
    """
    results = []

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 10:
                ticker_col = cols[1] if len(cols) > 1 else None
                if ticker_col:
                    ticker_link = ticker_col.find('a')
                    if ticker_link and ticker_link.get('href', '').startswith('quote.ashx'):
                        ticker = ticker_link.get_text(strip=True)
                        # Skip invalid tickers
                        if ticker.isdigit() or len(ticker) < 2:
                            continue

                        try:
                            company = cols[2].get_text(strip=True)[:50] if len(cols) > 2 else ''
                            sector = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                            change = 0.0
                            volume = ''
                            for col in cols:
                                text = col.get_text(strip=True)
                                if '%' in text and not text.startswith('$') and change == 0.0:
                                    try:
                                        change = float(text.replace('%', '').replace(',', ''))
                                    except ValueError:
                                        pass
                                if ('M' in text or 'K' in text) and not volume:
                                    cleaned = text.replace('.', '').replace('M', '').replace('K', '').replace(',', '')
                                    if cleaned.isdigit():
                                        volume = text

                            results.append({
                                'ticker': ticker,
                                'company': company,
                                'sector': sector,
                                'change': change,
                                'volume': volume,
                            })

                            if len(results) >= limit:
                                break
                        except Exception:
                            continue

        return results

    except requests.RequestException as e:
        logger.error(f"Failed to fetch Finviz screener: {e}")
        return []


def scrape_sector_performance() -> List[Dict]:
    """
    Scrape sector performance data from Finviz groups page.
    Returns list of sectors with performance metrics.
    """
    results = []

    try:
        url = "https://finviz.com/groups.ashx?g=sector&v=140&o=-perf1w"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    first_col = cols[0]
                    link = first_col.find('a')
                    if link and 'g=sector' in str(link.get('href', '')):
                        try:
                            sector_name = link.get_text(strip=True)

                            def parse_pct(col):
                                text = col.get_text(strip=True).replace('%', '').replace(',', '')
                                try:
                                    return float(text) if text and text != '-' else 0.0
                                except ValueError:
                                    return 0.0

                            perfs = []
                            for col in cols[1:]:
                                val = parse_pct(col)
                                perfs.append(val)

                            if len(perfs) >= 6 and sector_name:
                                results.append({
                                    'sector': sector_name,
                                    'perf_1d': perfs[0] if len(perfs) > 0 else 0,
                                    'perf_1w': perfs[1] if len(perfs) > 1 else 0,
                                    'perf_1m': perfs[2] if len(perfs) > 2 else 0,
                                    'perf_3m': perfs[3] if len(perfs) > 3 else 0,
                                    'perf_6m': perfs[4] if len(perfs) > 4 else 0,
                                    'perf_1y': perfs[5] if len(perfs) > 5 else 0
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing row: {e}")
                            continue

        if not results:
            results = scrape_sector_from_map()

        results.sort(key=lambda x: x['perf_1m'], reverse=True)

        logger.info(f"Scraped {len(results)} sectors from Finviz")
        return results

    except requests.RequestException as e:
        logger.error(f"Failed to fetch Finviz data: {e}")
        return []


def scrape_sector_from_map() -> List[Dict]:
    """
    Alternative: scrape sector data from the map page.
    """
    results = []

    try:
        url = "https://finviz.com/map.ashx?t=sec"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        text = response.text

        script_pattern = re.compile(r'var\s+map_data\s*=\s*(\[.*?\]);', re.DOTALL)
        match = script_pattern.search(text)

        if match:
            try:
                data = json.loads(match.group(1))
                for item in data:
                    if isinstance(item, dict) and 'name' in item:
                        results.append({
                            'sector': item.get('name', ''),
                            'perf_1d': item.get('perf_d', 0),
                            'perf_1w': item.get('perf_w', 0),
                            'perf_1m': item.get('perf_m', 0),
                            'perf_3m': item.get('perf_q', 0),
                            'perf_6m': item.get('perf_h', 0),
                            'perf_1y': item.get('perf_y', 0)
                        })
            except json.JSONDecodeError:
                pass

        return results

    except Exception as e:
        logger.debug(f"Map scrape failed: {e}")
        return []


def scrape_top_gainers(limit: int = 20) -> List[Dict]:
    """Scrape top gaining stocks from Finviz screener (small-cap+)."""
    url = "https://finviz.com/screener.ashx?v=111&s=ta_topgainers&f=cap_smallover"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} top gainers from Finviz")
    return results


def scrape_top_losers(limit: int = 20) -> List[Dict]:
    """Scrape top losing stocks from Finviz screener (small-cap+)."""
    url = "https://finviz.com/screener.ashx?v=111&s=ta_toplosers&f=cap_smallover"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} top losers from Finviz")
    return results


def scrape_unusual_volume(limit: int = 20) -> List[Dict]:
    """Scrape stocks with unusual volume from Finviz (small-cap+)."""
    url = "https://finviz.com/screener.ashx?v=111&s=ta_unusualvolume&f=cap_smallover"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} unusual volume stocks from Finviz")
    return results


def scrape_new_highs(limit: int = 20) -> List[Dict]:
    """Scrape stocks at new highs from Finviz (small-cap+)."""
    url = "https://finviz.com/screener.ashx?v=111&s=ta_newhigh&f=cap_smallover"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} new high stocks from Finviz")
    return results


def scrape_oversold(limit: int = 20) -> List[Dict]:
    """Scrape oversold stocks (RSI < 30) from Finviz (small-cap+)."""
    url = "https://finviz.com/screener.ashx?v=111&s=ta_oversold&f=cap_smallover"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} oversold stocks from Finviz")
    return results


def scrape_overbought(limit: int = 20) -> List[Dict]:
    """Scrape overbought stocks (RSI > 70) from Finviz (small-cap+)."""
    url = "https://finviz.com/screener.ashx?v=111&s=ta_overbought&f=cap_smallover"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} overbought stocks from Finviz")
    return results


def scrape_industry_movers(finviz_industry: str, limit: int = 15) -> List[Dict]:
    """
    Scrape top movers within a specific Finviz industry.
    Used for hot themes (semiconductors, gold, biotech, etc.).
    """
    url = f"https://finviz.com/screener.ashx?v=111&f={finviz_industry},cap_smallover&o=-change"
    results = _scrape_finviz_screener(url, limit)
    logger.info(f"Found {len(results)} movers for industry {finviz_industry}")
    return results


def scan_finviz_signals(hot_themes: Optional[List[Dict]] = None) -> Dict[str, any]:
    """
    Run all Finviz scans and return aggregated results.
    If hot_themes provided, also scans industry-specific screens.
    """
    result = {
        'top_gainers': scrape_top_gainers(15),
        'top_losers': scrape_top_losers(15),
        'unusual_volume': scrape_unusual_volume(15),
        'new_highs': scrape_new_highs(15),
        'oversold': scrape_oversold(10),
        'overbought': scrape_overbought(10),
        'industry_movers': {},
    }

    # Scan industry-specific screens for hot themes
    if hot_themes:
        for theme in hot_themes:
            if theme.get('is_hot') and theme.get('finviz_industry'):
                industry = theme['finviz_industry']
                theme_name = theme['theme']
                movers = scrape_industry_movers(industry, limit=10)
                if movers:
                    result['industry_movers'][theme_name] = movers

    return result


def get_sector_etf_performance() -> List[Dict]:
    """
    Get sector performance using sector ETFs via yfinance.
    More reliable than scraping Finviz.
    """
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        sector_etfs = {
            'Technology': 'XLK',
            'Healthcare': 'XLV',
            'Financial': 'XLF',
            'Consumer Cyclical': 'XLY',
            'Communication': 'XLC',
            'Industrials': 'XLI',
            'Consumer Defensive': 'XLP',
            'Energy': 'XLE',
            'Materials': 'XLB',
            'Real Estate': 'XLRE',
            'Utilities': 'XLU'
        }

        results = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=35)

        tickers = list(sector_etfs.values())
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)

        for sector, etf in sector_etfs.items():
            try:
                if len(tickers) == 1:
                    close = data['Close']
                else:
                    close = data['Close'][etf]

                if len(close) >= 2:
                    perf_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100
                    perf_1m = ((close.iloc[-1] / close.iloc[0]) - 1) * 100

                    results.append({
                        'sector': sector,
                        'etf': etf,
                        'perf_1d': round(perf_1d, 2),
                        'perf_1w': 0,
                        'perf_1m': round(perf_1m, 2),
                        'perf_3m': 0,
                        'perf_6m': 0,
                        'perf_1y': 0
                    })
            except Exception as e:
                logger.debug(f"Error getting {sector} ETF data: {e}")
                continue

        results.sort(key=lambda x: x['perf_1m'], reverse=True)
        logger.info(f"Got {len(results)} sector performances from ETFs")
        return results

    except ImportError:
        logger.warning("yfinance not available for sector ETF data")
        return []
    except Exception as e:
        logger.error(f"Error getting sector ETF performance: {e}")
        return []


def get_sector_heatmap() -> Dict[str, float]:
    """
    Get sector performance as a simple dict for the report.
    """
    sectors = scrape_sector_performance()
    if not sectors or len(sectors) < 5:
        sectors = get_sector_etf_performance()
    return {s['sector']: s['perf_1m'] for s in sectors}


def compute_finviz_scores(signals: Dict[str, any]) -> Dict[str, Dict]:
    """
    Convert Finviz signal categories into per-ticker scores.

    Signal weights:
        top_gainers=80, new_highs=75, industry_movers=65,
        unusual_volume=60, overbought=55, oversold=40, top_losers=20

    Multi-signal bonus: +5 per additional signal type (capped at +15).
    """
    SIGNAL_WEIGHTS = {
        'top_gainers': 80,
        'new_highs': 75,
        'unusual_volume': 60,
        'overbought': 55,
        'oversold': 40,
        'top_losers': 20,
    }
    INDUSTRY_WEIGHT = 65
    MULTI_SIGNAL_BONUS = 5
    MAX_BONUS = 15

    ticker_data = {}  # ticker -> {scores: [], signals: [], change, sector}

    # Standard signal categories
    for category, weight in SIGNAL_WEIGHTS.items():
        for stock in signals.get(category, []):
            t = stock.get('ticker', '')
            if not t:
                continue
            if t not in ticker_data:
                ticker_data[t] = {
                    'scores': [], 'signals': [],
                    'change': stock.get('change', 0.0),
                    'sector': stock.get('sector', ''),
                }
            ticker_data[t]['scores'].append(weight)
            ticker_data[t]['signals'].append(category)
            # Keep the most extreme change
            if abs(stock.get('change', 0.0)) > abs(ticker_data[t]['change']):
                ticker_data[t]['change'] = stock.get('change', 0.0)

    # Industry movers (nested dict: theme -> list)
    for theme_name, movers in signals.get('industry_movers', {}).items():
        for stock in movers:
            t = stock.get('ticker', '')
            if not t:
                continue
            if t not in ticker_data:
                ticker_data[t] = {
                    'scores': [], 'signals': [],
                    'change': stock.get('change', 0.0),
                    'sector': stock.get('sector', ''),
                }
            ticker_data[t]['scores'].append(INDUSTRY_WEIGHT)
            ticker_data[t]['signals'].append(f'industry:{theme_name}')

    # Compute final score per ticker
    results = {}
    for ticker, data in ticker_data.items():
        base_score = max(data['scores'])  # Use strongest signal
        n_extra = len(data['signals']) - 1
        bonus = min(n_extra * MULTI_SIGNAL_BONUS, MAX_BONUS)
        results[ticker] = {
            'score': min(100, base_score + bonus),
            'signals': data['signals'],
            'change': data['change'],
            'sector': data['sector'],
        }

    return results


def get_finviz_tickers(signals: Dict[str, any]) -> set:
    """
    Extract all unique tickers from all Finviz signal categories.
    Used in Phase 2 (collect) of the pipeline.
    """
    tickers = set()
    for category in ['top_gainers', 'top_losers', 'unusual_volume',
                     'new_highs', 'oversold', 'overbought']:
        for stock in signals.get(category, []):
            t = stock.get('ticker', '')
            if t:
                tickers.add(t)
    for theme_name, movers in signals.get('industry_movers', {}).items():
        for stock in movers:
            t = stock.get('ticker', '')
            if t:
                tickers.add(t)
    return tickers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nSECTOR PERFORMANCE (1 Month)")
    print("-" * 40)
    sectors = scrape_sector_performance()
    if sectors:
        for sector in sectors:
            trend = "+" if sector['perf_1m'] >= 0 else ""
            print(f"{sector['sector']:25} | {trend}{sector['perf_1m']:.2f}%")
    else:
        print("Could not fetch sector data")

    print("\n\nTOP GAINERS TODAY")
    print("-" * 40)
    gainers = scrape_top_gainers(10)
    if gainers:
        for g in gainers:
            print(f"{g['ticker']:6} | {g['change']:+6.2f}% | {g.get('sector', '')}")
    else:
        print("Could not fetch gainers")

    print("\n\nTOP LOSERS TODAY")
    print("-" * 40)
    losers = scrape_top_losers(10)
    if losers:
        for l in losers:
            print(f"{l['ticker']:6} | {l['change']:+6.2f}%")
    else:
        print("Could not fetch losers")
