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


def youtube(textToSearch, entities=None):
    """Open a YouTube search in the browser."""
    query = urllib.parse.quote(textToSearch or "")
    if not query:
        return _respond("error")

    url = "https://www.youtube.com/results?search_query=" + query
    webbrowser.open_new_tab(url)
    return _respond("opened", {"query": textToSearch})

