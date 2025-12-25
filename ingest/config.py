"""Configuration handling for the ingest tool."""

from typing import Optional

import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "user_id": "RIi-1pAAAAAJ",
    "request_delay": 2,
}


def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from YAML file with defaults.

    Args:
        config_path: Path to config file. If None, uses config.yaml in current directory.

    Returns:
        Configuration dictionary with defaults applied.
    """
    config = DEFAULT_CONFIG.copy()

    if config_path is None:
        config_path = "config.yaml"

    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
            config.update(user_config)

    return config
