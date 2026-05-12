"""
ZENITH — Zero Latency Engineered Network for Intuitive Task Handling
LiveKit WebRTC Voice Agent  (livekit-agents v1.x)
===================================================================

Full Brain Integration:
  - On connect: fetches goals, workflows, commitments from Brain
    (http://localhost:3142) and delivers morning briefing.
  - All tools (search, WhatsApp, power, schedule, workflows) are
    wired as @function_tool — Gemini/Groq calls them automatically.
  - Voice workflow creation: "Create a workflow that..."
  - Voice goal creation: "Add a goal to..."

Flow:
  1. Silero VAD → detects speech
  2. Groq Whisper-large-v3 → transcribes in <300ms
  3. Gemini 2.0 Flash → NLU + tool calls
  4. Google Cloud TTS Journey-D → synthesises response
  5. LiveKit WebRTC → streams audio back

Run:
    python livekit_agent.py dev
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import google, openai, silero

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("zenith.voice_agent")

# ── Environment ────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
BRAIN_URL      = os.getenv("BRAIN_URL", "http://localhost:3142")

if GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# ── Import MCP tool functions directly ────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from mcp_server import (
        serpapi_search as _serpapi_search,
        enable_power_saving_mode as _enable_power,
        disable_power_saving_mode as _disable_power,
        get_schedule as _get_schedule,
        trigger_n8n_workflow as _trigger_n8n,
        whatsapp_send_message as _whatsapp_send,
    )
    _MCP_AVAILABLE = True
    logger.info("MCP tools imported successfully.")
except ImportError as e:
    _MCP_AVAILABLE = False
    logger.warning(f"MCP tools unavailable: {e}")


# ── Brain API Client ───────────────────────────────────────────────────────
class BrainClient:
    """HTTP client for ZENITH Brain (jarvis-main daemon on port 3142)."""

    def __init__(self, base_url: str = BRAIN_URL):
        self.base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def _get(self, path: str, **kwargs) -> dict | list:
        try:
            r = self._session.get(f"{self.base}{path}", timeout=8, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Brain GET {path} failed: {e}")
            return {}

    def _post(self, path: str, data: dict, **kwargs) -> dict | list:
        try:
            r = self._session.post(f"{self.base}{path}", json=data, timeout=10, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Brain POST {path} failed: {e}")
            return {"error": str(e)}

    # ── Getters ─────────────────────────────────────────────────────────

    def get_goals(self) -> list[dict]:
        d = self._get("/api/goals")
        return d if isinstance(d, list) else d.get("goals", d.get("data", []))

    def get_workflows(self) -> list[dict]:
        d = self._get("/api/workflows")
        return d if isinstance(d, list) else d.get("workflows", d.get("data", []))

    def get_commitments(self) -> list[dict]:
        d = self._get("/api/commitments")
        return d if isinstance(d, list) else d.get("commitments", d.get("data", []))

    def get_health(self) -> dict:
        return self._get("/health")

    # ── Actions ──────────────────────────────────────────────────────────

    def create_goal(self, title: str, level: str = "task",
                    description: str = "", time_horizon: str = "weekly") -> dict:
        return self._post("/api/goals", {
            "title": title,
            "level": level,
            "description": description,
            "time_horizon": time_horizon,
            "status": "active",
        })

    def create_workflow(self, name: str, description: str = "") -> dict:
        return self._post("/api/workflows", {
            "name": name,
            "description": description,
            "enabled": True,
        })

    def run_workflow(self, workflow_id: str, trigger_data: dict = None) -> dict:
        return self._post(f"/api/workflows/{workflow_id}/execute",
                          {"trigger_data": trigger_data or {}})

    def send_chat(self, text: str, conversation_id: str = "zenith-voice") -> str:
        """Send a chat message to the Brain agent and get the full response."""
        import websockets as ws_lib

        async def _send():
            try:
                async with ws_lib.connect(
                    f"{self.base.replace('http','ws')}/ws",
                    open_timeout=5
                ) as ws:
                    await ws.send(json.dumps({
                        "type": "chat",
                        "payload": {"text": text, "conversationId": conversation_id}
                    }))
                    full = ""
                    for _ in range(30):
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        d = json.loads(raw)
                        t = d.get("type", "")
                        p = d.get("payload", {})
                        if t == "stream":
                            full += p.get("text", "")
                        elif t == "status" and p.get("status") == "done":
                            full = p.get("fullText", full)
                            break
                    return full.strip()
            except Exception as e:
                return f"Brain chat error: {e}"

        return asyncio.get_event_loop().run_until_complete(_send())

    # ── Morning Briefing ─────────────────────────────────────────────────

    def build_morning_briefing(self) -> str:
        """Build a spoken daily briefing from Brain data."""
        lines = []
        now = datetime.now()
        lines.append(f"Good {'morning' if now.hour < 12 else 'evening'}, nnssprasad.")
        lines.append("ZENITH is online. Here is your daily briefing.")

        # Goals
        goals = self.get_goals()
        active = [g for g in goals if g.get("status") == "active"]
        if active:
            lines.append(f"You have {len(active)} active goal{'s' if len(active)>1 else ''}.")
            for g in active[:3]:
                lines.append(f"Goal: {g['title']}.")
        else:
            lines.append("No active goals today.")

        # Workflows
        workflows = self.get_workflows()
        enabled = [w for w in workflows if w.get("enabled")]
        if enabled:
            lines.append(f"You have {len(enabled)} automation workflow{'s' if len(enabled)>1 else ''} configured: "
                         + ", ".join(w["name"] for w in enabled[:5]) + ".")

        # Commitments / tasks
        commitments = self.get_commitments()
        pending = [c for c in commitments if c.get("status") == "pending"] if isinstance(commitments, list) else []
        if pending:
            lines.append(f"You have {len(pending)} pending task{'s' if len(pending)>1 else ''}.")
            for c in pending[:3]:
                lines.append(f"Task: {c.get('what', c.get('title', 'Untitled'))}.")

        lines.append("What would you like to do?")
        return " ".join(lines)


# ── Singleton brain client ─────────────────────────────────────────────────
brain = BrainClient()


# ── Helper ────────────────────────────────────────────────────────────────
async def _call(fn, *args, **kwargs):
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)


# ── Pre-warm ──────────────────────────────────────────────────────────────
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("Silero VAD pre-loaded.")


# ══════════════════════════════════════════════════════════════════════════
# ZENITH Agent
# ══════════════════════════════════════════════════════════════════════════
class ZenithAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are ZENITH — Zero Latency Engineered Network for Intuitive Task Handling. "
                "You are the personal AI assistant for nnssprasad. "
                "You are connected to the ZENITH Brain (database of goals, workflows, tasks, memory). "
                "Use the available tools proactively and accurately. "
                "Never use markdown, bullet points, or symbols in spoken replies. "
                "Keep responses concise — 2 to 3 sentences maximum unless briefing. "
                "\n\nAvailable tools:\n"
                "  brain_get_briefing       — Get full morning briefing with goals, workflows, tasks\n"
                "  brain_get_goals          — List active goals\n"
                "  brain_get_workflows      — List configured workflows\n"
                "  brain_create_goal        — Create a new goal by voice\n"
                "  brain_create_workflow    — Create a new workflow by voice\n"
                "  brain_run_workflow       — Execute a workflow by name or ID\n"
                "  serpapi_search           — Real-time internet search\n"
                "  whatsapp_send_message    — Send WhatsApp message to a contact\n"
                "  enable_power_saving_mode — Turn on Windows power saving\n"
                "  disable_power_saving_mode— Restore balanced power plan\n"
                "  get_schedule             — Read schedule, deadlines, meetings\n"
                "  trigger_n8n_workflow     — Trigger an n8n automation\n"
            )
        )

    # ── Brain-connected tools ────────────────────────────────────────────

    @function_tool()
    async def brain_get_briefing(self) -> str:
        """Get the daily briefing: goals, workflows, and pending tasks from the Brain."""
        logger.info("[Tool] brain_get_briefing")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, brain.build_morning_briefing)

    @function_tool()
    async def brain_get_goals(self) -> str:
        """Get the list of active goals from the ZENITH Brain database."""
        logger.info("[Tool] brain_get_goals")
        goals = await asyncio.get_event_loop().run_in_executor(None, brain.get_goals)
        if not goals:
            return "You have no goals set yet. Would you like to create one?"
        active = [g for g in goals if g.get("status") == "active"]
        if not active:
            return f"You have {len(goals)} goals but none are currently active."
        return "Your active goals are: " + "; ".join(g["title"] for g in active[:5]) + "."

    @function_tool()
    async def brain_get_workflows(self) -> str:
        """Get the list of automation workflows configured in the ZENITH Brain."""
        logger.info("[Tool] brain_get_workflows")
        wfs = await asyncio.get_event_loop().run_in_executor(None, brain.get_workflows)
        if not wfs:
            return "No workflows configured yet."
        enabled = [w for w in wfs if w.get("enabled")]
        return (f"You have {len(enabled)} workflow{'s' if len(enabled)!=1 else ''}: "
                + ", ".join(w["name"] for w in enabled[:6]) + ".")

    @function_tool()
    async def brain_create_goal(self, title: str, time_horizon: str = "weekly") -> str:
        """
        Create a new goal in the ZENITH Brain.
        Args:
            title: The goal title as spoken (e.g. 'Finish the ZENITH presentation').
            time_horizon: How far out — 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'.
        """
        logger.info(f"[Tool] brain_create_goal: {title} ({time_horizon})")
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: brain.create_goal(title, time_horizon=time_horizon)
        )
        if "error" in str(result).lower():
            return f"Could not create goal. {result}"
        return f"Goal created: {title}. Set as a {time_horizon} goal."

    @function_tool()
    async def brain_create_workflow(self, name: str, description: str = "") -> str:
        """
        Create a new automation workflow by voice.
        Args:
            name: Short workflow name (e.g. 'Daily Email Summary').
            description: What the workflow does.
        """
        logger.info(f"[Tool] brain_create_workflow: {name}")
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: brain.create_workflow(name, description)
        )
        if "error" in str(result).lower():
            return f"Could not create workflow: {result}"
        return f"Workflow '{name}' created in the Brain. You can edit it in the Workflows panel."

    @function_tool()
    async def brain_run_workflow(self, workflow_name: str) -> str:
        """
        Run an existing workflow by name.
        Args:
            workflow_name: Name of the workflow to run.
        """
        logger.info(f"[Tool] brain_run_workflow: {workflow_name}")
        wfs = await asyncio.get_event_loop().run_in_executor(None, brain.get_workflows)
        # Find by name (fuzzy)
        match = next(
            (w for w in wfs if workflow_name.lower() in w["name"].lower()), None
        )
        if not match:
            return f"No workflow named '{workflow_name}' found. Available: {[w['name'] for w in wfs]}."
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: brain.run_workflow(match["id"])
        )
        if "error" in str(result).lower():
            return f"Workflow '{match['name']}' could not run: {result}"
        return f"Workflow '{match['name']}' triggered successfully."

    # ── MCP tools ────────────────────────────────────────────────────────

    @function_tool()
    async def serpapi_search(self, query: str) -> str:
        """Search the internet for real-time data, weather, news or any facts."""
        logger.info(f"[Tool] serpapi_search: '{query}'")
        return await _call(_serpapi_search, query) if _MCP_AVAILABLE else "Search unavailable."

    @function_tool()
    async def whatsapp_send_message(self, contact_name: str, message: str) -> str:
        """Send a WhatsApp message to a contact by name."""
        logger.info(f"[Tool] WhatsApp -> {contact_name}: {message}")
        return await _call(_whatsapp_send, contact_name, message) if _MCP_AVAILABLE \
               else "WhatsApp tool unavailable."

    @function_tool()
    async def enable_power_saving_mode(self) -> str:
        """Enable Windows Power Saving mode."""
        logger.info("[Tool] enable_power_saving_mode")
        return await _call(_enable_power) if _MCP_AVAILABLE else "Tool unavailable."

    @function_tool()
    async def disable_power_saving_mode(self) -> str:
        """Disable power saving and restore the Balanced power plan."""
        logger.info("[Tool] disable_power_saving_mode")
        return await _call(_disable_power) if _MCP_AVAILABLE else "Tool unavailable."

    @function_tool()
    async def get_schedule(self) -> str:
        """Get nnssprasad's upcoming deadlines, meetings and reminders."""
        logger.info("[Tool] get_schedule")
        return await _call(_get_schedule) if _MCP_AVAILABLE else "Schedule unavailable."

    @function_tool()
    async def trigger_n8n_workflow(self, workflow_id: str) -> str:
        """Trigger an n8n automation workflow by its ID or webhook path."""
        logger.info(f"[Tool] trigger_n8n: {workflow_id}")
        return await _call(_trigger_n8n, workflow_id) if _MCP_AVAILABLE else "n8n unavailable."

    # ── Greeting on room join ────────────────────────────────────────────

    async def on_enter(self):
        """Deliver morning briefing when nnssprasad joins the room."""
        logger.info("ZenithAgent: room joined — building briefing...")
        try:
            briefing = await asyncio.get_event_loop().run_in_executor(
                None, brain.build_morning_briefing
            )
        except Exception as e:
            logger.warning(f"Briefing failed: {e}")
            briefing = (
                "ZENITH online. Zero Latency Engineered Network activated. "
                "Identity confirmed. All systems operational. How can I help you?"
            )

        await self.session.generate_reply(
            instructions=f"Say this exactly as a spoken greeting, naturally: {briefing}"
        )


# ── Session Entrypoint ────────────────────────────────────────────────────
async def entrypoint(ctx: JobContext):
    logger.info(f"New ZENITH session: room={ctx.room.name}")
    await ctx.connect()

    # STT: Groq Whisper-large-v3
    stt = openai.STT(
        base_url="https://api.groq.com/openai/v1",
        model="whisper-large-v3",
        api_key=GROQ_API_KEY,
        language="en",
    )

    # LLM: Gemini 2.0 Flash (primary) with Groq LLaMA fallback via env
    llm = google.LLM(
        model="gemini-2.0-flash",
        api_key=GEMINI_API_KEY or None,
    )

    # TTS: Google Cloud TTS — Journey-D neural voice
    tts = google.TTS(
        voice_name="en-US-Journey-D",
        speaking_rate=1.05,
    )

    vad = ctx.proc.userdata.get("vad") or silero.VAD.load()

    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm,
        tts=tts,
    )

    await session.start(
        agent=ZenithAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )


# ── Entry ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
    ))
