#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from random import choice
import json
import urllib.parse
import webbrowser


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


def open_website(string, entities):
    """Open a website by name."""
    websites = {
        "youtube": "https://youtube.com",
        "github": "https://github.com",
        "google": "https://google.com",
        "gmail": "https://mail.google.com",
        "maps": "https://maps.google.com",
        "stackoverflow": "https://stackoverflow.com"
    }

    target = (string or "").lower()
    for name, url in websites.items():
        if name in target:
            webbrowser.open(url)
            return _respond("opened", {"site": name})

    search_url = f"https://www.google.com/search?q={urllib.parse.quote(string or '')}"
    webbrowser.open(search_url)
    return _respond("searched", {"query": string})


def search_web(string, entities):
    """Search the web."""
    query = string
    for entity in entities or []:
        if entity.get("entity") == "query":
            query = entity.get("sourceText", string)
            break

    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query or '')}"
    webbrowser.open(search_url)
    return _respond("searched", {"query": query})

