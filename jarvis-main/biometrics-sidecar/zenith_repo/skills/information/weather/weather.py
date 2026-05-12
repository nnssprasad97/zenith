#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from random import choice
import json
import re

import requests


SKILL_DIR = Path(__file__).resolve().parent
ANSWERS_PATH = SKILL_DIR / "data" / "answers" / "en.json"


def _answers() -> dict:
    with ANSWERS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _respond(key: str, replacements: dict | None = None) -> dict:
    template = choice(_answers()[key])
    for name, value in (replacements or {}).items():
        template = template.replace(f"%{name}%", str(value))
    return {"type": "end", "key": key, "speech": template}


def _extract_location(string: str) -> str:
    match = re.search(r"(?:in|for|at)\s+(.+)$", string, re.IGNORECASE)
    return match.group(1).strip() if match else "auto:ip"


def get_weather(string, entities):
    """Return the current weather for a place or the caller IP location."""
    location = _extract_location(string or "")
    url = f"https://wttr.in/{location}?format=j1"

    try:
        data = requests.get(url, timeout=15).json()
        current = data["current_condition"][0]
        nearest = data.get("nearest_area", [{}])[0]
        area = nearest.get("areaName", [{"value": location}])[0]["value"]
        country = nearest.get("country", [{"value": ""}])[0]["value"]
        summary = current["weatherDesc"][0]["value"]
        temperature = current["temp_C"]
        humidity = current["humidity"]
    except (KeyError, IndexError, ValueError, TypeError, requests.RequestException):
        return _respond("error", {"location": location})

    label = area if not country else f"{area}, {country}"
    return _respond(
        "weather",
        {
            "location": label,
            "summary": summary,
            "temperature": temperature,
            "humidity": humidity
        }
    )

