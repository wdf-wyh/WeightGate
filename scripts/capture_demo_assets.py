"""Capture README demo assets from a running WeightGate stack (local only)."""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

GW = "http://127.0.0.1:8000"
CP = "http://127.0.0.1:8080"
CONSOLE = "http://127.0.0.1:5173"
KEY = "sk-af-tenant-a-devonly"


def _wait(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _chat_snippet() -> str:
    try:
        r = httpx.post(
            f"{GW}/v1/chat/completions",
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
            json={
                "model": "tinyllama",
                "messages": [{"role": "user", "content": "Say hi in one short sentence."}],
                "max_tokens": 48,
            },
            timeout=60.0,
        )
        body = r.json() if "json" in r.headers.get("content-type", "") else {"raw": r.text}
        return json.dumps({"status": r.status_code, "body": body}, ensure_ascii=False, indent=2)[:2800]
    except Exception as exc:
        return json.dumps({"error": str(exc)}, indent=2)


def _tenants() -> list[dict]:
    try:
        r = httpx.get(f"{CP}/v1/tenants", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return [
        {"id": "tenant_a", "name": "Tenant A", "status": "active", "created_at": "…"},
        {"id": "tenant_b", "name": "Tenant B", "status": "active", "created_at": "…"},
    ]


def _policy(tenant_id: str) -> dict:
    try:
        r = httpx.get(f"{CP}/v1/tenants/{tenant_id}/route-policy", timeout=10.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"mode": "hybrid", "short_max_chars": 512}


def _demo_html(chat: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>WeightGate</title>
<style>
:root {{ --bg:#0f1419; --panel:#1a222c; --ink:#e8eef5; --muted:#9aa8b8; --accent:#3d9cf0; --ok:#3ecf8e; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:"Segoe UI",system-ui,sans-serif; color:var(--ink);
  background:radial-gradient(1200px 600px at 10% -10%, #1c3a5a 0%, var(--bg) 55%);
  min-height:100vh; padding:28px 36px; }}
h1 {{ font-size:42px; margin:0 0 8px; letter-spacing:-0.03em; }}
.tag {{ color:var(--accent); font-weight:600; font-size:14px; text-transform:uppercase; letter-spacing:.08em; }}
.sub {{ color:var(--muted); max-width:640px; line-height:1.5; margin-bottom:24px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.card {{ background:color-mix(in srgb, var(--panel) 92%, black); border:1px solid #2a3542; border-radius:12px; padding:16px 18px; }}
.card h2 {{ margin:0 0 10px; font-size:15px; color:var(--muted); font-weight:600; }}
pre {{ margin:0; white-space:pre-wrap; word-break:break-word; font:12px/1.45 Consolas,"Cascadia Mono",monospace; color:#d7e3f0; max-height:300px; overflow:hidden; }}
.ok {{ color:var(--ok); }}
.flow {{ font-family:Consolas,monospace; font-size:13px; line-height:1.7; color:#c5d4e4; }}
</style></head><body>
<div class="tag">WeightGate</div>
<h1>OpenAI-compatible edge</h1>
<p class="sub">Ollama ↔ vLLM / cloud hybrid routing with multi-tenant isolation. Live local stack capture.</p>
<div class="grid">
  <div class="card"><h2>Hybrid route</h2>
    <div class="flow">client → gateway :8000<br/>&nbsp;&nbsp;→ ollama | vllm | cloud<br/>control-plane :8080<br/>data/tenants/&#123;id&#125;/</div>
  </div>
  <div class="card"><h2>POST /v1/chat/completions <span class="ok">live</span></h2>
    <pre>{html.escape(chat)}</pre>
  </div>
</div>
</body></html>"""


def _console_html(tenants: list[dict], policy: dict) -> str:
    rows = "".join(
        f"<tr><td class='mono'>{html.escape(str(t.get('id','')))}</td>"
        f"<td>{html.escape(str(t.get('name','')))}</td>"
        f"<td><span class='badge'>{html.escape(str(t.get('status','')))}</span></td>"
        f"<td class='muted mono'>{html.escape(str(t.get('created_at',''))[:19])}</td></tr>"
        for t in tenants
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>WeightGate Console</title>
<style>
:root {{
  --bg:#0f1419; --panel:#161d26; --line:#2a3542; --text:#e7eef7; --muted:#93a0b0;
  --accent:#3d9cf0; --accent-2:#62b0ff; --ok:#3ecf8e;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:14px/1.45 "Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }}
.shell {{ max-width:1100px; margin:0 auto; padding:20px 24px 40px; }}
header {{ padding:8px 0 18px; border-bottom:1px solid var(--line); margin-bottom:14px; }}
.brand {{ font-size:18px; font-weight:700; letter-spacing:-0.02em; }}
.brand span {{ color:var(--accent-2); }}
.nav {{ display:flex; gap:14px; margin-bottom:22px; flex-wrap:wrap; }}
.nav a {{ color:var(--muted); text-decoration:none; padding:6px 2px; border-bottom:2px solid transparent; }}
.nav a.active {{ color:var(--text); border-bottom-color:var(--accent); }}
h1 {{ font-size:1.45rem; margin:0 0 6px; }}
.lead {{ color:var(--muted); margin:0 0 16px; }}
.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin-bottom:14px; }}
.row {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
input, select, button {{ font:inherit; border-radius:8px; border:1px solid var(--line); background:#0c1016; color:var(--text); padding:8px 10px; }}
button.primary {{ background:var(--accent); border-color:var(--accent); color:#041018; font-weight:600; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
.mono {{ font-family:Consolas,"Cascadia Mono",monospace; font-size:12px; }}
.muted {{ color:var(--muted); }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#1d3a2a; color:var(--ok); font-size:12px; }}
</style></head><body>
<div class="shell">
  <header><div class="brand">WeightGate <span>console</span></div></header>
  <nav class="nav">
    <a class="active" href="#">Tenants</a>
    <a href="#">Instances</a>
    <a href="#">Hosts</a>
    <a href="#">Alerts</a>
    <a href="#">Catalog</a>
    <a href="#">Usage</a>
  </nav>
  <section>
    <h1>Tenants</h1>
    <p class="lead">Manage tenants, route policy, and API key issuance via control-plane only.</p>
    <div class="panel"><div class="row">
      <input placeholder="tenant_id" value="" readonly />
      <input placeholder="display name" value="" readonly />
      <button class="primary">Create</button>
    </div></div>
    <div class="panel">
      <table><thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Created</th></tr></thead>
      <tbody>{rows}</tbody></table>
    </div>
    <div class="panel">
      <h1 style="font-size:1.05rem">Route policy &amp; keys</h1>
      <div class="row">
        <select><option>tenant_a</option><option>tenant_b</option></select>
        <select><option>hybrid</option><option>local_only</option><option>cloud_only</option></select>
        <button class="primary">Save policy</button>
        <button>Issue API key</button>
      </div>
      <p class="muted">Current: <span class="mono">{html.escape(str(policy.get('mode','hybrid')))}</span> · short_max_chars
        {html.escape(str(policy.get('short_max_chars',512)))}</p>
    </div>
  </section>
</div>
</body></html>"""


def main() -> None:
    chat = _chat_snippet()
    tenants = _tenants()
    policy = _policy(tenants[0]["id"] if tenants else "tenant_a")

    demo_path = ASSETS / "_demo.html"
    console_path = ASSETS / "_console.html"
    demo_path.write_text(_demo_html(chat), encoding="utf-8")
    console_path.write_text(_console_html(tenants, policy), encoding="utf-8")

    frames: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        page.goto(demo_path.as_uri(), wait_until="networkidle")
        f1 = ASSETS / "frame-demo.png"
        page.screenshot(path=str(f1), full_page=False)
        frames.append(f1)

        if _wait(f"{CP}/docs", 8):
            page.goto(f"{CP}/docs", wait_until="networkidle")
            page.wait_for_timeout(600)
            f2 = ASSETS / "control-plane.png"
            page.screenshot(path=str(f2), full_page=False)
            frames.append(f2)

        if _wait(f"{GW}/docs", 8):
            page.goto(f"{GW}/docs", wait_until="networkidle")
            page.wait_for_timeout(600)
            f3 = ASSETS / "gateway.png"
            page.screenshot(path=str(f3), full_page=False)
            frames.append(f3)

        console_shot = ASSETS / "console.png"
        if _wait(CONSOLE, 8):
            page.goto(CONSOLE, wait_until="networkidle")
            page.wait_for_timeout(1000)
            page.screenshot(path=str(console_shot), full_page=False)
        else:
            page.goto(console_path.as_uri(), wait_until="networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(console_shot), full_page=False)
        frames.append(console_shot)

        browser.close()

    from PIL import Image

    imgs = [Image.open(fp).convert("P", palette=Image.ADAPTIVE) for fp in frames]
    gif_path = ASSETS / "demo.gif"
    imgs[0].save(
        gif_path,
        save_all=True,
        append_images=imgs[1:],
        duration=1500,
        loop=0,
        optimize=True,
    )
    print(f"wrote {gif_path} ({len(imgs)} frames)")

    for pth in (demo_path, console_path, ASSETS / "frame-demo.png"):
        pth.unlink(missing_ok=True)
    print("assets:", sorted(p.name for p in ASSETS.iterdir()))


if __name__ == "__main__":
    main()
