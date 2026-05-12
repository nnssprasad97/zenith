"""
JARVIS — Local Automation MCP Server
Runs as an HTTP/SSE server on port 3143 via uvicorn.
The LiveKit agent imports tool functions directly from this module.

Tools:
  • enable_power_saving_mode   — Windows powercfg Power Saver scheme
  • disable_power_saving_mode  — Restore Balanced plan
  • serpapi_search             — Real-time internet search
  • playwright_automation      — Headless Chromium automation
  • whatsapp_send_message      — Send WhatsApp message via WhatsApp Web (Playwright)
  • get_schedule               — Read deadlines/meetings from schedule.json
  • trigger_n8n_workflow       — POST to local n8n webhook

Run as server:
    python mcp_server.py
Import directly:
    from mcp_server import serpapi_search, enable_power_saving_mode, ...
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import asyncio
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("zenith.mcp")

SERPAPI_KEY  = os.getenv("SERPAPI_API_KEY", "")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
SCHEDULE_FILE = Path(__file__).parent / "data" / "schedule.json"

mcp = FastMCP("zenith-local-mcp")


# ── TOOL: Power Saving Mode ────────────────────────────────────────────────

@mcp.tool()
def enable_power_saving_mode() -> str:
    """Enables the Windows Power Saver power plan via powercfg."""
    try:
        result = subprocess.run(
            ["powercfg", "/setactive", "a1841308-3541-4fab-bc81-f71556f20b4a"],
            capture_output=True, text=True, timeout=10
        )
        return "Power saving mode enabled." if result.returncode == 0 \
               else f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Failed: {e}"


@mcp.tool()
def disable_power_saving_mode() -> str:
    """Restores the Balanced power plan."""
    try:
        result = subprocess.run(
            ["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"],
            capture_output=True, text=True, timeout=10
        )
        return "Balanced power plan restored." if result.returncode == 0 \
               else f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Failed: {e}"


# ── TOOL: SerpAPI Search ───────────────────────────────────────────────────

@mcp.tool()
def serpapi_search(query: str) -> str:
    """
    Search the internet for real-time data.
    Args:
        query: Search query string.
    """
    if not SERPAPI_KEY:
        return "SERPAPI_API_KEY not configured."
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERPAPI_KEY, "num": 3},
            timeout=12
        )
        resp.raise_for_status()
        data = resp.json()
        ab = data.get("answer_box", {})
        if ab.get("answer"):
            return f"Answer: {ab['answer']}"
        if ab.get("snippet"):
            return f"Answer: {ab['snippet']}"
        organic = data.get("organic_results", [])
        if organic:
            top = organic[0]
            return f"{top.get('title', '')}: {top.get('snippet', 'No result.')}"
        return "No results found."
    except Exception as e:
        return f"Search failed: {e}"


# ── TOOL: WhatsApp Message ─────────────────────────────────────────────────

@mcp.tool()
async def whatsapp_send_message(contact_name: str, message: str) -> str:
    """
    Send a WhatsApp message to a contact by searching their name on WhatsApp Web.
    Requires WhatsApp Web to be logged in (first run opens browser for QR scan).
    Args:
        contact_name: Name of the contact as saved in WhatsApp (e.g. 'Karthik').
        message: Message text to send.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            # Use persistent context to keep WhatsApp Web session alive
            user_data_dir = str(Path(__file__).parent / "data" / "whatsapp_session")
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)

            browser = await pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,   # Must be visible for WhatsApp Web
                args=["--no-sandbox"],
            )
            page = browser.pages[0] if browser.pages else await browser.new_page()

            # Navigate to WhatsApp Web
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            logger.info("WhatsApp Web loaded. Waiting for chats to appear...")

            # Wait for chat list (up to 30s — user may need to scan QR on first run)
            try:
                await page.wait_for_selector('div[aria-label="Chat list"]', timeout=30_000)
            except Exception:
                await browser.close()
                return "WhatsApp Web not ready. Please open WhatsApp Web manually and scan QR code first."

            # Search for contact
            search_box = page.locator('div[contenteditable="true"][data-tab="3"]')
            await search_box.click()
            await search_box.fill(contact_name)
            await page.wait_for_timeout(2000)

            # Click first result
            first_result = page.locator(f'span[title="{contact_name}"]').first
            if await first_result.count() == 0:
                # Try partial match
                first_result = page.locator(f'span[title*="{contact_name}"]').first

            if await first_result.count() == 0:
                await browser.close()
                return f"Contact '{contact_name}' not found in WhatsApp."

            await first_result.click()
            await page.wait_for_timeout(1000)

            # Type and send message
            msg_box = page.locator('div[contenteditable="true"][data-tab="10"]')
            await msg_box.click()
            await msg_box.fill(message)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2000)

            await browser.close()
            return f"WhatsApp message sent to {contact_name}: '{message}'"
    except Exception as e:
        return f"WhatsApp send failed: {type(e).__name__}: {e}"


# ── TOOL: Playwright Browser Automation ───────────────────────────────────

@mcp.tool()
async def playwright_automation(url: str, action: str = "navigate",
                                selector: str = None, text_to_type: str = None) -> str:
    """
    Automate a headless browser for tasks like form filling, clicking, navigation.
    Args:
        url: URL to navigate to.
        action: 'navigate' | 'click' | 'fill' | 'screenshot'
        selector: CSS selector for the target element.
        text_to_type: Text to type when action is 'fill'.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            result_msg = f"Navigated to {url}"
            if action == "click" and selector:
                await page.locator(selector).click(timeout=8_000)
                await page.wait_for_load_state("networkidle", timeout=10_000)
                result_msg = f"Clicked '{selector}'"
            elif action == "fill" and selector and text_to_type:
                await page.locator(selector).fill(text_to_type)
                result_msg = f"Filled form field '{selector}'"
            elif action == "screenshot":
                sp = str(Path(__file__).parent / "data" / "screenshot.png")
                Path(sp).parent.mkdir(exist_ok=True)
                await page.screenshot(path=sp)
                result_msg = f"Screenshot saved"
            title = await page.title()
            await browser.close()
            return f"{result_msg}. Page: '{title}'"
    except Exception as e:
        return f"Browser automation failed: {e}"


# ── TOOL: Schedule ─────────────────────────────────────────────────────────

@mcp.tool()
def get_schedule() -> str:
    """Returns upcoming deadlines, meetings, and reminders for nnssprasad.
    Pulls from ZENITH Brain (commitments API) first, falls back to local schedule.json.
    """
    # Try Brain API first
    try:
        r = requests.get("http://localhost:3142/api/commitments", timeout=5)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("commitments", data.get("data", []))
            pending = [c for c in items if c.get("status") == "pending"]
            if pending:
                lines = ["Your upcoming tasks and commitments:"]
                for c in pending[:8]:
                    title = c.get("what") or c.get("title", "Untitled")
                    due = c.get("when_due")
                    due_str = f" — due {due}" if due else ""
                    lines.append(f"  • {title}{due_str}")
                return "\n".join(lines)
    except Exception:
        pass  # Fall through to local file

    # Fall back to local schedule.json
    try:
        if SCHEDULE_FILE.exists():
            data = json.loads(SCHEDULE_FILE.read_text())
            events = data.get("events", [])
            if not events:
                return "No upcoming events."
            lines = ["Your upcoming schedule:"]
            for e in events:
                lines.append(f"  • {e.get('time','TBD')} — {e.get('title','Untitled')}")
            return "\n".join(lines)
        else:
            SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
            demo = {"events": [
                {"time": "Today 3:00 PM",    "title": "Team sync meeting"},
                {"time": "Tomorrow 5:00 PM", "title": "Project deadline — ZENITH demo"},
                {"time": "Friday 10:00 AM",  "title": "Code review session"},
            ]}
            SCHEDULE_FILE.write_text(json.dumps(demo, indent=2))
            return "Today: Team sync at 3 PM. Tomorrow: ZENITH demo deadline at 5 PM. Friday: Code review at 10 AM."
    except Exception as e:
        return f"Schedule error: {e}"


# ── TOOL: n8n Workflow ─────────────────────────────────────────────────────

@mcp.tool()
def trigger_n8n_workflow(workflow_id: str, payload: dict = None) -> str:
    """
    Trigger an n8n automation workflow via its webhook.
    Args:
        workflow_id: Webhook path (e.g. 'send-email').
        payload: Optional JSON data for the workflow.
    """
    try:
        url = f"{N8N_BASE_URL}/webhook/{workflow_id}"
        resp = requests.post(url, json=payload or {}, timeout=15,
                             headers={"Content-Type": "application/json"})
        if resp.status_code in (200, 201):
            try:
                return f"Workflow '{workflow_id}' triggered: {resp.json()}"
            except Exception:
                return f"Workflow '{workflow_id}' triggered: {resp.text[:200]}"
        return f"n8n returned HTTP {resp.status_code}"
    except requests.ConnectionError:
        return f"Cannot reach n8n at {N8N_BASE_URL}. Is n8n running?"
    except Exception as e:
        return f"n8n error: {e}"


# ── Standalone server entry ────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting Jarvis MCP Server (stdio transport)...")
    mcp.run(transport="stdio")
