"""Centralized version management for the Stock Exchange."""

from pathlib import Path

# Path: _version.py -> app -> exchange -> StockExchange
VERSION = (Path(__file__).parent.parent.parent / "VERSION").read_text().strip()
