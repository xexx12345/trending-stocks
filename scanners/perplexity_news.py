"""
Perplexity News Scanner - AI-powered news discovery via Perplexity API.

Uses Perplexity's sonar model with web search grounding to discover
trending stocks from real-time news sources.

Cost: ~$0.005-0.015 per scan (~$0.30-0.90/month at 2 scans/day)
Requires: PERPLEXITY_API_KEY environment variable
"""

import logging
import os
import re
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Perplexity API endpoint
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Queries to discover trending stocks
DISCOVERY_QUERIES = [
    "What stocks are trending in financial news today? List specific ticker symbols.",
    "Which stocks had unusual volume or significant price movements today? Include ticker symbols.",
    "What companies announced major news (earnings, FDA approvals, contracts) this week? Include ticker symbols.",
]

# Common stock ticker pattern
TICKER_PATTERN = re.compile(r'\b([A-Z]{1,5})\b')

# Known non-ticker uppercase words to filter out
NON_TICKERS = {
    'AI', 'IPO', 'ETF', 'CEO', 'CFO', 'COO', 'CTO', 'NYSE', 'NASDAQ', 'SEC',
    'FDA', 'API', 'USA', 'US', 'UK', 'EU', 'GDP', 'CPI', 'EPS', 'PE', 'ROI',
    'YTD', 'QTD', 'MOM', 'YOY', 'THE', 'AND', 'FOR', 'ARE', 'WAS', 'HAS',
    'ITS', 'NEW', 'TOP', 'BUY', 'SELL', 'HOLD', 'NOT', 'ALL', 'TODAY', 'THIS',
}


def _get_api_key() -> Optional[str]:
    """Get Perplexity API key from environment."""
    return os.environ.get('PERPLEXITY_API_KEY')


def _extract_tickers(text: str) -> List[str]:
    """Extract potential stock tickers from text."""
    matches = TICKER_PATTERN.findall(text)
    tickers = []

    for match in matches:
        # Filter out common non-ticker words
        if match not in NON_TICKERS and len(match) >= 1:
            tickers.append(match)

    return list(set(tickers))


def _analyze_sentiment(text: str) -> str:
    """Simple sentiment analysis based on keywords."""
    text_lower = text.lower()

    positive_words = ['surge', 'soar', 'gain', 'rally', 'beat', 'record', 'strong', 'positive', 'growth', 'up']
    negative_words = ['drop', 'fall', 'decline', 'miss', 'weak', 'negative', 'down', 'concern', 'warning']

    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)

    if pos_count > neg_count + 1:
        return 'very_positive'
    elif pos_count > neg_count:
        return 'positive'
    elif neg_count > pos_count + 1:
        return 'very_negative'
    elif neg_count > pos_count:
        return 'negative'
    else:
        return 'neutral'


def _has_catalyst(text: str) -> bool:
    """Check if text mentions a potential catalyst."""
    text_lower = text.lower()
    catalyst_keywords = [
        'earnings', 'beat', 'revenue', 'guidance', 'fda', 'approval',
        'contract', 'partnership', 'acquisition', 'merger', 'buyback',
        'dividend', 'split', 'upgrade', 'analyst', 'target', 'announcement',
    ]
    return any(keyword in text_lower for keyword in catalyst_keywords)


def _calculate_perplexity_score(
    mention_count: int,
    sentiment: str,
    has_catalyst: bool,
) -> float:
    """
    Calculate Perplexity discovery score (0-100).

    Scoring logic:
    - Base: 50
    - Mention count: +5 per mention (max +20)
    - Sentiment: very_positive = +15, positive = +10, negative = -5
    - Has catalyst: +15
    """
    score = 50.0

    # Mention count bonus
    score += min(20, mention_count * 5)

    # Sentiment adjustment
    if sentiment == 'very_positive':
        score += 15
    elif sentiment == 'positive':
        score += 10
    elif sentiment == 'negative':
        score -= 5
    elif sentiment == 'very_negative':
        score -= 10

    # Catalyst bonus
    if has_catalyst:
        score += 15

    return min(100.0, max(0.0, score))


def query_perplexity(query: str) -> Optional[Dict]:
    """
    Query Perplexity API with a single prompt.

    Args:
        query: The question to ask Perplexity

    Returns:
        Dict with response content and sources, or None if failed
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("PERPLEXITY_API_KEY not set, skipping Perplexity scan")
        return None

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    payload = {
        'model': 'sonar',
        'messages': [
            {
                'role': 'system',
                'content': 'You are a financial news analyst. When mentioning stocks, always include their ticker symbols in parentheses, e.g., Apple (AAPL). Be specific and concise.',
            },
            {
                'role': 'user',
                'content': query,
            }
        ],
        'max_tokens': 500,
        'temperature': 0.1,
    }

    try:
        response = requests.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')

        # Extract sources if available (Perplexity includes citations)
        sources = []
        if 'citations' in data:
            sources = data.get('citations', [])

        return {
            'content': content,
            'sources': sources,
        }

    except requests.RequestException as e:
        logger.warning(f"Perplexity API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Error querying Perplexity: {e}")
        return None


def scan_perplexity(queries: Optional[List[str]] = None) -> List[Dict]:
    """
    Scan for trending stocks using Perplexity AI.

    Args:
        queries: Optional list of queries to run (defaults to DISCOVERY_QUERIES)

    Returns:
        List of dicts with ticker, score, sentiment, and summary
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("PERPLEXITY_API_KEY not set, skipping Perplexity scan")
        return []

    if queries is None:
        queries = DISCOVERY_QUERIES

    logger.info(f"Running Perplexity scan with {len(queries)} queries...")

    # Track ticker mentions across all queries
    ticker_data = {}
    all_content = []

    for query in queries:
        result = query_perplexity(query)

        if result and result['content']:
            content = result['content']
            all_content.append(content)

            # Extract tickers from response
            tickers = _extract_tickers(content)

            for ticker in tickers:
                if ticker not in ticker_data:
                    ticker_data[ticker] = {
                        'ticker': ticker,
                        'mention_count': 0,
                        'summaries': [],
                        'sources': [],
                    }

                ticker_data[ticker]['mention_count'] += 1
                # Store relevant snippet
                ticker_data[ticker]['summaries'].append(content[:200])
                ticker_data[ticker]['sources'].extend(result.get('sources', []))

    if not ticker_data:
        logger.info("No tickers discovered from Perplexity")
        return []

    # Combine all content for sentiment analysis per ticker
    combined_content = ' '.join(all_content)

    # Build final results
    results = []
    for ticker, data in ticker_data.items():
        # Find ticker-specific context for sentiment
        ticker_context = ''
        for summary in data['summaries']:
            if ticker in summary:
                ticker_context += summary + ' '

        sentiment = _analyze_sentiment(ticker_context or combined_content)
        has_cat = _has_catalyst(ticker_context or combined_content)

        score = _calculate_perplexity_score(
            mention_count=data['mention_count'],
            sentiment=sentiment,
            has_catalyst=has_cat,
        )

        results.append({
            'ticker': ticker,
            'score': round(score, 1),
            'mention_count': data['mention_count'],
            'sentiment': sentiment,
            'has_catalyst': has_cat,
            'summary': data['summaries'][0][:100] + '...' if data['summaries'] else '',
            'sources': list(set(data['sources']))[:3],
        })

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)

    logger.info(f"Perplexity scan discovered {len(results)} tickers")
    return results


def get_perplexity_tickers() -> List[str]:
    """Get list of tickers discovered from Perplexity scan (for pipeline integration)."""
    results = scan_perplexity()
    return [r['ticker'] for r in results]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nPERPLEXITY NEWS SCAN")
    print("-" * 70)

    api_key = _get_api_key()
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY environment variable not set")
        print("Set it with: export PERPLEXITY_API_KEY=pplx-xxxxx")
    else:
        results = scan_perplexity()

        if results:
            print(f"\nTrending Stocks (via Perplexity AI):\n")
            print(f"{'Ticker':<8} {'Score':<8} {'Mentions':<10} {'Sentiment':<15} {'Catalyst':<10} {'Summary'}")
            print("-" * 90)
            for r in results[:15]:
                cat_str = 'Yes' if r['has_catalyst'] else 'No'
                summary = r['summary'][:35] + '...' if len(r['summary']) > 35 else r['summary']
                print(f"{r['ticker']:<8} {r['score']:<8.1f} {r['mention_count']:<10} "
                      f"{r['sentiment']:<15} {cat_str:<10} {summary}")
        else:
            print("No trending stocks discovered")
