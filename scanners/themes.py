"""
Theme Scanner - Identifies hot market themes via thematic ETF momentum
Dynamically discovers which sectors/themes are trending
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

THEME_DEFINITIONS = {
    'semiconductors': {
        'etfs': ['SMH', 'SOXX', 'PSI'],
        'tickers': [
            'NVDA', 'AMD', 'INTC', 'MU', 'AVGO', 'QCOM', 'TSM', 'ASML',
            'LRCX', 'AMAT', 'KLAC', 'MRVL', 'ON', 'NXPI', 'TXN', 'ADI',
            'MCHP', 'SWKS', 'MPWR', 'ARM', 'GFS', 'SMCI'
        ],
        'finviz_industry': 'ind_semiconductors',
    },
    'precious_metals': {
        'etfs': ['GLD', 'SLV', 'GDX', 'GDXJ', 'SIL', 'SILJ'],
        'tickers': [
            'NEM', 'GOLD', 'AEM', 'WPM', 'FNV', 'RGLD', 'AG', 'PAAS',
            'KGC', 'HMY', 'EGO', 'BTG', 'CDE', 'MAG', 'HL', 'FSM'
        ],
        'finviz_industry': 'ind_gold',
    },
    'energy': {
        'etfs': ['XLE', 'XOP', 'OIH', 'USO'],
        'tickers': [
            'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY', 'MPC', 'VLO',
            'PSX', 'DVN', 'FANG', 'HAL', 'BKR', 'MRO', 'APA', 'AR',
            'RRC', 'EQT', 'CTRA'
        ],
        'finviz_industry': 'ind_oilgasexploration',
    },
    'biotech': {
        'etfs': ['XBI', 'IBB'],
        'tickers': [
            'MRNA', 'BNTX', 'REGN', 'VRTX', 'GILD', 'BIIB', 'AMGN',
            'ALNY', 'BMRN', 'IONS', 'EXAS', 'NBIX', 'ARGX', 'PCVX'
        ],
        'finviz_industry': 'ind_biotechnology',
    },
    'uranium_nuclear': {
        'etfs': ['URA', 'URNM'],
        'tickers': [
            'CCJ', 'UEC', 'DNN', 'LEU', 'NXE', 'UUUU', 'SMR'
        ],
        'finviz_industry': 'ind_uranium',
    },
    'steel_materials': {
        'etfs': ['SLX', 'XME', 'PICK'],
        'tickers': [
            'CLF', 'NUE', 'STLD', 'X', 'RS', 'AA', 'CENX', 'FCX',
            'SCCO', 'VALE', 'RIO', 'BHP', 'TECK'
        ],
        'finviz_industry': 'ind_steel',
    },
    'defense': {
        'etfs': ['ITA', 'PPA', 'XAR'],
        'tickers': [
            'LMT', 'RTX', 'NOC', 'GD', 'BA', 'LHX', 'HII', 'TDG',
            'HWM', 'KTOS', 'PLTR', 'RKLB'
        ],
        'finviz_industry': 'ind_aerospacedefense',
    },
    'china_tech': {
        'etfs': ['KWEB', 'FXI', 'MCHI'],
        'tickers': [
            'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI',
            'TME', 'IQ'
        ],
        'finviz_industry': None,
    },
    'cannabis': {
        'etfs': ['MSOS', 'MJ'],
        'tickers': ['TLRY', 'CGC', 'ACB', 'CRON', 'SNDL'],
        'finviz_industry': None,
    },
}


def scan_theme_etf_momentum(theme_name: str, etf_list: List[str]) -> Dict:
    """
    Scan momentum for a theme's ETFs.
    Returns theme performance data.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=35)

    etf_perf = []

    try:
        data = yf.download(etf_list, start=start_date, end=end_date, progress=False)

        for etf in etf_list:
            try:
                if len(etf_list) == 1:
                    close = data['Close']
                else:
                    close = data['Close'][etf]

                if close.empty or len(close) < 2:
                    continue

                perf_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100
                perf_1w = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0
                perf_1m = ((close.iloc[-1] / close.iloc[0]) - 1) * 100

                etf_perf.append({
                    'etf': etf,
                    'price': round(close.iloc[-1], 2),
                    'perf_1d': round(perf_1d, 2),
                    'perf_1w': round(perf_1w, 2),
                    'perf_1m': round(perf_1m, 2),
                })
            except Exception as e:
                logger.debug(f"Error processing ETF {etf}: {e}")
                continue

    except Exception as e:
        logger.error(f"Failed to download ETF data for {theme_name}: {e}")

    # Calculate average performance across theme ETFs
    if etf_perf:
        avg_1d = sum(e['perf_1d'] for e in etf_perf) / len(etf_perf)
        avg_1w = sum(e['perf_1w'] for e in etf_perf) / len(etf_perf)
        avg_1m = sum(e['perf_1m'] for e in etf_perf) / len(etf_perf)
    else:
        avg_1d = avg_1w = avg_1m = 0

    # A theme is "hot" if any ETF is >5% monthly or >2% weekly
    is_hot = any(
        e['perf_1m'] > 5 or e['perf_1w'] > 2
        for e in etf_perf
    )

    return {
        'theme': theme_name,
        'etf_perf': etf_perf,
        'avg_1d': round(avg_1d, 2),
        'avg_1w': round(avg_1w, 2),
        'avg_1m': round(avg_1m, 2),
        'is_hot': is_hot,
        'tickers': THEME_DEFINITIONS[theme_name]['tickers'],
        'finviz_industry': THEME_DEFINITIONS[theme_name].get('finviz_industry'),
    }


def discover_hot_themes() -> List[Dict]:
    """
    Scan all themes and return sorted by performance.
    """
    results = []

    # Batch download all ETFs at once for efficiency
    all_etfs = []
    for theme_def in THEME_DEFINITIONS.values():
        all_etfs.extend(theme_def['etfs'])
    all_etfs = list(set(all_etfs))

    logger.info(f"Scanning {len(all_etfs)} thematic ETFs across {len(THEME_DEFINITIONS)} themes...")

    for theme_name, theme_def in THEME_DEFINITIONS.items():
        result = scan_theme_etf_momentum(theme_name, theme_def['etfs'])
        results.append(result)

    # Sort by average 1-month performance
    results.sort(key=lambda x: x['avg_1m'], reverse=True)

    hot_count = sum(1 for r in results if r['is_hot'])
    logger.info(f"Theme scan complete: {hot_count}/{len(results)} themes are hot")

    return results


def get_theme_tickers(hot_themes: List[Dict]) -> List[str]:
    """
    Collect all tickers from hot themes for injection into momentum scanner.
    """
    tickers = []
    for theme in hot_themes:
        if theme['is_hot']:
            tickers.extend(theme['tickers'])
    return list(set(tickers))


def scan_themes() -> Dict:
    """
    Main entry point for theme scanning.
    Returns hot themes data and tickers to inject.
    """
    hot_themes = discover_hot_themes()
    theme_tickers = get_theme_tickers(hot_themes)

    return {
        'hot_themes': hot_themes,
        'theme_tickers': theme_tickers,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nTHEMATIC ETF MOMENTUM SCAN")
    print("=" * 70)

    results = scan_themes()

    for theme in results['hot_themes']:
        hot_marker = " *** HOT ***" if theme['is_hot'] else ""
        print(f"\n{theme['theme'].upper()}{hot_marker}")
        print(f"  Avg 1M: {theme['avg_1m']:+.2f}%  |  Avg 1W: {theme['avg_1w']:+.2f}%")
        for etf in theme['etf_perf']:
            print(f"    {etf['etf']:6} ${etf['price']:>8.2f}  "
                  f"1D: {etf['perf_1d']:+6.2f}%  "
                  f"1W: {etf['perf_1w']:+6.2f}%  "
                  f"1M: {etf['perf_1m']:+6.2f}%")

    print(f"\n\nHot theme tickers to scan: {len(results['theme_tickers'])}")
    print(', '.join(sorted(results['theme_tickers'])))
