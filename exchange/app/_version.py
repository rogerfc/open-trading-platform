"""Centralized version management for the Stock Exchange."""

from pathlib import Path

# Path: _version.py -> app -> /app (in container) or exchange (local)
# Try both locations for compatibility
_version_file = Path(__file__).parent.parent / "VERSION"
if not _version_file.exists():
    _version_file = Path(__file__).parent.parent.parent / "VERSION"
VERSION = _version_file.read_text().strip() if _version_file.exists() else "0.0.0"
