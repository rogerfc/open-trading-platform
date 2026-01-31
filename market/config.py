"""Configuration file management for market CLI."""

from pathlib import Path

import yaml

CONFIG_FILENAME = ".market.yaml"
USER_CONFIG_DIR = Path.home() / ".market"


def find_config() -> Path | None:
    """Find config file (project first, then user).

    Returns:
        Path to config file if found, None otherwise.
    """
    # Check project root (current directory)
    project_config = Path(CONFIG_FILENAME)
    if project_config.exists():
        return project_config

    # Check user config
    user_config = USER_CONFIG_DIR / "config.yaml"
    if user_config.exists():
        return user_config

    return None


def load_config() -> dict:
    """Load config from file.

    Returns:
        Config dictionary, or empty dict if no config found.
    """
    path = find_config()
    if path is None:
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict, path: Path | None = None) -> Path:
    """Save config to file.

    Args:
        config: Config dictionary to save.
        path: Path to save to. Defaults to project config file.

    Returns:
        Path where config was saved.
    """
    if path is None:
        path = Path(CONFIG_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    return path


def get_default_config() -> dict:
    """Get default configuration values.

    Returns:
        Dictionary with default config values.
    """
    return {
        "exchange_url": "http://localhost:8000",
        "agents_url": "http://localhost:8001",
        "grafana_url": "http://localhost:3000",
        "grafana_api_key": "",
        "grafana_folder": "",
    }
