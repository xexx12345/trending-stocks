# Trending Stocks Scanner - Recommendations

Review date: 2025-02-10

## Overview

This document contains recommendations for improving the Trending Stocks Scanner codebase, organized by priority level. The scanner is well-structured but lacks testing, documentation, and some implementation details.

---

## Critical Issues (Fix Immediately)

### 1. Missing Cache Implementation

**Issue:** `config.yaml` defines `cache.enabled: true` and `cache.ttl_minutes: 60` but there's no caching code in the codebase.

**Impact:** Users expect caching to work based on config, leading to confusion and wasted API calls.

**Recommendations:**
- Implement simple file-based or SQLite caching keyed by `(scanner_name, date, params_hash)`
- Honor TTL from config
- Add `--no-cache` CLI flag to force refresh
- **OR** Remove dead cache config entirely to avoid confusion

**Effort:** 4-6 hours

---

### 2. Zero Test Coverage

**Issue:** No tests exist for any scanner or scoring logic in a financial tool.

**Impact:** Risk of bugs in critical calculations (momentum, RSI, scoring) that could lead to incorrect trading signals.

**Recommendations:**
- Set up pytest framework
- Add unit tests for each module
- Add integration tests for full pipeline
- Add tests for edge cases (empty data, API failures, malformed responses)

**Priority tests to add:**
1. Scoring logic (weight normalization, multi-source bonus)
2. Momentum calculations (RSI, breakouts, trend quality)
3. Ticker extraction from text
4. Error handling and graceful degradation

**Effort:** 8-12 hours

**Example test structure:**
```
tests/
├── test_scoring.py
├── test_momentum.py
├── test_reddit.py
├── test_news.py
├── test_finviz.py
└── test_integration.py
```

---

### 3. Missing Environment Documentation

**Issue:** `.env` is in `.gitignore` but `.env.example` exists without clear instructions.

**Impact:** Users don't know what API keys are required and how to configure them.

**Recommendations:**
- Document all environment variables in README
- Create a comprehensive `.env.example` with descriptions
- Add setup instructions for each API (Reddit, Perplexity optional)
- Add validation on startup for missing required keys

**Effort:** 1-2 hours

---

## High Priority (Significant Impact)

### 4. Refactor Main.py (Too Large)

**Issue:** `main.py` is 1059 lines with mixed concerns (CLI, orchestration, output, caching).

**Impact:** Hard to maintain, test, and understand. Violates single responsibility principle.

**Recommendations:**
- Create `pipeline/scanner_pipeline.py` for scan orchestration
- Create `output/output_handler.py` for report generation
- Create `output/data_saver.py` for JSON/CSV saving
- Keep `main.py` focused on CLI parsing only

**New structure:**
```
main.py (~100 lines)
├── CLI parsing
└── Pipeline orchestration

pipeline/
├── scanner_pipeline.py
└── phase_executor.py

output/
├── output_handler.py
├── data_saver.py
└── report_formatter.py
```

**Effort:** 6-8 hours

---

### 5. Add Type Hints Throughout

**Issue:** Only `main.py` and `utils/scoring.py` have type hints. Scanner modules lack them.

**Impact:** Poor IDE support, harder to catch bugs early, unclear function contracts.

**Recommendations:**
- Add type hints to all scanner functions
- Use `typing` module for complex types (Dict, List, Optional, Set, Tuple)
- Use `TypedDict` for structured data where appropriate
- Run mypy in CI to enforce type checking

**Effort:** 4-6 hours

---

### 6. Improve Logging Configuration

**Issue:** Uses basic `logging.basicConfig()` without file logging or configurability.

**Impact:** No audit trail, hard to debug issues after the fact, can't adjust verbosity.

**Recommendations:**
- Add file logging to `output/logs/`
- Make log levels configurable via config.yaml
- Add structured logging (JSON format) for machine parsing
- Add request/response logging for API calls (with sensitive data redacted)
- Add rotation to prevent large log files

**Effort:** 3-4 hours

**Example config:**
```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file_enabled: true
  file_path: output/logs/scanner.log
  max_bytes: 10485760  # 10MB
  backup_count: 5
```

---

### 7. Improve Error Recovery

**Issue:** Scanners fail silently or crash entire pipeline on individual failures.

**Impact:** One failed source breaks entire scan, no partial results.

**Recommendations:**
- Add retry with exponential backoff for HTTP calls
- Graceful degradation: continue if one source fails
- Better error messages for missing API keys
- Track and report failed sources in final output
- Add `--continue-on-error` flag

**Effort:** 4-5 hours

---

## Medium Priority (Quality of Life)

### 8. Add CLI Flags for Partial Runs

**Issue:** Users must run full scan every time, which can be slow when only interested in specific sources.

**Impact:** Wasted time when testing or debugging specific scanners.

**Recommendations:**
```bash
python main.py --no-momentum      # Skip yfinance downloads (slow)
python main.py --longs-only       # Skip short candidates pipeline
python main.py --shorts-only      # Skip long scoring
python main.py --skip-history     # Don't save raw data
python main.py --sources reddit,news  # Run specific sources only
```

**Effort:** 2-3 hours

---

### 9. Parallelize Scanner Execution

**Issue:** All scanners run sequentially. Many are independent (reddit, news, finviz, google_trends, perplexity).

**Impact:** Pipeline currently takes 3-5 minutes. Could be under 2 minutes with parallelization.

**Recommendations:**
- Use `concurrent.futures.ThreadPoolExecutor`
- Group Phase 1 scanners into parallel batches
- Respect rate limits with per-domain semaphores
- Phase 3 enrichment can also parallelize (short_interest, options are per-ticker)

**Effort:** 4-6 hours

---

### 10. Create README.md

**Issue:** No README exists. Users don't know how to set up, install, or run the scanner.

**Impact:** High barrier to entry, potential users may give up.

**Recommendations:**
- Installation steps (Python version, pip install)
- Required API keys setup (Reddit, optional Perplexity)
- Quick start guide
- Example output
- Troubleshooting section
- Link to this recommendations file

**Effort:** 2-3 hours

---

### 11. Add Health Check Command

**Issue:** No way to verify all APIs are configured before running full scan.

**Impact:** Users discover missing API keys only after running for several minutes.

**Recommendations:**
```bash
python main.py --health
```

Should verify:
- Reddit API credentials
- Perplexity API key (if enabled)
- yfinance connectivity
- Config file validity

**Effort:** 1-2 hours

---

## Low Priority (Nice to Have)

### 12. Add Performance Metrics

Track and display scan time per source to identify bottlenecks.

**Effort:** 1-2 hours

---

### 13. Pre-commit Hooks

Add formatting (black, ruff) and linting to maintain code quality.

**Effort:** 1 hour

---

### 14. Docker Support

Containerize for consistent execution environments.

**Effort:** 3-4 hours

---

### 15. Add Watchlist Persistence

Save and restore user watchlists between runs.

**Effort:** 2-3 hours

---

## Quick Wins (< 2 hours each)

1. Add `^VIX` and `HYG` to baseline watchlist (already suggested in momentum.py comments)
2. Implement basic file-based caching
3. Add retry logic to HTTP scanners (finviz, insider, congress)
4. Create `tests/` directory with pytest skeleton
5. Write comprehensive README.md with setup instructions
6. Add CLI flag to display config currently being used
7. Add timestamp to all output filenames for better organization
8. Add progress bars for long-running operations

---

## Top 3 to Start With

Based on impact vs effort ratio, start with these:

1. **Write README.md** (2-3 hours) - Enables users to actually use the tool
2. **Implement basic caching** (4-6 hours) - Eliminates confusion, speeds up re-runs
3. **Add test skeleton and key tests** (8-12 hours) - Ensures reliability of financial calculations

---

## Summary

| Priority | Issues | Total Effort |
|----------|--------|--------------|
| Critical | 3 | 13-20 hours |
| High | 4 | 17-23 hours |
| Medium | 4 | 9-14 hours |
| Low | 4 | 7-10 hours |
| Quick Wins | 8 | 16 hours |
| **Total** | **23** | **62-83 hours** |

---

## Notes from IMPROVEMENTS.md

The existing `IMPROVEMENTS.md` file contains many excellent suggestions, particularly around:

- Backtest Tracker (Tier 1) - Validate that yesterday's picks actually worked
- Earnings & Event Calendar Filter (Tier 1) - Avoid being blindsided by earnings
- Multi-Day Trend Tracking (Tier 1) - Distinguish real trends from one-day noise
- Source Independence Score (Tier 1) - Prevent illusion of confirmation from redundant signals

Those are all high-value features that should be prioritized after addressing the critical issues above.
