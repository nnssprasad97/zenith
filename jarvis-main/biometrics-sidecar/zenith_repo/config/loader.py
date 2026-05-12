from __future__ import annotations

from pathlib import Path
import os
import re

import yaml
from dotenv import load_dotenv


_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _resolve_env(value):
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if isinstance(value, str):
        match = _ENV_PATTERN.match(value.strip())
        if match:
            return os.getenv(match.group(1), "")
    return value


def load_zenith_config(path: str | Path = "config/zenith.yaml") -> dict:
    load_dotenv()
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}
    return _resolve_env(raw_config)

