#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from random import choice
import json

import wikipedia


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


def search_wikipedia(string, entities):
    """Search Wikipedia and return a concise summary."""
    query = string.strip()
    if not query:
        return _respond("error")

    try:
        summary = wikipedia.summary(query, sentences=2, auto_suggest=True)
        return _respond("summary", {"topic": query, "summary": summary})
    except wikipedia.DisambiguationError as exc:
        options = ", ".join(exc.options[:3])
        return _respond("disambiguation", {"topic": query, "options": options})
    except wikipedia.PageError:
        return _respond("not_found", {"topic": query})

