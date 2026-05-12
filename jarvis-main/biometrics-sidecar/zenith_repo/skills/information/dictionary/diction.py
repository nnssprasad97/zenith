#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from random import choice
import json
import urllib.parse

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


def translate(word, entities=None):
    """Look up a dictionary definition for a word."""
    query = (word or "").strip().lower()
    if not query:
        return _respond("error")

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(query)}"
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        return _respond("not_found", {"word": query})

    data = response.json()
    try:
        meaning = data[0]["meanings"][0]
        part_of_speech = meaning["partOfSpeech"]
        definition = meaning["definitions"][0]["definition"]
    except (KeyError, IndexError, TypeError):
        return _respond("not_found", {"word": query})

    return _respond(
        "definition",
        {"word": query, "part_of_speech": part_of_speech, "definition": definition}
    )

