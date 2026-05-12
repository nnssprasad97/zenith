"""
ZENITH — Enterprise Functionality Test Suite
Tests all microservices end-to-end (CI-safe, no camera/mic needed).
Run from: biometrics-sidecar/
"""
import sys, os, json, ast, importlib, subprocess, time
from pathlib import Path

PASS = "\u2705"; FAIL = "\u274c"; WARN = "\u26a0\ufe0f"
results = []

def check(name, fn):
    try:
        msg = fn()
        results.append((PASS, name, msg or "OK"))
    except Exception as e:
        results.append((FAIL, name, str(e)[:120]))

# ═══════════════════════════════════════════════════════
# 1. CORE LIBRARY IMPORTS
# ═══════════════════════════════════════════════════════
def test_cv2():
    if 'cv2' in sys.modules: del sys.modules['cv2']
    import cv2
    cv2.face.LBPHFaceRecognizer_create()
    return f"OpenCV {cv2.__version__} + LBPH OK"

def test_yolo():
    from ultralytics import YOLO
    return "ultralytics YOLO importable"

def test_mcp():
    from mcp.server.fastmcp import FastMCP
    return "FastMCP importable"

def test_playwright():
    from playwright.async_api import async_playwright
    return "Playwright importable"

def test_livekit():
    from livekit.agents import AgentSession, Agent, WorkerOptions, cli, function_tool
    return "livekit-agents v1.x importable"

def test_lk_openai():
    from livekit.plugins import openai; return "livekit-plugins-openai OK"
def test_lk_google():
    from livekit.plugins import google; return "livekit-plugins-google OK"
def test_lk_silero():
    from livekit.plugins import silero; return "livekit-plugins-silero OK"
def test_groq_sdk():
    import groq; return f"groq SDK {groq.__version__} OK"
def test_requests():
    import requests; return f"requests {requests.__version__} OK"
def test_websockets():
    import websockets; return f"websockets {websockets.__version__} OK"
def test_dotenv():
    from dotenv import load_dotenv; load_dotenv(); return "python-dotenv OK"

check("cv2 4.x + LBPHFaceRecognizer",  test_cv2)
check("ultralytics YOLO",               test_yolo)
check("mcp[cli] FastMCP",               test_mcp)
check("Playwright",                     test_playwright)
check("livekit-agents v1.x",            test_livekit)
check("livekit-plugins-openai",         test_lk_openai)
check("livekit-plugins-google",         test_lk_google)
check("livekit-plugins-silero",         test_lk_silero)
check("groq SDK",                       test_groq_sdk)
check("requests",                       test_requests)
check("websockets",                     test_websockets)
check("python-dotenv",                  test_dotenv)

# ═══════════════════════════════════════════════════════
# 2. VISION SERVICE — ZENITH Biometric Auth
# ═══════════════════════════════════════════════════════
def test_yolo_file():
    p = Path("yolov8n.pt")
    if not p.exists(): raise FileNotFoundError("yolov8n.pt missing")
    return f"yolov8n.pt found ({p.stat().st_size//1024} KB)"

def test_trainer():
    p = Path("Face Recognition/trainer/trainer.yml")
    if not p.exists(): raise FileNotFoundError("trainer.yml missing")
    return f"trainer.yml found ({p.stat().st_size//1024} KB)"

def test_lbph_load():
    import cv2
    r = cv2.face.LBPHFaceRecognizer_create()
    r.read("Face Recognition/trainer/trainer.yml")
    return "LBPH loaded from trainer.yml"

def test_haar():
    import cv2
    c = cv2.CascadeClassifier("Face Recognition/haarcascade_frontalface_default.xml")
    if c.empty(): raise RuntimeError("Cascade empty")
    return "Haar cascade loaded"

def test_users_json():
    d = json.loads(Path("users.json").read_text())
    names = list(d.values())
    if not any("nnssprasad" in n for n in names):
        raise ValueError(f"Expected nnssprasad, got: {names}")
    return f"users.json OK: {d}"

def test_vision_import():
    import vision_service
    return "vision_service importable"

def test_vision_ocr():
    # Test pytesseract is importable (OCR pipeline)
    import pytesseract
    return f"pytesseract importable"

check("yolov8n.pt exists",              test_yolo_file)
check("trainer.yml exists",             test_trainer)
check("LBPH load from trainer.yml",     test_lbph_load)
check("Haar cascade load",              test_haar)
check("users.json → nnssprasad",        test_users_json)
check("vision_service module",          test_vision_import)
check("pytesseract (OCR)",              test_vision_ocr)

# ═══════════════════════════════════════════════════════
# 3. MCP SERVER — Tools Validation
# ═══════════════════════════════════════════════════════
def test_mcp_import():
    if "mcp_server" in sys.modules: del sys.modules["mcp_server"]
    import mcp_server as ms
    assert ms.mcp.name == "zenith-local-mcp", f"Expected zenith-local-mcp, got: {ms.mcp.name}"
    return f"mcp_server OK — FastMCP name: {ms.mcp.name}"

def test_serpapi_key():
    from dotenv import load_dotenv; load_dotenv()
    k = os.getenv("SERPAPI_API_KEY","")
    if not k: raise ValueError("SERPAPI_API_KEY missing")
    return f"Key set ({k[:8]}…)"

def test_serpapi_live():
    import requests
    from dotenv import load_dotenv; load_dotenv()
    k = os.getenv("SERPAPI_API_KEY","")
    r = requests.get("https://serpapi.com/search",
                     params={"q":"temperature in Hyderabad right now","api_key":k,"num":1},
                     timeout=12)
    r.raise_for_status()
    data = r.json()
    ab = data.get("answer_box",{})
    ans = ab.get("answer") or ab.get("snippet") or \
          (data.get("organic_results") or [{}])[0].get("snippet","no result")
    return f"SerpAPI live: '{ans[:80]}'"

def test_schedule_file():
    from mcp_server import get_schedule
    result = get_schedule()
    if "error" in result.lower(): raise RuntimeError(result)
    return f"get_schedule OK: '{result[:60]}'"

def test_powercfg():
    r = subprocess.run(["powercfg","/list"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0: raise RuntimeError(r.stderr)
    return f"powercfg /list OK ({len(r.stdout.splitlines())} lines)"

def test_whatsapp_tool_exists():
    from mcp_server import whatsapp_send_message
    import inspect
    sig = inspect.signature(whatsapp_send_message.fn if hasattr(whatsapp_send_message,'fn') else whatsapp_send_message)
    return f"whatsapp_send_message defined — params: {list(sig.parameters.keys())}"

def test_n8n_config():
    from dotenv import load_dotenv; load_dotenv()
    url = os.getenv("N8N_BASE_URL","http://localhost:5678")
    return f"N8N_BASE_URL = {url}"

check("mcp_server import + zenith name", test_mcp_import)
check("SERPAPI_API_KEY in .env",          test_serpapi_key)
check("SerpAPI LIVE search (Hyderabad)", test_serpapi_live)
check("get_schedule() tool",             test_schedule_file)
check("powercfg availability",           test_powercfg)
check("whatsapp_send_message tool",      test_whatsapp_tool_exists)
check("n8n base URL config",             test_n8n_config)

# ═══════════════════════════════════════════════════════
# 4. LIVEKIT VOICE AGENT
# ═══════════════════════════════════════════════════════
def test_lk_env():
    from dotenv import load_dotenv; load_dotenv()
    missing = [k for k in ["LIVEKIT_URL","LIVEKIT_API_KEY","LIVEKIT_API_SECRET"] if not os.getenv(k)]
    if missing: raise ValueError(f"Missing: {missing}")
    url = os.getenv("LIVEKIT_URL")
    return f"LiveKit URL: {url}"

def test_lk_agent_import():
    if "livekit_agent" in sys.modules: del sys.modules["livekit_agent"]
    import livekit_agent as la
    assert hasattr(la, "ZenithAgent"), "ZenithAgent class not found!"
    assert hasattr(la, "entrypoint"), "entrypoint not found!"
    return "livekit_agent: ZenithAgent + entrypoint OK"

def test_groq_key():
    from dotenv import load_dotenv; load_dotenv()
    k = os.getenv("GROQ_API_KEY","")
    if not k: raise ValueError("GROQ_API_KEY missing")
    return f"GROQ_API_KEY set ({k[:12]}…)"

def test_groq_live():
    from groq import Groq
    from dotenv import load_dotenv; load_dotenv()
    c = Groq(api_key=os.getenv("GROQ_API_KEY",""))
    r = c.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":"Reply with exactly: ZENITH_ONLINE"}],
        max_tokens=10
    )
    ans = r.choices[0].message.content.strip()
    if "ZENITH" not in ans: raise AssertionError(f"Got: {ans}")
    return f"Groq LLM LIVE: '{ans}'"

def test_gemini_key():
    from dotenv import load_dotenv; load_dotenv()
    k = os.getenv("GEMINI_API_KEY","")
    if not k: raise ValueError("GEMINI_API_KEY missing")
    return f"GEMINI_API_KEY set ({k[:12]}…)"

def test_google_tts_plugin():
    from livekit.plugins.google import TTS
    tts = TTS(voice_name="en-US-Journey-D")
    return f"Google TTS plugin instantiated OK"

check("LiveKit env vars set",           test_lk_env)
check("livekit_agent: ZenithAgent",     test_lk_agent_import)
check("GROQ_API_KEY in .env",           test_groq_key)
check("Groq LLM LIVE call",             test_groq_live)
check("GEMINI_API_KEY in .env",         test_gemini_key)
check("Google Cloud TTS plugin",        test_google_tts_plugin)

# ═══════════════════════════════════════════════════════
# 5. SIDECAR + CONFIG + WAKE WORD
# ═══════════════════════════════════════════════════════
def test_sidecar_syntax():
    ast.parse(Path("sidecar.py").read_text())
    return "sidecar.py syntax valid"

def test_wake_word():
    from dotenv import load_dotenv; load_dotenv()
    ww = os.getenv("WAKE_WORD","")
    if ww != "zenith": raise ValueError(f"Wake word is '{ww}', expected 'zenith'")
    return f"WAKE_WORD=zenith ✓"

def test_config():
    import config
    return f"config.py: USER={config.USER_NAME}, WAKE={config.WAKE_WORD}"

def test_launch_ts():
    src = Path("../launch.ts").read_text(encoding="utf-8")
    if "ZENITH" not in src: raise AssertionError("ZENITH not found in launch.ts")
    return "launch.ts contains ZENITH branding"

check("sidecar.py syntax",              test_sidecar_syntax)
check("WAKE_WORD=zenith",               test_wake_word)
check("config.py",                      test_config)
check("launch.ts ZENITH branding",      test_launch_ts)

# ═══════════════════════════════════════════════════════
# 6. WHATSAPP LIVE TOOL READINESS (no actual send)
# ═══════════════════════════════════════════════════════
def test_playwright_chromium():
    import subprocess
    r = subprocess.run(
        ["python", "-c",
         "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop(); print('OK')"],
        capture_output=True, text=True, timeout=30
    )
    if "OK" not in r.stdout:
        raise RuntimeError(r.stderr[:100] or "Playwright chromium launch failed")
    return "Playwright Chromium launches OK"

def test_whatsapp_session_dir():
    d = Path("data/whatsapp_session")
    d.mkdir(parents=True, exist_ok=True)
    return f"WhatsApp session dir ready: {d}"

check("Playwright Chromium launch",     test_playwright_chromium)
check("WhatsApp session dir",           test_whatsapp_session_dir)

# ═══════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════
W = 68
print("\n" + "═"*W)
print("  ██████████   ZENITH — ENTERPRISE TEST REPORT   ██████████")
print("═"*W)
passed = sum(1 for r in results if r[0]==PASS)
failed = sum(1 for r in results if r[0]==FAIL)
for icon,name,msg in results:
    print(f"  {icon}  {name:<42}  {msg}")
print("═"*W)
pct = int(passed/len(results)*100)
bar = "█"*int(pct/5) + "░"*(20-int(pct/5))
print(f"  [{bar}] {pct}%   PASSED: {passed}/{len(results)}   FAILED: {failed}")
print("═"*W)
if failed:
    print("\n  ⚠  FAILED TESTS:")
    for icon,name,msg in results:
        if icon==FAIL:
            print(f"     • {name}: {msg}")
print()
sys.exit(0 if failed==0 else 1)
