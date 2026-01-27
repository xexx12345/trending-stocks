"""
Shared ticker blacklist — replaces per-scanner whitelists.

Two-tier filtering:
- $TICKER patterns (high confidence): only block TICKER_BLACKLIST
- Standalone TICKER (lower confidence): also block 1-2 letter unless in ALLOW_SHORT_TICKERS
"""

import re
from typing import Set

# Common English words, finance jargon, Reddit-isms, and trading verbs
# that look like tickers but aren't.
TICKER_BLACKLIST = frozenset([
    # English words
    "THE", "FOR", "AND", "ALL", "NEW", "HIGH", "LOW", "LONG", "JUST", "BACK",
    "WELL", "GOOD", "BEST", "EVER", "EVEN", "ONLY", "VERY", "MUCH", "MOST",
    "MANY", "SOME", "LAST", "NEXT", "OVER", "LIKE", "JUST", "KNOW", "TAKE",
    "MAKE", "COME", "LOOK", "WANT", "GIVE", "TELL", "WORK", "CALL", "NEED",
    "WILL", "EACH", "THEM", "THEN", "THAN", "BEEN", "HAVE", "FROM", "WERE",
    "BEEN", "SAID", "DOES", "INTO", "ALSO", "MORE", "WHEN", "WITH", "WHAT",
    "THIS", "THAT", "YOUR", "THEY", "MADE", "REAL", "HARD", "EASY", "HUGE",
    "SAFE", "FAST", "MOVE", "PLAY", "FREE", "TRUE", "PART", "FULL", "DONE",
    "SAME", "HERE", "KEEP", "HELP", "TALK", "TURN", "LIVE", "FEEL", "NICE",
    "SURE", "OPEN", "LOST", "FEAR", "PLAN", "LATE", "MEAN", "RATE", "STOP",
    "MUST", "NEAR", "SENT", "POST", "READ", "CASH", "RICH", "POOR", "SAVE",
    "FUND", "WEEK", "YEAR", "DAYS", "TIME", "NEWS", "DATA", "FIND", "PICK",
    "DROP", "GRAB", "LAND", "ZERO", "TANK", "GOLD", "ROCK", "FIRE", "PURE",
    "LINK", "MIND", "CORE", "EDGE", "PATH", "SELF", "LIFE", "DEEP", "VAST",
    "RARE", "WISE", "FLAT", "DUMB", "YALL", "HAHA", "LMAO", "IIRC", "FWIW",
    "IMHO",
    # Note: GOLD is blacklisted for standalone because "gold" is too common.
    # Barrick Gold ($GOLD) is caught via $prefix or company-name matching.

    # Finance jargon
    "CEO", "CFO", "COO", "CTO", "IPO", "ETF", "SEC", "FDA", "EPS", "ATH",
    "GDP", "CPI", "RSI", "MACD", "VWAP", "SMA", "EMA", "EBIT", "GAAP",
    "NAV", "AUM", "OTC", "NYSE", "AMEX", "FTSE", "DJIA", "FOMC", "FDIC",
    "SPAC", "REIT", "PIPE", "SPX", "DXY", "VIX", "CBOE", "FINR",
    "ROIC", "WACC", "CAGR", "DCF", "EBITDA",

    # Reddit-isms
    "YOLO", "FOMO", "HODL", "TLDR", "LMAO", "ROFL", "IMHO", "IIRC",
    "WSB", "DD", "TA", "OTM", "ITM", "ATM", "DTE", "LEAPS", "FD",
    "APE", "APES", "DEFI", "NFT", "NFTS", "DYOR",

    # Trading verbs / nouns
    "BUY", "SELL", "HOLD", "CALL", "PUTS", "BULL", "BEAR", "PUMP", "DUMP",
    "MOON", "GAIN", "LOSS", "LONG", "SHORT", "LEAP", "RISK", "BETA",
    "TOPS", "DIPS", "PUTS", "BANG", "YUGE", "BAGS", "ROPE",

    # Common abbreviations
    "USA", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY",
    "IRS", "DOJ", "FBI", "CIA", "CDC", "EPA", "DOD", "DOE",
    "IMF", "WHO", "NATO", "OPEC",
    "INC", "LLC", "LTD", "CORP", "MGMT",
    "EST", "PST", "CST", "UTC",
    "PDF", "API", "SQL", "URL", "AWS", "APP", "APPS",
    "LOL", "OMG", "WTF", "BTW", "FYI", "TBH", "SMH",
    "RIP", "MVP", "GOAT", "OG",
    "PM", "AM", "CEO", "VP",
    "AI",  # Too ambiguous standalone; use $AI or company-name match for C3.ai
])

# Well-known 1-2 letter tickers that should be allowed even though they're short.
# These pass through even without a $ prefix.
ALLOW_SHORT_TICKERS = frozenset([
    "F",   # Ford
    "V",   # Visa
    "C",   # Citigroup
    "X",   # US Steel
    "T",   # AT&T
    "GE",  # GE Aerospace
    "GM",  # General Motors
    "BA",  # Boeing
    "AA",  # Alcoa
    "AG",  # First Majestic Silver
    "ON",  # ON Semiconductor
    "MU",  # Micron
    "GS",  # Goldman Sachs
    "MS",  # Morgan Stanley
    "HD",  # Home Depot
    "LI",  # Li Auto
    "JD",  # JD.com
    "HL",  # Hecla Mining
    "DB",  # Deutsche Bank
    "NIO", # keep as reminder — 3-letter, passes by default
])

# Regex: $TICKER (2-5 letters) or standalone TICKER (2-5 uppercase letters)
_DOLLAR_PATTERN = re.compile(r'\$([A-Z]{2,5})\b')
_STANDALONE_PATTERN = re.compile(r'(?<![A-Za-z])([A-Z]{2,5})(?![a-z])\b')


def is_valid_ticker(candidate: str, has_dollar_prefix: bool = False) -> bool:
    """
    Check whether a candidate string is likely a real ticker.

    Args:
        candidate: Uppercase string, e.g. "NVDA"
        has_dollar_prefix: True if extracted from $TICKER pattern (higher confidence)

    Returns:
        True if the candidate should be treated as a ticker.
    """
    if not candidate or not candidate.isalpha():
        return False

    length = len(candidate)

    # Too long or too short
    if length > 5 or length < 1:
        return False

    # Always block blacklisted words regardless of prefix
    if candidate in TICKER_BLACKLIST:
        return False

    # For standalone (no $), require 3+ letters unless explicitly allowed
    if not has_dollar_prefix and length <= 2:
        return candidate in ALLOW_SHORT_TICKERS

    return True


def extract_tickers_from_text(text: str) -> Set[str]:
    """
    Extract plausible ticker symbols from free text.

    Uses two passes:
    1. $TICKER patterns — high confidence, only blocked by TICKER_BLACKLIST
    2. Standalone UPPERCASE words — also blocked if 1-2 letters and not in ALLOW_SHORT_TICKERS

    Returns:
        Set of valid ticker strings.
    """
    tickers = set()
    upper_text = text.upper()

    # Pass 1: $TICKER — high confidence
    for match in _DOLLAR_PATTERN.finditer(upper_text):
        candidate = match.group(1)
        if is_valid_ticker(candidate, has_dollar_prefix=True):
            tickers.add(candidate)

    # Pass 2: standalone uppercase words
    for match in _STANDALONE_PATTERN.finditer(text):
        candidate = match.group(1)
        # Only consider if it's actually all-uppercase in the original text
        if candidate == candidate.upper() and is_valid_ticker(candidate, has_dollar_prefix=False):
            tickers.add(candidate)

    return tickers
