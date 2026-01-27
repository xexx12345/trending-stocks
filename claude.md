# Trending Stocks Project

A tool to identify trending stocks each morning through multiple data sources.

## Project Overview

This project aggregates trending stock information from:
- Technical momentum indicators
- Reddit discussions (r/wallstreetbets, r/stocks, r/investing)
- News mentions and sentiment
- Finviz sector heatmaps

## Key Commands

- Run daily scan: `python main.py`
- Run specific source: `python main.py --source [momentum|reddit|news|finviz]`

## Development Guidelines

- Keep API rate limits in mind for Reddit and news sources
- Cache results to avoid redundant API calls
- Output should be concise and actionable for morning review
