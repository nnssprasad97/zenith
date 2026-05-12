/**
 * ZENITH — Zero Latency Engineered Network for Intuitive Task Handling
 * Unified Launcher — single command starts all services with colour-coded output.
 *
 * Usage:  bun run launch
 *
 * Services started (staggered):
 *   [BRAIN  ]  Bun daemon — WebSocket server + dashboard (port 3142)
 *   [LIVEKIT]  Python LiveKit voice agent — WebRTC + Groq + Gemini + Google TTS
 *   [SIDECAR]  Python face auth + legacy WebSocket mic bridge
 */

import { spawn } from "bun";
import path from "node:path";
import os from "node:os";

const SIDECAR_DIR = path.join(import.meta.dir, "biometrics-sidecar");
const PYTHON = "python";

// ── ANSI colours ───────────────────────────────────────────────────────────
const R = "\x1b[0m";
const B = "\x1b[1m";
const C = { brain: "\x1b[36m", livekit: "\x1b[33m", sidecar: "\x1b[32m", sys: "\x1b[34m", err: "\x1b[31m" };

function tag(name: string, c: string) { return `${B}${c}[${name.padEnd(8)}]${R} `; }
function log(name: string, c: string, line: string, isErr = false) {
  process.stdout.write(`${tag(name, isErr ? C.err : c)}${line}\n`);
}

// ── Service definitions ────────────────────────────────────────────────────
const services = [
  {
    name: "BRAIN",
    color: C.brain,
    cmd: [Bun.which("bun") ?? "bun", "--hot", "run", "src/daemon/index.ts"] as [string, ...string[]],
    cwd: import.meta.dir,
    delay: 0,
  },
  {
    name: "LIVEKIT",
    color: C.livekit,
    cmd: [PYTHON, "livekit_agent.py", "dev"] as [string, ...string[]],
    cwd: SIDECAR_DIR,
    delay: 4000,   // wait for brain to bind its port
  },
  {
    name: "SIDECAR",
    color: C.sidecar,
    cmd: [PYTHON, "sidecar.py"] as [string, ...string[]],
    cwd: SIDECAR_DIR,
    delay: 6000,   // after brain is fully ready
  },
];

// ── Stream relay ───────────────────────────────────────────────────────────
async function relay(stream: ReadableStream<Uint8Array> | null, name: string, color: string, isErr = false) {
  if (!stream) return;
  const reader = stream.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const l of lines) if (l.trim()) log(name, color, l, isErr);
  }
  if (buf.trim()) log(name, color, buf, isErr);
}

// ── Spawner ────────────────────────────────────────────────────────────────
const procs: ReturnType<typeof spawn>[] = [];

async function start(svc: (typeof services)[number]) {
  log("SYSTEM", C.sys, `▶ Starting ${svc.name}: ${svc.cmd.join(" ")}`);
  const p = spawn({
    cmd: svc.cmd,
    cwd: svc.cwd,
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env },
  });
  procs.push(p);
  relay(p.stdout, svc.name, svc.color);
  relay(p.stderr, svc.name, svc.color, true);
  p.exited.then(code => {
    if (code !== 0) log("SYSTEM", C.err, `${svc.name} exited with code ${code} — check output above`);
  });
}

// ── Shutdown ───────────────────────────────────────────────────────────────
function shutdown() {
  log("SYSTEM", C.sys, "\nCtrl+C — shutting down all J.A.R.V.I.S. services...");
  for (const p of procs) { try { p.kill(); } catch {} }
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

// ── Main ───────────────────────────────────────────────────────────────────
console.clear();
console.log(`${B}${C.sys}`);
console.log("  ╔══════════════════════════════════════════╗");
console.log("  ║       Z E N I T H   L A U N C H E R     ║");
console.log("  ║  Zero Latency Engineered Network for    ║");
console.log("  ║  Intuitive Task Handling                ║");
console.log("  ╠══════════════════════════════════════════╣");
console.log(`  ║  ${C.brain}BRAIN${C.sys}    Bun Daemon — port 3142           ║`);
console.log(`  ║  ${C.livekit}LIVEKIT${C.sys}  WebRTC Voice Agent               ║`);
console.log(`  ║  ${C.sidecar}SIDECAR${C.sys}  Face Auth + Mic Bridge           ║`);
console.log("  ╚══════════════════════════════════════════╝");
console.log(`${R}\n`);

for (const svc of services) {
  if (svc.delay) await Bun.sleep(svc.delay);
  await start(svc);
}

log("SYSTEM", C.sys, "✅ All services started. Press Ctrl+C to stop all.\n");

// Keep process alive indefinitely
await new Promise(() => {});
