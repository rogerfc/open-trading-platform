"""Agent Platform - Autonomous trading agent management."""

from pathlib import Path

__version__ = (Path(__file__).parent.parent.parent / "VERSION").read_text().strip()
