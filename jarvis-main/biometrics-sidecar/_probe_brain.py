"""Probe all ZENITH Brain REST endpoints and WebSocket flow"""
import requests, json, asyncio, websockets

BASE = "http://localhost:3142"
results = []

def check(name, fn):
    try:
        msg = fn()
        results.append(("OK", name, msg))
    except Exception as e:
        results.append(("FAIL", name, str(e)[:120]))

# 1. Health
def test_health():
    r = requests.get(f"{BASE}/health", timeout=5)
    d = r.json()
    svcs = [k for k,v in d.get("services",{}).items() if v=="running"]
    return f"HTTP 200 - services: {svcs}"

# 2. Dashboard HTML
def test_dashboard():
    r = requests.get(f"{BASE}/", timeout=5)
    return f"HTTP {r.status_code} - {len(r.text)} bytes"

# 3. API routes probe
def test_api_routes():
    endpoints = [
        "/api/commitments", "/api/tasks", "/api/goals",
        "/api/workflows", "/api/memory", "/api/conversations",
        "/api/settings", "/api/observations", "/api/schedule",
        "/api/agents", "/api/sidecars", "/api/authority/requests",
        "/api/content", "/api/documents"
    ]
    found = []
    for ep in endpoints:
        try:
            r = requests.get(f"{BASE}{ep}", timeout=3)
            if r.status_code not in (404,):
                found.append(f"{ep}={r.status_code}")
        except Exception:
            pass
    return f"Found {len(found)} endpoints: {found}"

# 4. WebSocket connect + welcome
def test_ws_connect():
    async def _ws():
        async with websockets.connect("ws://localhost:3142/ws", open_timeout=5) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            d = json.loads(msg)
            return f"WS connected - msg type={d.get('type')} keys={list(d.get('payload',{}).keys())[:5]}"
    return asyncio.run(_ws())

# 5. WebSocket chat roundtrip
def test_ws_chat():
    async def _chat():
        async with websockets.connect("ws://localhost:3142/ws", open_timeout=5) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)  # welcome
            await ws.send(json.dumps({
                "type": "chat",
                "payload": {"text": "What are my goals and tasks today? List them briefly.", "conversationId": "zenith-test-001"}
            }))
            full = ""
            for _ in range(20):
                raw = await asyncio.wait_for(ws.recv(), timeout=20)
                d = json.loads(raw)
                t = d.get("type", "")
                p = d.get("payload", {})
                if t == "stream":
                    full += p.get("text", "")
                elif t == "status" and p.get("status") == "done":
                    full = p.get("fullText", full)
                    break
            return f"Chat response ({len(full)} chars): {full[:200]!r}"
    return asyncio.run(_chat())

# 6. Workflows API
def test_workflows():
    r = requests.get(f"{BASE}/api/workflows", timeout=5)
    if r.status_code == 200:
        d = r.json()
        wfs = d if isinstance(d, list) else d.get("workflows", d.get("data", []))
        return f"HTTP 200 - {len(wfs)} workflows"
    return f"HTTP {r.status_code}"

# 7. Goals API
def test_goals():
    r = requests.get(f"{BASE}/api/goals", timeout=5)
    if r.status_code == 200:
        d = r.json()
        goals = d if isinstance(d, list) else d.get("goals", d.get("data", []))
        return f"HTTP 200 - {len(goals)} goals"
    return f"HTTP {r.status_code}"

# 8. Commitments API  
def test_commitments():
    r = requests.get(f"{BASE}/api/commitments", timeout=5)
    if r.status_code == 200:
        d = r.json()
        items = d if isinstance(d, list) else d.get("commitments", d.get("data", []))
        return f"HTTP 200 - {len(items)} commitments"
    return f"HTTP {r.status_code}"

check("Health endpoint",          test_health)
check("Dashboard HTML",           test_dashboard)
check("API routes probe",         test_api_routes)
check("WebSocket connect",        test_ws_connect)
check("WebSocket chat roundtrip", test_ws_chat)
check("Workflows API",            test_workflows)
check("Goals API",                test_goals)
check("Commitments API",          test_commitments)

print()
print("=" * 68)
print("  ZENITH BRAIN — FULL CONNECTIVITY AUDIT")
print("=" * 68)
for status, name, msg in results:
    icon = "✅" if status == "OK" else "❌"
    print(f"  {icon}  {name:<35} {msg}")
print("=" * 68)
ok = sum(1 for s, _, _ in results if s == "OK")
print(f"  {ok}/{len(results)} checks passed")
print()
