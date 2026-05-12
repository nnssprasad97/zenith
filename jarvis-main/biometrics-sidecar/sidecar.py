"""
JARVIS — Main Orchestration Sidecar
=====================================
This is the primary Python entry point that ties all microservices together.

Startup sequence:
  1. Run vision_service.authenticate_user()  (YOLOv8 + LBPH face auth)
  2. Connect to the Bun WebSocket Brain at ws://localhost:3142/ws
  3. Send auth event so the dashboard registers the authenticated user
  4. Start two concurrent async loops:
       • listen_to_ws()  — receives agent replies from Brain and speaks them
       • mic_loop()      — captures voice, strips wake word, sends to Brain
  5. Auto-reconnect if the WebSocket drops

Note: Voice agent (LiveKit) runs separately via livekit_agent.py
      MCP server runs separately via mcp_server.py
      This sidecar handles Face Auth + legacy WebSocket fallback voice.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

import websockets
from dotenv import load_dotenv

load_dotenv()

# ── Add sidecar dir to path so local imports work ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from core.speech import speak, listen

# Use new vision_service for authentication
try:
    from vision_service import authenticate_user
    _VISION_SERVICE = True
except ImportError:
    # Fallback to legacy module if vision_service deps not installed
    import face_recognition_module as _fr
    authenticate_user = _fr.authenticate
    _VISION_SERVICE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("zenith.sidecar")

# ── Config ────────────────────────────────────────────────────────────────
BRAIN_WS_URL = os.getenv("BRAIN_WS_URL", "ws://localhost:3142/ws")
DAEMON_TOKEN = os.getenv("DAEMON_TOKEN", "")
if DAEMON_TOKEN:
    BRAIN_WS_URL += f"?token={DAEMON_TOKEN}"

try:
    from config import WAKE_WORD
except ImportError:
    WAKE_WORD = os.getenv("WAKE_WORD", "zenith")

RECONNECT_DELAY_SECS = 5
MAX_RECONNECT_ATTEMPTS = 0   # 0 = infinite

# ── Markdown cleaner for TTS ──────────────────────────────────────────────

def _clean_for_speech(text: str) -> str:
    """Strip markdown formatting before passing text to TTS."""
    text = re.sub(r"#{1,6}\s*", "", text)                       # headings
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)       # bold / italic
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)         # code
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)       # links
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)            # images
    text = re.sub(r"-{3,}", "", text)                           # hr
    text = re.sub(r"\n{3,}", "\n\n", text)                      # excess newlines
    return text.strip()


# ── WebSocket Listeners ───────────────────────────────────────────────────

async def listen_to_ws(websocket) -> None:
    """
    Read messages from the Bun Brain and speak assistant replies aloud.
    Handles:
      • type='notification', source='assistant_message'  → speak reply
      • type='notification', source='proactive'          → speak heartbeat
      • type='stream', accumulated field                 → ignore (dashboard only)
    """
    async for raw in websocket:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type")
        payload  = msg.get("payload", {})

        if msg_type == "notification":
            source = payload.get("source", "")
            text   = payload.get("text", "")
            if text and source in ("assistant_message", "proactive", "heartbeat"):
                clean = _clean_for_speech(text)
                if clean:
                    logger.info(f"[TTS] Speaking: {clean[:80]}…")
                    # Run blocking TTS in thread pool so we don't block WS loop
                    threading.Thread(target=speak, args=(clean,), daemon=True).start()

        elif msg_type == "status" and payload.get("status") == "done":
            # Full response text available — use it for TTS if stream not already spoken
            full_text = payload.get("fullText", "")
            if full_text:
                clean = _clean_for_speech(full_text)
                if clean:
                    threading.Thread(target=speak, args=(clean,), daemon=True).start()


async def mic_loop(websocket) -> None:
    """
    Continuously record microphone input, detect wake word, and forward
    the command to the Bun Brain over WebSocket as a 'chat' message.
    """
    loop = asyncio.get_running_loop()
    logger.info(f"[Mic] Listening for wake word: '{WAKE_WORD}'")

    while True:
        try:
            # listen() is blocking — run in thread pool
            raw_command: str = await loop.run_in_executor(None, listen)

            if not raw_command:
                continue

            cmd_lower = raw_command.lower().strip()

            # Only process if wake word is spoken (or if no wake word configured)
            if WAKE_WORD and WAKE_WORD not in cmd_lower:
                continue

            # Strip wake word from command
            command = cmd_lower.replace(WAKE_WORD, "").strip()
            if not command:
                speak("Yes?")
                continue

            logger.info(f"[Mic] Command: '{command}'")
            msg = {
                "type": "chat",
                "payload": {
                    "text": command,
                    "source": "voice",
                },
            }
            await websocket.send(json.dumps(msg))

        except websockets.exceptions.ConnectionClosed:
            logger.warning("[Mic] WebSocket closed — exiting mic loop")
            break
        except Exception as e:
            logger.error(f"[Mic] Error: {e}")
            await asyncio.sleep(1)


# ── Face Authentication ───────────────────────────────────────────────────

def _run_face_auth() -> str | None:
    """
    Runs face authentication synchronously.
    Returns the authenticated username, or None on failure.
    """
    logger.info(f"[Auth] Using {'VisionService (YOLOv8+LBPH)' if _VISION_SERVICE else 'Legacy LBPH'}")
    speak("Initiating face authentication. Please look at the camera.")

    try:
        result = authenticate_user()
    except Exception as e:
        logger.error(f"[Auth] Exception: {e}")
        speak("Authentication error. Starting in limited mode.")
        return None

    if result.get("authenticated"):
        user = result["user"]
        conf = result.get("confidence", "N/A")
        logger.info(f"[Auth] Authenticated: {user} (confidence={conf})")
        speak(f"Welcome, {user}. Authentication successful.")
        return user
    else:
        reason = result.get("reason", "Unknown reason")
        logger.warning(f"[Auth] Failed: {reason}")
        speak("Authentication failed. Running in limited mode.")
        return None


# ── Main Orchestration Loop ───────────────────────────────────────────────

async def main() -> None:
    # Step 1: Face authentication
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(None, _run_face_auth)

    logger.info(f"[Main] Connecting to Brain at {BRAIN_WS_URL}…")
    attempts = 0

    while MAX_RECONNECT_ATTEMPTS == 0 or attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            async with websockets.connect(
                BRAIN_WS_URL,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                attempts = 0  # Reset on successful connection
                logger.info("[Main] Connected to Bun Brain.")
                speak("Connected to JARVIS central brain. Ready for commands.")

                # Send auth/status event to brain
                await ws.send(json.dumps({
                    "type": "chat",
                    "payload": {
                        "text": (
                            f"SYSTEM: ZENITH Biometric sidecar online. "
                            f"User '{user or 'Unknown'}' authenticated via "
                            f"{'YOLOv8 + LBPH' if _VISION_SERVICE else 'LBPH'}."
                        ),
                        "source": "sidecar_init",
                    },
                }))

                # Run concurrent WS listener and mic loop
                ws_task  = asyncio.create_task(listen_to_ws(ws))
                mic_task = asyncio.create_task(mic_loop(ws))

                done, pending = await asyncio.wait(
                    [ws_task, mic_task],
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        except (websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosedOK,
                ConnectionRefusedError,
                OSError) as e:
            attempts += 1
            logger.error(f"[Main] Connection error ({type(e).__name__}): {e}. Retry {attempts} in {RECONNECT_DELAY_SECS}s…")
            await asyncio.sleep(RECONNECT_DELAY_SECS)
        except Exception as e:
            logger.error(f"[Main] Unexpected error: {e}")
            await asyncio.sleep(RECONNECT_DELAY_SECS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[Main] Sidecar shut down by user.")
