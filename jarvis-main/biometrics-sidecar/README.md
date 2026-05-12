# JARVIS Biometrics Sidecar

Python microservices that extend the main Bun/TypeScript JARVIS brain with:

| Service | File | What it does |
|---|---|---|
| **Vision Auth** | `vision_service.py` | YOLOv8n person detection → LBPH face auth → Tesseract OCR |
| **MCP Server** | `mcp_server.py` | SerpAPI search, Playwright automation, Power Mode, n8n webhooks |
| **LiveKit Agent** | `livekit_agent.py` | WebRTC voice: Groq Whisper STT → Gemini LLM → Google Cloud TTS |
| **Main Sidecar** | `sidecar.py` | Face auth gate + WebSocket bridge to Bun brain + legacy TTS/mic |

---

## Step 1 — Install Dependencies

```bash
# From the jarvis-main folder:
bun run install:sidecar

# Or manually inside biometrics-sidecar/:
pip install -r requirements.txt
playwright install chromium
```

---

## Step 2 — Configure `.env`

All required keys are already saved in `biometrics-sidecar/.env`:

```
LIVEKIT_URL=wss://ai-assistant-8h7l160m.livekit.cloud
LIVEKIT_API_KEY=APIiSUz5asKdTi2
LIVEKIT_API_SECRET=jUmynesCA5I4LFBRVh5q8vWZV1IASyeYfY7yrepeaofP
SERPAPI_API_KEY=3e5a9b6212fc7350057c1b6a699868ba0f9594bf6b9f571459c3fc0df46c5c2a
GROQ_API_KEY=...
GEMINI_API_KEY=...
```

For Google Cloud TTS (in `livekit_agent.py`), you also need:
```
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\gcp-credentials.json
```
Download from GCP Console → IAM → Service Accounts → Create Key (JSON).

---

## Step 3 — Train the LBPH Face Model (one-time)

The `trainer.yml` is already included. If you need to re-train (new face):

```bash
cd biometrics-sidecar
# 1. Capture new face samples:
python "Face Recognition/Sample generator.py"
# 2. Re-train the model:
python "Face Recognition/Model Trainer.py"
```

---

## Step 4 — Run the System

### Terminal 1 — Bun Brain (TypeScript)
```bash
cd jarvis-main
bun run dev
```

### Terminal 2 — MCP Tool Server
```bash
bun run mcp
# or: cd biometrics-sidecar && python mcp_server.py
```

### Terminal 3 — LiveKit Voice Agent (WebRTC)
```bash
bun run livekit
# or: cd biometrics-sidecar && python livekit_agent.py dev
```

### Terminal 4 — Face Auth + WebSocket Sidecar (optional legacy voice)
```bash
bun run sidecar
# or: cd biometrics-sidecar && python sidecar.py
```

---

## Architecture Flow

```
[Camera] ──► vision_service.py (YOLOv8n + LBPH)
                       │ authenticated=True
                       ▼
[Microphone/WebRTC] ──► livekit_agent.py
                       │   STT: Groq Whisper
                       │   LLM: Gemini 1.5 Flash ──► mcp_server.py ──► SerpAPI
                       │                                             ──► Playwright
                       │                                             ──► Power Mode
                       │                                             ──► n8n
                       │   TTS: Google Cloud TTS
                       ▼
[Speaker output] ◄──── LiveKit WebRTC Room
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `LBPH trainer not found` | Run `"Face Recognition/Model Trainer.py"` |
| `Camera inaccessible` | Ensure no other app is using the webcam |
| `Playwright browser not found` | Run `playwright install chromium` |
| `Connection refused` on sidecar | Start `bun run dev` first |
| Google TTS 403 error | Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` |
| Groq rate limit | The free tier is generous; wait 60 seconds |
