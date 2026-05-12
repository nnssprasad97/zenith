# ZENITH — Complete Build Instructions

> Your open-source, Tony Stark-inspired AI assistant.
> Built on 4 real repositories. No unnecessary rewrites.

---

## OVERVIEW

Zenith is assembled from four source repositories:

| Repo | What you take | Reuse % |
|------|--------------|---------|
| `leon-ai/leon` | Skills architecture, NLU engine, hotword, web app skeleton, bridges, HTTP API | ~90% |
| `SAGAR-TAMANG/friday-tony-stark-demo` | FastMCP server, voice pipeline (LiveKit), Gemini LLM integration, SSE tool registry | ~85% |
| `vierisid/jarvis` | LLMManager fallback pattern, YAML config system | ~70% |
| `GauravSingh9356/J.A.R.V.I.S` | Tool logic scripts (news, wiki, weather, OCR, YouTube, email, face recognition) | ~90% of scripts |

**Golden rule**: If it exists and works, copy it. Only write new code for the glue between parts.

---

## PART 1 — WHAT TO COPY FROM EACH REPOSITORY

### 1.1 From `leon-ai/leon` (use `master` branch — stable)

Clone it separately:
```bash
git clone -b master https://github.com/leon-ai/leon.git leon-source
```

**Copy these folders/files into `zenith/`:**

```
leon-source/skills/           → zenith/skills/
leon-source/server/           → zenith/server/
leon-source/hotword/          → zenith/hotword/
leon-source/bridges/          → zenith/bridges/
leon-source/tcp_server/       → zenith/tcp_server/
leon-source/core/             → zenith/core/
leon-source/app/              → zenith/app/          (UI base)
leon-source/bin/              → zenith/bin/
leon-source/scripts/          → zenith/scripts/
leon-source/logs/             → zenith/logs/
leon-source/package.json      → zenith/package.json  (merge, don't overwrite)
leon-source/tsconfig.json     → zenith/tsconfig.json
leon-source/.env.sample       → zenith/.env.sample   (extend with Zenith keys)
leon-source/nodemon.json      → zenith/nodemon.json
```

**What each part gives you:**

- `skills/` — the entire skill/package system. Each subfolder is a domain (calendar, checker, trend, videodownloader, etc.). Each skill has: Python logic, multilingual expressions JSON, answers JSON, config JSON, and tests. This is your plugin architecture, already built.
- `server/` — TypeScript server with NLU brain, intent routing, WebSocket events, HTTP API. The most valuable part of Leon.
- `hotword/` — standalone Node.js process that listens for a wake word offline. Plug it in and "Hey Zenith" works.
- `bridges/` — the Python bridge (`bridges/python/`) that lets the Node.js server execute Python skill scripts. **Critical** — do not skip this.
- `core/` — language configuration (`langs.json`), NLU fallback rules, core constants.
- `app/` — existing web frontend. Modest but functional. You will extend this into the Zenith HUD.

**What to IGNORE from Leon:**
- `leon-source/.github/` — CI config, not needed
- Leon's default TTS (uses `flite` — robotic)
- Leon's default STT (requires keys you don't have)
- `CHANGELOG.md`, `LICENSE.md` — replace with your own

---

### 1.2 From `SAGAR-TAMANG/friday-tony-stark-demo`

Clone it:
```bash
git clone https://github.com/SAGAR-TAMANG/friday-tony-stark-demo.git friday-source
```

**Copy these into `zenith/voice/`:**

```
friday-source/server.py           → zenith/voice/mcp_server.py
friday-source/agent_friday.py     → zenith/voice/agent.py
friday-source/friday/             → zenith/voice/friday_tools/
  friday/config.py                → zenith/voice/friday_tools/config.py
  friday/tools/web.py             → zenith/voice/friday_tools/web.py
  friday/tools/system.py          → zenith/voice/friday_tools/system.py
  friday/tools/utils.py           → zenith/voice/friday_tools/utils.py
  friday/prompts/                 → zenith/voice/friday_tools/prompts/
  friday/resources/               → zenith/voice/friday_tools/resources/
friday-source/pyproject.toml      → zenith/voice/pyproject.toml
friday-source/.env.example        → (merge into zenith/.env.sample)
```

**What each part gives you:**

- `mcp_server.py` — FastMCP server that exposes tools over SSE. This is the "backend brain" that the voice agent calls. Runs on port 8000.
- `agent.py` — LiveKit voice pipeline. STT → LLM (Gemini) → TTS → Speaker. You will modify the STT and TTS providers in this file (see Part 2).
- `friday_tools/web.py` — `search_web`, `fetch_url`, `get_world_news`, `open_world_monitor`. Keep as-is.
- `friday_tools/system.py` — `get_current_time`, `get_system_info`. Keep as-is.

**Key lines to change in `agent.py` after copying:**

```python
# CHANGE THESE at the top of agent.py:
STT_PROVIDER = "groq_whisper"    # was "sarvam"
LLM_PROVIDER = "gemini"          # keep — already correct
TTS_PROVIDER = "google_cloud"    # was "openai"
```

**What to IGNORE from Friday:**
- `uv.lock` — regenerate with your own `uv sync`
- `.python-version` — use whatever Python ≥ 3.11 you have
- The Supabase ticketing tool (optional, needs key)

---

### 1.3 From `vierisid/jarvis`

Clone it:
```bash
git clone https://github.com/vierisid/jarvis.git jarvis-source
```

**Copy these into `zenith/providers/`:**

```
jarvis-source/src/llm/provider.ts    → read carefully, port logic to Python
jarvis-source/src/llm/manager.ts     → zenith/providers/manager.py (port to Python)
jarvis-source/src/config/types.ts    → reference for zenith/config/zenith.yaml schema
jarvis-source/src/config/loader.ts   → zenith/config/loader.py (port to Python)
jarvis-source/config.example.yaml    → zenith/config/zenith.example.yaml (adapt)
jarvis-source/roles/                 → zenith/config/roles/ (keep YAML files)
```

**What each part gives you:**

- `manager.ts` → `manager.py` — multi-provider fallback logic. When Gemini fails (rate limit, error), automatically tries Groq, then OpenRouter. Port this TypeScript class to Python — it's only ~80 lines.
- `config/loader.ts` → `loader.py` — YAML config loader with deep merge and `~` path expansion. Simple to port.
- `zenith.example.yaml` — the config file schema. Adapt the provider section to Gemini/Groq/OpenRouter.
- `roles/` — YAML personality/role definitions. Keep these — they define assistant behavior.

**Python port of the critical `manager.py`** (write this file yourself, it's ~60 lines):

```python
# zenith/providers/manager.py
import google.generativeai as genai
from groq import Groq
from openai import OpenAI  # OpenRouter uses OpenAI-compatible API

class ZenithProviderManager:
    def __init__(self, config: dict):
        self.providers = self._init_providers(config)

    def _init_providers(self, config):
        providers = []
        if config.get("gemini", {}).get("api_key"):
            providers.append(GeminiProvider(config["gemini"]))
        if config.get("groq", {}).get("api_key"):
            providers.append(GroqProvider(config["groq"]))
        if config.get("openrouter", {}).get("api_key"):
            providers.append(OpenRouterProvider(config["openrouter"]))
        return providers

    async def chat(self, messages: list, tools=None) -> str:
        last_error = None
        for provider in self.providers:
            try:
                return await provider.chat(messages, tools)
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(f"All providers failed. Last error: {last_error}")
```

**What to IGNORE from Jarvis:**
- `src/llm/ollama.ts` — you said no Ollama
- `src/llm/anthropic.ts` — no Anthropic key
- `src/llm/openai.ts` — no OpenAI key
- `sidecar/desktop-bridge/` — Tauri handles this better
- All `bun`/`npm` run scripts — you're porting to Python

---

### 1.4 From `GauravSingh9356/J.A.R.V.I.S`

Clone it:
```bash
git clone https://github.com/GauravSingh9356/J.A.R.V.I.S.git gaurav-source
```

**Copy these Python files into `zenith/skills/` (they become skill actions):**

```
gaurav-source/news.py              → zenith/skills/information/news/news.py
gaurav-source/helpers.py           → split into:
                                     zenith/skills/information/wiki/wiki.py
                                     zenith/skills/information/weather/weather.py
                                     zenith/skills/information/dictionary/dictionary.py
gaurav-source/youtube.py           → zenith/skills/entertainment/youtube/youtube.py
gaurav-source/youtube_downloader.py → zenith/skills/entertainment/youtube/downloader.py
gaurav-source/diction.py           → zenith/skills/information/dictionary/diction.py
gaurav-source/amazon.py            → zenith/skills/shopping/amazon/amazon.py (optional)
gaurav-source/OCR.py               → zenith/skills/productivity/ocr/ocr.py
gaurav-source/Face-Recognition/    → zenith/skills/security/face_auth/ (future scope)
```

**What each part gives you:**

- `news.py` — NewsAPI integration. Fetches headlines. Works as-is after wrapping in Leon skill format.
- `helpers.py` — Wikipedia search, weather (OpenWeatherMap), geolocation, jokes. Split by domain.
- `youtube.py` — Opens YouTube with search query. One function, 5 lines. Easy to wrap.
- `youtube_downloader.py` — Downloads YouTube videos. Wrap in Leon skill.
- `diction.py` — Dictionary with spell-checking via `difflib`. Clever implementation.
- `OCR.py` — Tesseract OCR. Reads text from images. Genuine capability.
- `Face-Recognition/` — OpenCV face detection. Mark as future scope, copy but don't wire up yet.

**What to IGNORE from GauravSingh:**
- `jarvis.py` — the monolithic main loop with `while True` / `if "jarvis" in query`. This is the old way. Do NOT copy this.
- `PyAudio-0.2.11-cp38-cp38-win_amd64.whl` — Windows binary, useless
- `data.json`, `data.txt` — flat data files, replace with SQLite via Leon's TinyDB pattern
- `requirements.txt` — dependencies pulled into individual skill `config.json` instead
- `ImgContor.jpg`, `canny.jpg`, `jarvis.jpg`, `jarvis1.jpg` — test images

---

## PART 2 — STEP-BY-STEP BUILD INSTRUCTIONS

### Phase 1: Leon Foundation (Days 1–3)

**Goal**: Get a working personal assistant running locally.

**Step 1.1 — Prerequisites**
```bash
# Install Node.js >= 22
node --version  # must be >= 22.13.1

# Install npm >= 10
npm --version

# Install Python >= 3.11
python3 --version

# Install uv (Python package manager for voice components)
pip install uv

# Install Leon CLI
npm install --global @leon-ai/cli
```

**Step 1.2 — Create Leon (your Zenith base)**
```bash
# Create Zenith from Leon's stable master
leon create birth

# This creates a ~/leon directory. You'll rename/move it:
mv ~/leon ~/zenith
cd ~/zenith

# Verify setup
leon check

# Start Leon
leon start
# Open http://localhost:1337 — you have a working assistant
```

**Step 1.3 — Rename & rebrand**

In `zenith/package.json`, change:
```json
{
  "name": "zenith",
  "description": "Zenith — Your open-source personal AI assistant"
}
```

In `zenith/core/langs.json`, add your fallback words for "Zenith" alongside "Leon":
```json
"hotword": "zenith"
```

In `zenith/app/src/` find Leon branding and replace "Leon" with "Zenith" in display text. Don't rename variables — only user-facing strings.

**Step 1.4 — Create the Zenith GitHub repo**

```bash
cd ~/zenith
git init
git remote add origin https://github.com/YOUR_USERNAME/zenith.git
git add .
git commit -m "feat: zenith foundation from leon master"
git push -u origin main
```

---

### Phase 2: Voice Pipeline Upgrade (Week 1–2)

**Goal**: Replace Leon's default STT/TTS with Friday's modern LiveKit pipeline.

**Step 2.1 — Set up the voice directory**
```bash
mkdir -p ~/zenith/voice
cd ~/zenith/voice

# Copy Friday source files (you cloned friday-source earlier)
cp ../friday-source/server.py ./mcp_server.py
cp ../friday-source/agent_friday.py ./agent.py
cp -r ../friday-source/friday/ ./friday_tools/
cp ../friday-source/pyproject.toml ./pyproject.toml

# Install voice dependencies
uv sync
```

**Step 2.2 — Replace Sarvam STT with Groq Whisper**

Open `~/zenith/voice/agent.py`. Find the STT section and replace:

```python
# REMOVE this (Sarvam):
# from livekit.plugins import sarvam
# stt = sarvam.STT(...)

# ADD this (Groq Whisper):
import httpx
from livekit.agents.stt import STT, SpeechEvent, SpeechEventType

class GroqWhisperSTT(STT):
    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo"):
        super().__init__()
        self.api_key = api_key
        self.model = model

    async def recognize(self, audio_data: bytes) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("audio.wav", audio_data, "audio/wav")},
                data={"model": self.model}
            )
            return response.json()["text"]
```

At the top of `agent.py`, change the provider constants:
```python
STT_PROVIDER = "groq_whisper"   # changed from "sarvam"
LLM_PROVIDER = "gemini"         # unchanged
TTS_PROVIDER = "google_cloud"   # changed from "openai"
```

**Step 2.3 — Replace OpenAI TTS with Google Cloud TTS**

```python
# REMOVE this (OpenAI TTS):
# from livekit.plugins import openai as openai_tts

# ADD this (Google Cloud TTS):
from google.cloud import texttospeech

class GoogleCloudTTS:
    def __init__(self):
        self.client = texttospeech.TextToSpeechAsyncClient()

    async def synthesize(self, text: str) -> bytes:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Neural2-D",  # deep male voice, closest to JARVIS
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        response = await self.client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content
```

**Alternative TTS (fully offline, no key needed):**
```bash
pip install kokoro-onnx --break-system-packages
```
```python
# Local TTS with Kokoro (no API key required)
from kokoro_onnx import Kokoro

class KokoroTTS:
    def __init__(self):
        self.kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")

    async def synthesize(self, text: str, voice: str = "af") -> bytes:
        samples, sample_rate = self.kokoro.create(text, voice=voice, speed=1.0)
        return samples
```

**Step 2.4 — Update `.env` with new keys**
```bash
# Add to zenith/.env:
GOOGLE_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_key
LIVEKIT_API_SECRET=your_livekit_secret
# Google Cloud TTS (if using):
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-service-account.json
# OpenRouter (fallback, optional):
OPENROUTER_API_KEY=your_openrouter_key
```

**Step 2.5 — Test voice pipeline**
```bash
# Terminal 1: MCP server
cd ~/zenith/voice
uv run python mcp_server.py

# Terminal 2: Voice agent
uv run python agent.py

# Open LiveKit Playground: https://agents-playground.livekit.io
# Connect to your room. Say "Hey Zenith" — you should get a response.
```

---

### Phase 3: Tool Migration (Week 3–4)

**Goal**: Convert GauravSingh scripts into Leon skill packages.

**Step 3.1 — Understand Leon's skill structure**

Every skill follows this pattern:
```
zenith/skills/{domain}/{skill_name}/
├── data/
│   ├── answers/
│   │   └── en.json       ← what Zenith says back
│   └── expressions/
│       └── en.json       ← what you can say to trigger it
├── config/
│   ├── config.json       ← API keys, options
│   └── config.sample.json
├── test/
│   └── {skill}.spec.js
├── __init__.py
└── {skill}.py            ← the actual logic
```

**Step 3.2 — Create the Reminders skill** (your #1 requirement from the whiteboard)

```bash
mkdir -p ~/zenith/skills/productivity/reminders/data/answers
mkdir -p ~/zenith/skills/productivity/reminders/data/expressions
mkdir -p ~/zenith/skills/productivity/reminders/config
touch ~/zenith/skills/productivity/reminders/__init__.py
```

`data/expressions/en.json`:
```json
{
  "create_reminder": {
    "expressions": [
      "Remind me to %reminder_text% at %time%",
      "Set a reminder for %reminder_text%",
      "Add a reminder: %reminder_text%",
      "Don't let me forget to %reminder_text%",
      "Remind me about %reminder_text% tomorrow"
    ],
    "entities": [
      {
        "type": "trim",
        "name": "reminder_text",
        "conditions": [{ "type": "after", "from": ["to", "about", "for", "forget to"] }]
      }
    ]
  },
  "list_reminders": {
    "expressions": [
      "What are my reminders",
      "Show my reminders",
      "List all reminders",
      "What do I have to do"
    ]
  },
  "delete_reminder": {
    "expressions": [
      "Delete reminder %id%",
      "Remove reminder %id%",
      "Cancel reminder %id%"
    ]
  }
}
```

`data/answers/en.json`:
```json
{
  "reminder_created": [
    "Reminder set: %text%. I'll notify you at the right time, sir.",
    "Done. I've scheduled a reminder for %text%."
  ],
  "reminders_list": [
    "Here are your active reminders: %list%",
    "You have %count% reminder(s): %list%"
  ],
  "no_reminders": [
    "You have no active reminders, sir.",
    "Your schedule is clear."
  ],
  "reminder_deleted": [
    "Reminder deleted.",
    "Consider it gone."
  ]
}
```

`reminders.py`:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import utils
from datetime import datetime

def create_reminder(string, entities):
    """Create a new reminder"""
    db_result = utils.db()
    db = db_result['db']
    Query = db_result['query']

    reminder_text = string
    for entity in entities:
        if entity.get('entity') == 'reminder_text':
            reminder_text = entity.get('sourceText', string)
            break

    reminder = {
        'text': reminder_text,
        'created_at': datetime.now().isoformat(),
        'done': False
    }
    db.insert(reminder)

    return utils.output('end', 'reminder_created',
        utils.translate('reminder_created', {'text': reminder_text}))


def list_reminders(string, entities):
    """List all active reminders"""
    db_result = utils.db()
    db = db_result['db']
    Query = db_result['query']

    reminders = db.search(Query.done == False)

    if not reminders:
        return utils.output('end', 'no_reminders', utils.translate('no_reminders'))

    items = [f"{i+1}. {r['text']}" for i, r in enumerate(reminders)]
    reminder_list = ', '.join(items)

    return utils.output('end', 'reminders_list',
        utils.translate('reminders_list', {
            'count': len(reminders),
            'list': reminder_list
        }))


def delete_reminder(string, entities):
    """Delete a reminder"""
    db_result = utils.db()
    db = db_result['db']

    # Simple: delete all done reminders or by index
    db.update({'done': True})
    return utils.output('end', 'reminder_deleted', utils.translate('reminder_deleted'))
```

**Step 3.3 — Create the News skill** (from GauravSingh `news.py`)

```bash
mkdir -p ~/zenith/skills/information/news/data/answers
mkdir -p ~/zenith/skills/information/news/data/expressions
mkdir -p ~/zenith/skills/information/news/config
touch ~/zenith/skills/information/news/__init__.py
```

`config/config.sample.json`:
```json
{
  "news": {
    "newsapi_key": "",
    "max_articles": 5
  }
}
```

`news.py` — copy the logic from `gaurav-source/news.py`, then wrap it:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import utils
import requests

def get_headlines(string, entities):
    """Fetch and speak today's headlines"""
    api_key = utils.config('newsapi_key')
    max_articles = utils.config('max_articles') or 5

    url = f"https://newsapi.org/v2/top-headlines?country=in&apiKey={api_key}&pageSize={max_articles}"
    response = utils.http('GET', url)
    data = response.json()

    if data.get('status') != 'ok':
        return utils.output('end', 'error', utils.translate('fetch_error'))

    headlines = [a['title'] for a in data.get('articles', [])]
    result = '. '.join(headlines)

    return utils.output('end', 'headlines', utils.translate('headlines', {'news': result}))
```

**Step 3.4 — Create the Chrome Automation skill** (from your whiteboard requirement #2)

```bash
mkdir -p ~/zenith/skills/automation/chrome/data/answers
mkdir -p ~/zenith/skills/automation/chrome/data/expressions
touch ~/zenith/skills/automation/chrome/__init__.py
```

`chrome.py`:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import utils
import subprocess
import webbrowser

def open_website(string, entities):
    """Open a website by name"""
    websites = {
        'youtube': 'https://youtube.com',
        'github': 'https://github.com',
        'google': 'https://google.com',
        'gmail': 'https://mail.google.com',
        'maps': 'https://maps.google.com',
        'stackoverflow': 'https://stackoverflow.com',
    }

    target = string.lower()
    for name, url in websites.items():
        if name in target:
            webbrowser.open(url)
            return utils.output('end', 'opened',
                utils.translate('opened', {'site': name}))

    # Fallback: search for it
    search_url = f"https://www.google.com/search?q={string}"
    webbrowser.open(search_url)
    return utils.output('end', 'searched',
        utils.translate('searched', {'query': string}))


def search_web(string, entities):
    """Search the web"""
    query = string
    for entity in entities:
        if entity.get('entity') == 'query':
            query = entity.get('sourceText', string)
            break

    search_url = f"https://www.google.com/search?q={query}"
    webbrowser.open(search_url)
    return utils.output('end', 'searched',
        utils.translate('searched', {'query': query}))
```

**Step 3.5 — Create the Q&A skill** (your whiteboard requirement #4)

This routes complex questions to Gemini:

`qa.py`:
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import utils
import os
import google.generativeai as genai

def answer(string, entities):
    """Answer any question using Gemini"""
    api_key = os.getenv('GOOGLE_API_KEY')
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel('gemini-2.5-flash')

    prompt = f"""You are Zenith, a personal AI assistant in the style of JARVIS from Iron Man.
Answer this question concisely and helpfully (2-3 sentences max for voice output):

{string}"""

    response = model.generate_content(prompt)
    answer_text = response.text.strip()

    return utils.output('end', 'answered',
        utils.translate('answered', {'response': answer_text}))
```

**Step 3.6 — Register all new skills**

For each new skill, add an entry in `zenith/core/langs.json` under the `fallbacks` section if you need keyword-based routing alongside NLU:

```json
{
  "fallbacks": [
    { "words": ["remind", "reminder"], "package": "productivity", "module": "reminders", "action": "create_reminder" },
    { "words": ["news", "headlines"], "package": "information", "module": "news", "action": "get_headlines" },
    { "words": ["open", "website", "browse"], "package": "automation", "module": "chrome", "action": "open_website" }
  ]
}
```

---

### Phase 4: Provider Abstraction Layer (Week 5)

**Goal**: Gemini primary, Groq fallback, OpenRouter tertiary.

**Step 4.1 — Create providers directory**
```bash
mkdir -p ~/zenith/providers
touch ~/zenith/providers/__init__.py
```

**Step 4.2 — `zenith/providers/gemini.py`**
```python
import google.generativeai as genai
import os

class GeminiProvider:
    name = "gemini"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
        self.model_name = config.get("model", "gemini-2.5-flash")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    async def chat(self, messages: list, tools=None) -> str:
        # Convert messages to Gemini format
        history = []
        for msg in messages[:-1]:
            history.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [msg["content"]]
            })
        last_message = messages[-1]["content"]

        chat = self.model.start_chat(history=history)
        response = chat.send_message(last_message)
        return response.text
```

**Step 4.3 — `zenith/providers/groq_provider.py`**
```python
from groq import AsyncGroq
import os

class GroqProvider:
    name = "groq"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("GROQ_API_KEY")
        self.model = config.get("model", "llama-3.3-70b-versatile")
        self.client = AsyncGroq(api_key=self.api_key)

    async def chat(self, messages: list, tools=None) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024
        )
        return response.choices[0].message.content
```

**Step 4.4 — `zenith/providers/openrouter_provider.py`**
```python
from openai import AsyncOpenAI
import os

class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        self.model = config.get("model", "meta-llama/llama-3.3-70b-instruct")
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )

    async def chat(self, messages: list, tools=None) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content
```

**Step 4.5 — `zenith/providers/manager.py`** (ported from Jarvis `manager.ts`)
```python
import asyncio
from .gemini import GeminiProvider
from .groq_provider import GroqProvider
from .openrouter_provider import OpenRouterProvider


class ZenithProviderManager:
    """Multi-provider manager with automatic fallback. Ported from vierisid/jarvis."""

    def __init__(self, config: dict):
        self.providers = []
        llm_config = config.get("llm", {})

        if llm_config.get("gemini", {}).get("api_key"):
            self.providers.append(GeminiProvider(llm_config["gemini"]))

        if llm_config.get("groq", {}).get("api_key"):
            self.providers.append(GroqProvider(llm_config["groq"]))

        if llm_config.get("openrouter", {}).get("api_key"):
            self.providers.append(OpenRouterProvider(llm_config["openrouter"]))

        if not self.providers:
            raise ValueError("No LLM providers configured. Add at least GOOGLE_API_KEY.")

        self.current_provider_index = 0

    async def chat(self, messages: list, tools=None) -> str:
        errors = []
        for provider in self.providers:
            try:
                result = await provider.chat(messages, tools)
                self.current_provider_index = self.providers.index(provider)
                return result
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
                continue

        raise RuntimeError(f"All providers failed:\n" + "\n".join(errors))

    @property
    def active_provider(self) -> str:
        return self.providers[self.current_provider_index].name
```

**Step 4.6 — `zenith/config/zenith.yaml`** (adapted from Jarvis `config.example.yaml`)
```yaml
# Zenith Configuration
# Copy this to zenith/config/zenith.yaml and fill in your keys

server:
  port: 1337
  data_dir: "~/.zenith"

voice:
  stt_provider: "groq_whisper"      # groq_whisper | google | deepgram
  tts_provider: "google_cloud"      # google_cloud | kokoro_local
  wake_word: "zenith"
  language: "en-US"
  livekit_url: ""                   # from env: LIVEKIT_URL

llm:
  primary: "gemini"
  fallback: ["groq", "openrouter"]

  gemini:
    api_key: ""                     # from env: GOOGLE_API_KEY
    model: "gemini-2.5-flash"

  groq:
    api_key: ""                     # from env: GROQ_API_KEY
    model: "llama-3.3-70b-versatile"

  openrouter:
    api_key: ""                     # from env: OPENROUTER_API_KEY
    model: "meta-llama/llama-3.3-70b-instruct"

personality:
  name: "Zenith"
  style: "friday"                   # tony-stark friday style
  core_traits: ["loyal", "precise", "proactive", "efficient"]
  address_user_as: "sir"

skills:
  enabled: true
  nlp_confidence_threshold: 0.6    # below this, route to LLM
  auto_learn: false                 # future scope

memory:
  db_type: "tinydb"                 # tinydb | sqlite
  db_path: "~/.zenith/zenith.db"
  chat_history_limit: 100

ui:
  theme: "stark"                    # stark | minimal | neon
  port: 1337
```

---

### Phase 5: UI Dashboard (Week 6–8)

**Goal**: Extend Leon's existing web app into a Zenith HUD.

**Step 5.1 — Install Tauri for desktop app**
```bash
cd ~/zenith

# Install Rust (Tauri requirement)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# Install Tauri CLI
npm install --save-dev @tauri-apps/cli

# Initialize Tauri around Leon's existing app
npx tauri init
# - App name: Zenith
# - Window title: Zenith
# - Web assets relative path: ../app/dist
# - Dev server URL: http://localhost:1337
```

**Step 5.2 — Add Framer Motion and animation libraries**
```bash
cd ~/zenith/app
npm install framer-motion
npm install @radix-ui/react-dialog @radix-ui/react-tooltip
```

**Step 5.3 — Create the Zenith Orb component**

Create `zenith/app/src/components/ZenithOrb/ZenithOrb.jsx`:
```jsx
import { motion, useAnimation } from 'framer-motion'
import { useEffect } from 'react'

// Pulse states: idle | listening | thinking | speaking
export default function ZenithOrb({ state = 'idle' }) {
  const controls = useAnimation()

  const stateConfig = {
    idle:      { scale: 1,    opacity: 0.6, boxShadow: '0 0 20px #00d4ff33' },
    listening: { scale: 1.15, opacity: 1,   boxShadow: '0 0 40px #00d4ff99' },
    thinking:  { scale: 1.05, opacity: 0.9, boxShadow: '0 0 30px #7b61ff66' },
    speaking:  { scale: [1, 1.1, 1], opacity: 1, boxShadow: '0 0 50px #00d4ffcc' },
  }

  useEffect(() => {
    controls.start(stateConfig[state])
  }, [state])

  return (
    <div className="orb-container">
      <motion.div
        className="orb"
        animate={controls}
        transition={{ duration: 0.4, ease: 'easeInOut',
          repeat: state === 'speaking' ? Infinity : 0 }}
      />
      <p className="orb-label">{state.toUpperCase()}</p>
    </div>
  )
}
```

**Step 5.4 — Create the HUD layout**

Create `zenith/app/src/components/HUD/HUD.jsx`:
```jsx
import ZenithOrb from '../ZenithOrb/ZenithOrb'
import ChatLog from '../ChatLog/ChatLog'
import ToolMonitor from '../ToolMonitor/ToolMonitor'
import Controls from '../Controls/Controls'

export default function HUD({ assistantState, messages, toolEvents, reminders }) {
  return (
    <div className="hud-root">
      {/* Top bar */}
      <header className="hud-header">
        <span className="hud-title">ZENITH</span>
        <span className="hud-status">ONLINE · {new Date().toLocaleTimeString()}</span>
      </header>

      {/* Main grid: orb + chat */}
      <main className="hud-main">
        <section className="hud-orb-panel">
          <ZenithOrb state={assistantState} />
          <Controls reminders={reminders} />
        </section>

        <section className="hud-chat-panel">
          <ChatLog messages={messages} />
        </section>

        <section className="hud-monitor-panel">
          <ToolMonitor events={toolEvents} />
        </section>
      </main>
    </div>
  )
}
```

**Step 5.5 — Add WebSocket connection to Zenith state**

Leon's server already emits WebSocket events. In `zenith/app/src/`, find the existing WebSocket setup and extend it:

```javascript
// In your main app component, add tool monitoring:
socket.on('zenith:tool_call', (data) => {
  setToolEvents(prev => [{
    id: Date.now(),
    tool: data.tool,
    input: data.input,
    output: data.output,
    latency: data.latency,
    timestamp: new Date()
  }, ...prev].slice(0, 50)) // keep last 50 events
})

socket.on('zenith:state_change', (data) => {
  setAssistantState(data.state) // idle | listening | thinking | speaking
})
```

**Step 5.6 — Add HUD CSS** (dark Tony Stark theme)

Create `zenith/app/src/styles/hud.css`:
```css
:root {
  --zenith-bg: #050a0f;
  --zenith-panel: #0a1520;
  --zenith-border: #00d4ff22;
  --zenith-accent: #00d4ff;
  --zenith-accent-2: #7b61ff;
  --zenith-text: #c8e8f0;
  --zenith-muted: #4a6a7a;
  --zenith-danger: #ff4455;
  --zenith-success: #00ff88;
}

body { background: var(--zenith-bg); color: var(--zenith-text); }

.hud-root {
  display: grid;
  grid-template-rows: 48px 1fr;
  height: 100vh;
  font-family: 'Rajdhani', 'Share Tech Mono', monospace;
}

.hud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid var(--zenith-border);
  background: var(--zenith-panel);
  letter-spacing: 0.2em;
}

.hud-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--zenith-accent);
  letter-spacing: 0.4em;
}

.hud-main {
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  gap: 1px;
  background: var(--zenith-border);
  overflow: hidden;
}

.hud-main > section {
  background: var(--zenith-bg);
  overflow: hidden;
}

.orb-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.orb {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 35%, #00d4ff44, #050a0f 70%);
  border: 1.5px solid var(--zenith-accent);
}
```

---

### Phase 6: Desktop App (Week 9–10)

**Step 6.1 — Build and run as desktop app**
```bash
cd ~/zenith

# Development mode (hot reload)
npx tauri dev

# Production build
npx tauri build
# Output: src-tauri/target/release/zenith (Linux/Mac)
# Output: src-tauri/target/release/zenith.exe (Windows)
```

**Step 6.2 — Configure Tauri window style**

In `zenith/src-tauri/tauri.conf.json`:
```json
{
  "tauri": {
    "windows": [
      {
        "title": "Zenith",
        "width": 1280,
        "height": 800,
        "minWidth": 1024,
        "minHeight": 600,
        "resizable": true,
        "transparent": false,
        "decorations": false,
        "alwaysOnTop": false
      }
    ]
  }
}
```

---

## PART 3 — FULL MONOREPO STRUCTURE AFTER INTEGRATION

```
zenith/
│
├── skills/                        ← FROM LEON (keep structure exactly)
│   ├── calendar/                  ← Leon built-in (to-do, reminders base)
│   ├── checker/                   ← Leon built-in (is-it-down, etc.)
│   ├── trend/                     ← Leon built-in (GitHub trending, etc.)
│   ├── videodownloader/           ← Leon built-in (YouTube download)
│   ├── productivity/              ← NEW
│   │   ├── reminders/             ← written in Phase 3
│   │   └── ocr/                   ← from GauravSingh OCR.py
│   ├── information/               ← NEW
│   │   ├── news/                  ← from GauravSingh news.py
│   │   ├── wiki/                  ← from GauravSingh helpers.py
│   │   ├── weather/               ← from GauravSingh helpers.py
│   │   └── dictionary/            ← from GauravSingh diction.py
│   ├── automation/                ← NEW
│   │   └── chrome/                ← from your whiteboard req #2
│   ├── entertainment/             ← NEW
│   │   └── youtube/               ← from GauravSingh youtube.py
│   └── knowledge/                 ← NEW
│       └── qa/                    ← Gemini Q&A (whiteboard req #4)
│
├── server/                        ← FROM LEON (TypeScript, keep as-is)
│   └── src/
│       ├── core/                  ← NLU brain, intent routing
│       ├── stt/                   ← replace Leon's STT with Groq adapter
│       └── tts/                   ← replace Leon's TTS with Google/Kokoro
│
├── hotword/                       ← FROM LEON (keep exactly)
│
├── bridges/                       ← FROM LEON (keep exactly)
│   └── python/                    ← Python bridge for skills
│
├── tcp_server/                    ← FROM LEON (keep exactly)
│
├── core/                          ← FROM LEON + extend for Zenith
│   └── langs.json                 ← add Zenith fallback words
│
├── voice/                         ← FROM FRIDAY (voice pipeline)
│   ├── mcp_server.py              ← Friday's server.py renamed
│   ├── agent.py                   ← Friday's agent_friday.py modified
│   ├── friday_tools/              ← Friday's tool modules
│   │   ├── web.py                 ← keep as-is
│   │   ├── system.py              ← keep as-is
│   │   └── utils.py               ← keep as-is
│   └── pyproject.toml
│
├── providers/                     ← FROM JARVIS (ported to Python)
│   ├── __init__.py
│   ├── gemini.py
│   ├── groq_provider.py
│   ├── openrouter_provider.py
│   └── manager.py
│
├── app/                           ← FROM LEON + extended into Zenith HUD
│   └── src/
│       ├── components/
│       │   ├── ZenithOrb/         ← NEW: voice orb animation
│       │   ├── HUD/               ← NEW: main dashboard layout
│       │   ├── ToolMonitor/       ← NEW: live tool execution log
│       │   └── [Leon components]  ← keep existing chat, log components
│       └── styles/
│           └── hud.css            ← NEW: Tony Stark dark theme
│
├── config/
│   ├── zenith.yaml                ← FROM JARVIS config pattern
│   ├── zenith.example.yaml
│   └── loader.py                  ← ported from Jarvis config loader
│
├── src-tauri/                     ← NEW: Tauri desktop wrapper
│   └── tauri.conf.json
│
├── .env                           ← all API keys
├── .env.sample                    ← merged from Leon + Friday
├── package.json                   ← from Leon (extended)
├── tsconfig.json                  ← from Leon
└── README.md                      ← write your own
```

---

## PART 4 — ENVIRONMENT VARIABLES REFERENCE

Complete `.env` file:

```bash
# ============================================
# ZENITH ENVIRONMENT CONFIGURATION
# ============================================

# ── LLM Providers ──────────────────────────
GOOGLE_API_KEY=                    # Gemini (primary) — aistudio.google.com
GROQ_API_KEY=                      # Groq (fallback) — console.groq.com
OPENROUTER_API_KEY=                # OpenRouter (tertiary, optional)

# ── Voice Pipeline ──────────────────────────
LIVEKIT_URL=                       # wss://your-project.livekit.cloud
LIVEKIT_API_KEY=                   # LiveKit Cloud dashboard
LIVEKIT_API_SECRET=                # LiveKit Cloud dashboard

# ── TTS (pick one) ──────────────────────────
GOOGLE_APPLICATION_CREDENTIALS=   # /path/to/gcp-service-account.json
# OR use Kokoro (no key needed, local only)

# ── Tool APIs ───────────────────────────────
NEWS_API_KEY=                      # newsapi.org (free tier: 100 req/day)
OPENWEATHER_API_KEY=               # openweathermap.org (free)
SERPAPI_KEY=                       # serpapi.com (optional, for Chrome skill)

# ── Leon Server ─────────────────────────────
LEON_PORT=1337
LEON_LANG=en-US

# ── Database ────────────────────────────────
ZENITH_DB_PATH=~/.zenith/zenith.db
```

---

## PART 5 — API KEYS: WHERE TO GET THEM (ALL FREE)

| Key | Where | Free tier |
|-----|-------|-----------|
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | 1M tokens/day (Gemini Flash) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | 14,400 req/day (llama + whisper) |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) | $1 free credit on signup |
| `LIVEKIT_URL/KEY/SECRET` | [cloud.livekit.io](https://cloud.livekit.io) | Free tier (3 concurrent rooms) |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org) | 100 req/day |
| `OPENWEATHER_API_KEY` | [openweathermap.org](https://openweathermap.org) | 1000 req/day |
| Google Cloud TTS | [console.cloud.google.com](https://console.cloud.google.com) | 1M chars/month free |

---

## PART 6 — RUNNING ZENITH

After full setup, you need 3 terminals (or use a process manager like `pm2`):

**Terminal 1 — Leon server (main brain)**
```bash
cd ~/zenith
leon start
# or: npm start
```

**Terminal 2 — Voice MCP server**
```bash
cd ~/zenith/voice
uv run python mcp_server.py
```

**Terminal 3 — Voice agent**
```bash
cd ~/zenith/voice
uv run python agent.py
```

**Or use pm2 to manage all processes:**
```bash
npm install -g pm2

pm2 start "leon start" --name "zenith-core"
pm2 start "uv run python voice/mcp_server.py" --name "zenith-mcp" --cwd ~/zenith
pm2 start "uv run python voice/agent.py" --name "zenith-voice" --cwd ~/zenith

pm2 save
pm2 startup  # auto-start on boot
```

**Open Zenith:**
- Web: http://localhost:1337
- Desktop: `npx tauri dev` (development) or `./target/release/zenith` (production)

---

## PART 7 — WHAT NOT TO DO (COMMON MISTAKES)

1. **Do NOT copy `jarvis.py` from GauravSingh.** The `while True` loop with `if "jarvis" in query` matching is the old way. Leon's NLU replaces it entirely.

2. **Do NOT run `leon create birth` inside an existing project folder.** The CLI creates its own directory. Move it afterward.

3. **Do NOT modify Leon's `bridges/python/` files.** They are the communication layer between Node.js and Python skills. Edit your skill files in `skills/`, not the bridge.

4. **Do NOT put API keys in skill Python files.** Use Leon's `config/config.json` per skill + `utils.config('key')` to read them.

5. **Do NOT try to run all three voice processes as a single Python file.** The MCP server and voice agent are separate processes by design. They communicate over HTTP/SSE.

6. **Do NOT use Leon's `develop` branch for your base.** It is mid-rewrite and unstable. Use `master`. Follow the `develop` branch only as a reference for future architecture patterns.

7. **Do NOT add Ollama.** You said no, and the provider fallback chain (Gemini → Groq → OpenRouter) gives you 3 free tiers before anything fails.

---

## PART 8 — MILESTONE CHECKLIST

### Phase 1 ✓
- [ ] Leon running on localhost:1337
- [ ] Can type to it and get responses
- [ ] Built-in skills work (calendar, checker, etc.)
- [ ] Renamed to Zenith in UI

### Phase 2 ✓
- [ ] Voice MCP server running
- [ ] Can speak to Zenith and hear responses
- [ ] Groq Whisper STT working
- [ ] Google Cloud TTS / Kokoro TTS working
- [ ] Gemini LLM responding

### Phase 3 ✓
- [ ] Reminders skill: create, list, delete
- [ ] News skill: reads headlines aloud
- [ ] Chrome skill: opens websites by voice
- [ ] Q&A skill: answers general questions via Gemini

### Phase 4 ✓
- [ ] `zenith/providers/manager.py` working
- [ ] Gemini fails → automatically tries Groq
- [ ] `zenith/config/zenith.yaml` loaded on startup

### Phase 5 ✓
- [ ] Zenith HUD visible at localhost:1337
- [ ] Voice orb animates on speak/listen/think
- [ ] Chat log shows conversation history
- [ ] Tool monitor shows live tool calls

### Phase 6 ✓
- [ ] Tauri builds a native desktop window
- [ ] App runs without browser
- [ ] Auto-starts on login (pm2)

### Future Scope (from whiteboard)
- [ ] Multilingual support (Leon already has the i18n system — add `hi.json` expression files)
- [ ] Face authentication (GauravSingh Face-Recognition folder)
- [ ] SerpAPI Chrome tool (deeper web browsing)
- [ ] JSON web scraping (`json — web scrapping` from whiteboard)
- [ ] Autonomous skill generation (Leon develop branch feature)

---

## PART 9 — DEPENDENCY SUMMARY

### Node.js (managed by Leon's `package.json`)
All already included when you run `leon create birth`. Key ones:
- `@nlpjs/core` — NLU engine
- `socket.io` — WebSocket
- `express` — HTTP API
- `tinydb` (via Python bridge) — persistent storage

### Python voice stack (`voice/pyproject.toml`)
```toml
[project]
name = "zenith-voice"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
  "livekit-agents>=0.8.0",
  "livekit-plugins-google",
  "fastmcp>=0.1.0",
  "google-generativeai>=0.8.0",
  "groq>=0.10.0",
  "openai>=1.0.0",       # OpenRouter uses OpenAI client
  "httpx>=0.27.0",
  "google-cloud-texttospeech>=2.16.0",
  "python-dotenv>=1.0.0",
]
```

### Python skills stack (managed by Leon's Python bridge `Pipfile`)
```
wikipedia
requests
pyttsx3           # local TTS fallback
speechrecognition
newsapi-python
pyowm             # weather
pytesseract       # OCR
opencv-python     # face recognition (future)
difflib           # built-in, no install needed
playwright        # Chrome automation
tinydb            # storage (already in Leon bridge)
```

Install skill dependencies:
```bash
cd ~/zenith/bridges/python
pipenv install wikipedia requests newsapi-python pyowm pytesseract opencv-python playwright
playwright install chromium
```

---

*End of ZENITH_INSTRUCTIONS.md*
*Version 1.0 — Built from: leon-ai/leon + friday-tony-stark-demo + vierisid/jarvis + GauravSingh9356/J.A.R.V.I.S*


## AGENT NOTES
- Source repos are pre-cloned at: ~/leon-source, ~/friday-source, ~/jarvis-source, ~/gaurav-source
- All git operations should target the `main` branch of the zenith repo
- Commit message format: `feat(phase-N): description`
- If a package install fails, try with `--break-system-packages` flag for pip
- Do not delete any files from the source repos
- After Phase 6, run `git push origin main`