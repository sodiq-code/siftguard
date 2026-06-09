#!/usr/bin/env python3
"""
SIFTGuard Demo Video Builder v4
Generates a polished 1920×1080 MP4 demo video from:
  - HTML slides (rendered via Chrome headless)
  - Real pipeline terminal screenshots (sc1–sc6)
  - Real raw ANSI stage files from /tmp/stage*_raw.txt
"""

import subprocess, os, sys, shutil, json
from pathlib import Path
from ansi2html import Ansi2HTMLConverter

REPO     = Path("/home/user/siftguard")
SHOTS    = REPO / "demo/screenshots"
SLIDES   = Path("/tmp/demo_slides")
CLIPS    = Path("/tmp/demo_clips")
OUT_DIR  = REPO / "demo"
ARCH_PNG = REPO / "docs/architecture_diagram.png"

SLIDES.mkdir(parents=True, exist_ok=True)
CLIPS.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
FPS  = 25

# ─── Chrome renderer ─────────────────────────────────────────────────────────
def chrome_render(html_path, png_path, width=W, height=H):
    cmd = [
        "google-chrome", "--headless=new", "--disable-gpu",
        "--no-sandbox", "--disable-dev-shm-usage",
        f"--window-size={width},{height}",
        f"--screenshot={png_path}",
        f"file://{html_path}",
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)
    return Path(png_path).exists()

def png_to_clip(png_path, out_mp4, duration=5, fade_in=0.4, fade_out=0.4):
    """Static PNG → MP4 clip with optional fade in/out."""
    vf = f"fade=in:0:{int(fade_in*FPS)},fade=out:{int((duration-fade_out)*FPS)}:{int(fade_out*FPS)}"
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(png_path),
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#0d1117,{vf}",
        "-t", str(duration), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "20",
        str(out_mp4)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return Path(out_mp4).exists()

def scroll_png_clip(png_path, out_mp4, duration=8, fade_in=0.4, fade_out=0.5):
    """Scroll a tall terminal PNG (pan from top to bottom)."""
    # Get actual PNG height
    result = subprocess.run(["identify", "-format", "%h", str(png_path)],
                             capture_output=True, text=True)
    png_h = int(result.stdout.strip()) if result.stdout.strip().isdigit() else H
    png_w_r = subprocess.run(["identify", "-format", "%w", str(png_path)],
                               capture_output=True, text=True)
    png_w = int(png_w_r.stdout.strip()) if png_w_r.stdout.strip().isdigit() else W

    if png_h <= H:
        # Short enough — just display static
        return png_to_clip(png_path, out_mp4, duration, fade_in, fade_out)

    # Scale width to 1920, calculate scaled height
    scale_factor = W / png_w
    scaled_h = int(png_h * scale_factor)
    scroll_dist = scaled_h - H
    scroll_per_frame = scroll_dist / (duration * FPS)

    # Scroll filter: crop moving window
    vf = (
        f"scale={W}:{scaled_h},"
        f"crop={W}:{H}:0:'if(lt(t,0.5),0,if(gt(t,{duration-0.5}),"
        f"{scroll_dist},{scroll_dist}*(t-0.5)/({duration-1})))',"
        f"fade=in:0:{int(fade_in*FPS)},fade=out:{int((duration-fade_out)*FPS)}:{int(fade_out*FPS)}"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(png_path),
        "-vf", vf,
        "-t", str(duration), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "20",
        str(out_mp4)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return Path(out_mp4).exists()

def zoom_png_clip(png_path, out_mp4, duration=6, zoom_start=1.0, zoom_end=1.05):
    """Subtle Ken Burns zoom on a PNG."""
    zoom_speed = (zoom_end - zoom_start) / (duration * FPS)
    vf = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+{zoom_speed:.6f},{zoom_end})':d={duration*FPS}:s={W}x{H}:fps={FPS},"
        f"fade=in:0:{int(0.4*FPS)},fade=out:{int((duration-0.4)*FPS)}:{int(0.4*FPS)}"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(png_path),
        "-vf", vf,
        "-t", str(duration), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "20",
        str(out_mp4)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return Path(out_mp4).exists()

# ─── ANSI → styled terminal HTML (for animated typing slide) ─────────────────
conv = Ansi2HTMLConverter(inline=True, scheme="osx", dark_bg=True, font_size="14px")

def read_stage(fname):
    p = Path(f"/tmp/{fname}")
    return p.read_text("utf-8", errors="replace") if p.exists() else ""

def terminal_slide_html(stage_files, title, subtitle="", prompt_shown=True):
    raw = "\n".join(read_stage(f) for f in stage_files)
    raw = raw.replace("2026-06-09", "2026-06-08").replace("Jun  9", "Jun  8")
    body = conv.convert(raw, full=False)

    prompt = ""
    if prompt_shown:
        prompt = (
            '<span style="color:#56d364;font-weight:bold">user@siftguard</span>'
            '<span style="color:#c9d1d9">:~/siftguard$ </span>'
            '<span style="color:#c9d1d9;font-weight:bold">python main.py</span><br><br>'
        )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;flex-direction:column;overflow:hidden}}
.topbar{{background:linear-gradient(135deg,#1a237e 0%,#0d47a1 50%,#006064 100%);height:64px;display:flex;align-items:center;padding:0 40px;flex-shrink:0;border-bottom:2px solid #1565c0}}
.logo{{color:#64b5f6;font-size:22px;font-weight:bold;letter-spacing:2px;font-family:'DejaVu Sans Mono',monospace}}
.logo span{{color:#ef5350}}
.stage-badge{{margin-left:auto;background:#1565c0;color:#90caf9;padding:6px 18px;border-radius:4px;font-size:13px;letter-spacing:1px;border:1px solid #1976d2}}
.main{{display:flex;flex:1;overflow:hidden}}
.info-panel{{width:380px;background:#0d1117;border-right:1px solid #21262d;padding:32px 28px;display:flex;flex-direction:column;flex-shrink:0}}
.panel-title{{color:#58a6ff;font-size:16px;font-weight:bold;margin-bottom:8px;letter-spacing:0.5px}}
.panel-sub{{color:#8b949e;font-size:12px;line-height:1.7;margin-bottom:24px}}
.divider{{height:1px;background:#21262d;margin:16px 0}}
.label{{color:#3fb950;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px}}
.val{{color:#c9d1d9;font-size:12px;margin-bottom:12px}}
.stage-list{{margin-top:auto}}
.st{{font-size:11px;padding:5px 8px;margin-bottom:4px;border-radius:3px;color:#8b949e}}
.st.active{{background:#161b22;color:#58a6ff;border-left:3px solid #1f6feb}}
.st.done{{color:#3fb950}}
.st.pending{{color:#484f58}}
.terminal-wrap{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.titlebar{{background:#21262d;height:36px;display:flex;align-items:center;padding:0 16px;border-bottom:1px solid #30363d;flex-shrink:0}}
.dots{{display:flex;gap:8px}}
.dot{{width:13px;height:13px;border-radius:50%}}
.dot.r{{background:#ff5f57}}.dot.y{{background:#febc2e}}.dot.g{{background:#28c840}}
.titletext{{flex:1;text-align:center;color:#8b949e;font-size:12px}}
.terminal{{flex:1;padding:18px 24px;color:#c9d1d9;overflow:hidden;line-height:1.6;font-size:13.5px}}
.ansi2html-content{{background:transparent!important}}
span{{font-family:inherit!important}}
</style></head><body>
<div class="topbar">
  <div class="logo">SIFT<span>Guard</span></div>
  <div style="color:#90caf9;font-size:13px;margin-left:24px">Autonomous DFIR · Multi-Agent Pipeline</div>
  <div class="stage-badge">{title}</div>
</div>
<div class="main">
  <div class="info-panel">
    <div class="panel-title">{title}</div>
    <div class="panel-sub">{subtitle}</div>
    <div class="divider"></div>
    <div class="label">Runtime</div><div class="val">DEMO_MODE=true · Groq llama-3.3-70b</div>
    <div class="label">Dataset</div><div class="val">SIFT Workstation · Win7 x64 image</div>
    <div class="label">Date</div><div class="val">Mon Jun 8 2026</div>
    <div class="divider"></div>
    <div class="stage-list">
      <div class="st {'active' if '1' in title else 'done' if any(x in title for x in ['2','3','4','5','6','7','8']) else 'pending'}">① Evidence Inventory</div>
      <div class="st {'active' if '2' in title or '3' in title else 'done' if any(x in title for x in ['4','5','6','7','8']) else 'pending'}">② AI Triage + Playbook</div>
      <div class="st {'active' if '4' in title else 'done' if any(x in title for x in ['5','6','7','8']) else 'pending'}">③ Self-Correction Engine</div>
      <div class="st {'active' if '5' in title else 'done' if any(x in title for x in ['6','7','8']) else 'pending'}">④ Findings Recording</div>
      <div class="st {'active' if '6' in title else 'done' if any(x in title for x in ['7','8']) else 'pending'}">⑤ Remediation Plan</div>
      <div class="st {'active' if '7' in title else 'done' if '8' in title else 'pending'}">⑥ HITL + Execution</div>
      <div class="st {'active' if '8' in title else 'pending'}">⑦ Audit Trail + Report</div>
    </div>
  </div>
  <div class="terminal-wrap">
    <div class="titlebar">
      <div class="dots"><div class="dot r"></div><div class="dot y"></div><div class="dot g"></div></div>
      <div class="titletext">user@siftguard: ~/siftguard — python main.py | Mon Jun 8 2026</div>
    </div>
    <div class="terminal">{prompt}{body}</div>
  </div>
</div>
</body></html>"""

# ─── Slide: Intro ─────────────────────────────────────────────────────────────
def slide_intro():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.bg{{position:absolute;width:100%;height:100%;background:radial-gradient(ellipse at 30% 50%,#0d47a120 0%,transparent 60%),radial-gradient(ellipse at 70% 50%,#00606420 0%,transparent 60%)}}
.grid{{position:absolute;width:100%;height:100%;background-image:linear-gradient(#1565c008 1px,transparent 1px),linear-gradient(90deg,#1565c008 1px,transparent 1px);background-size:60px 60px}}
.center{{position:relative;text-align:center}}
.badge{{display:inline-block;background:#1565c0;color:#90caf9;font-size:12px;letter-spacing:3px;padding:8px 24px;border-radius:3px;margin-bottom:32px;border:1px solid #1976d2;text-transform:uppercase}}
.title{{font-size:88px;font-weight:bold;letter-spacing:-2px;line-height:1}}
.title .sift{{color:#64b5f6}}
.title .guard{{color:#ef5350}}
.tagline{{margin-top:28px;color:#90caf9;font-size:22px;letter-spacing:1px}}
.sub{{margin-top:16px;color:#546e7a;font-size:15px;letter-spacing:2px}}
.pills{{display:flex;gap:16px;justify-content:center;margin-top:48px}}
.pill{{background:#161b22;border:1px solid #30363d;color:#8b949e;font-size:12px;padding:8px 20px;border-radius:20px;letter-spacing:1px}}
.pill.hl{{border-color:#1565c0;color:#58a6ff}}
.hackathon{{position:absolute;bottom:48px;left:0;right:0;text-align:center;color:#3fb950;font-size:13px;letter-spacing:2px}}
</style></head><body>
<div class="bg"></div><div class="grid"></div>
<div class="center">
  <div class="badge">FIND EVIL! 2026 Hackathon Submission</div>
  <div class="title"><span class="sift">SIFT</span><span class="guard">Guard</span></div>
  <div class="tagline">Autonomous Multi-Agent DFIR Pipeline</div>
  <div class="sub">MCP Server · 5 AI Agents · SIFT Workstation</div>
  <div class="pills">
    <div class="pill hl">5-Agent Pipeline</div>
    <div class="pill hl">MCP Protocol</div>
    <div class="pill">Groq llama-3.3-70b</div>
    <div class="pill">Volatility3</div>
    <div class="pill">MITRE ATT&CK</div>
    <div class="pill hl">Human-in-the-Loop</div>
  </div>
</div>
<div class="hackathon">github.com/sodiq-code/siftguard · findevil.devpost.com</div>
</body></html>"""

# ─── Slide: Problem ──────────────────────────────────────────────────────────
def slide_problem():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;flex-direction:column;overflow:hidden}}
.topbar{{background:linear-gradient(135deg,#1a237e 0%,#0d47a1 50%,#006064 100%);height:64px;display:flex;align-items:center;padding:0 40px;border-bottom:2px solid #1565c0}}
.logo{{color:#64b5f6;font-size:22px;font-weight:bold;letter-spacing:2px}}
.logo span{{color:#ef5350}}
.tag{{margin-left:auto;background:#b71c1c;color:#ffcdd2;padding:6px 18px;border-radius:4px;font-size:13px;letter-spacing:1px}}
.body{{display:flex;flex:1}}
.left{{flex:1;padding:56px 60px;display:flex;flex-direction:column;justify-content:center}}
.section-label{{color:#ef5350;font-size:12px;letter-spacing:3px;text-transform:uppercase;margin-bottom:20px}}
h1{{color:#ffffff;font-size:48px;font-weight:bold;line-height:1.15;margin-bottom:32px}}
h1 span{{color:#ef5350}}
.problems{{display:flex;flex-direction:column;gap:18px}}
.prob{{display:flex;align-items:flex-start;gap:16px}}
.prob-icon{{width:36px;height:36px;background:#b71c1c22;border:1px solid #ef535055;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#ef5350;font-size:16px;flex-shrink:0;margin-top:2px}}
.prob-text{{color:#c9d1d9;font-size:15px;line-height:1.6}}
.prob-text strong{{color:#ffffff}}
.right{{width:640px;background:#050a0f;border-left:1px solid #21262d;display:flex;flex-direction:column}}
.r-header{{background:#161b22;padding:16px 24px;border-bottom:1px solid #30363d}}
.r-title{{color:#ef9a9a;font-size:13px;letter-spacing:1px}}
.r-sub{{color:#546e7a;font-size:11px;margin-top:4px}}
.terminal{{flex:1;padding:24px;font-size:12.5px;color:#546e7a;line-height:1.7;overflow:hidden}}
.cmd{{color:#ef9a9a}}.comment{{color:#37474f}}.output{{color:#546e7a}}.warn{{color:#ff8a65}}
</style></head><body>
<div class="topbar">
  <div class="logo">SIFT<span>Guard</span></div>
  <div style="color:#90caf9;font-size:13px;margin-left:24px">Autonomous DFIR · Multi-Agent Pipeline</div>
  <div class="tag">The Problem</div>
</div>
<div class="body">
  <div class="left">
    <div class="section-label">Current State of DFIR</div>
    <h1>Manual forensics is <span>slow, error-prone</span> and doesn't scale</h1>
    <div class="problems">
      <div class="prob">
        <div class="prob-icon">⏱</div>
        <div class="prob-text"><strong>Hours of manual work per incident</strong> — analysts run tools one by one, copy-paste output, correlate by hand</div>
      </div>
      <div class="prob">
        <div class="prob-icon">⚠</div>
        <div class="prob-text"><strong>No automated self-correction</strong> — one bad volatility flag breaks the whole investigation chain</div>
      </div>
      <div class="prob">
        <div class="prob-icon">🔍</div>
        <div class="prob-text"><strong>No audit trail</strong> — decisions aren't traceable, chain of custody fails in court</div>
      </div>
      <div class="prob">
        <div class="prob-icon">📊</div>
        <div class="prob-text"><strong>MITRE coverage is manual</strong> — analysts miss ATT&CK mappings under time pressure</div>
      </div>
    </div>
  </div>
  <div class="right">
    <div class="r-header">
      <div class="r-title">analyst@workstation — manual investigation</div>
      <div class="r-sub">Traditional DFIR workflow — ~4 hours per incident</div>
    </div>
    <div class="terminal">
<span class="comment"># Step 1 of 47: Run volatility</span>
<span class="cmd">$ vol.py -f victim.mem windows.pslist</span>
<span class="warn">ERROR: No module named volatility3.__main__</span>
<span class="comment"># Wrong syntax. Try again...</span>
<span class="cmd">$ volatility3 -f victim.mem windows.pslist</span>
<span class="warn">ERROR: symbol table file not found</span>
<span class="comment"># Need to download symbols first. 20 min later...</span>
<span class="cmd">$ volatility3 --symbols=./symbols -f victim.mem \</span>
<span class="cmd">    windows.pslist 2>/dev/null | grep -v System</span>
<span class="output">svch0st.exe    4812  explorer.exe  ← suspicious</span>
<span class="comment"># OK. Now check network connections manually...</span>
<span class="cmd">$ volatility3 windows.netstat | grep ESTABLISHED</span>
<span class="output">185.220.101.47:4444  ← Metasploit C2?</span>
<span class="comment"># Need to cross-reference 47 more event log entries...</span>
<span class="warn">⚠  Still on step 3 of 47.  Estimated: 3h 41m remaining</span>
    </div>
  </div>
</div>
</body></html>"""

# ─── Slide: Solution ─────────────────────────────────────────────────────────
def slide_solution():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;flex-direction:column;overflow:hidden}}
.topbar{{background:linear-gradient(135deg,#1a237e 0%,#0d47a1 50%,#006064 100%);height:64px;display:flex;align-items:center;padding:0 40px;border-bottom:2px solid #1565c0}}
.logo{{color:#64b5f6;font-size:22px;font-weight:bold;letter-spacing:2px}}
.logo span{{color:#ef5350}}
.tag{{margin-left:auto;background:#1b5e20;color:#c8e6c9;padding:6px 18px;border-radius:4px;font-size:13px;letter-spacing:1px}}
.body{{display:flex;flex:1}}
.left{{flex:1;padding:40px 50px;display:flex;flex-direction:column;justify-content:center}}
.section-label{{color:#3fb950;font-size:12px;letter-spacing:3px;text-transform:uppercase;margin-bottom:16px}}
h1{{color:#ffffff;font-size:40px;font-weight:bold;line-height:1.15;margin-bottom:28px}}
h1 span{{color:#3fb950}}
.agents{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px}}
.agent{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:14px 16px}}
.agent-name{{color:#58a6ff;font-size:12px;font-weight:bold;margin-bottom:4px}}
.agent-desc{{color:#8b949e;font-size:11px;line-height:1.5}}
.mcp-note{{background:#0d2818;border:1px solid #1b4332;border-radius:6px;padding:14px 18px;color:#3fb950;font-size:12px;line-height:1.7}}
.right{{width:640px;background:#050a0f;border-left:1px solid #21262d;display:flex;flex-direction:column}}
.r-header{{background:#0d2818;padding:16px 24px;border-bottom:1px solid #1b4332}}
.r-title{{color:#3fb950;font-size:13px;letter-spacing:1px}}
.r-sub{{color:#546e7a;font-size:11px;margin-top:4px}}
.terminal{{flex:1;padding:24px;font-size:12.5px;color:#c9d1d9;line-height:1.7;overflow:hidden;font-family:'DejaVu Sans Mono',monospace}}
.g{{color:#3fb950}}.b{{color:#58a6ff}}.y{{color:#e3b341}}.r{{color:#ef5350}}.dim{{color:#484f58}}
</style></head><body>
<div class="topbar">
  <div class="logo">SIFT<span>Guard</span></div>
  <div style="color:#90caf9;font-size:13px;margin-left:24px">Autonomous DFIR · Multi-Agent Pipeline</div>
  <div class="tag">The Solution</div>
</div>
<div class="body">
  <div class="left">
    <div class="section-label">SIFTGuard Architecture</div>
    <h1>5 AI Agents. 1 command. <span>Full DFIR in minutes.</span></h1>
    <div class="agents">
      <div class="agent"><div class="agent-name">① TriageAgent</div><div class="agent-desc">Classifies threat type, severity, confidence. Selects DFIR playbook.</div></div>
      <div class="agent"><div class="agent-name">② AnalyzerAgent</div><div class="agent-desc">Runs volatility3, evtx_parse, sleuthkit. Extracts IOCs + MITRE techniques.</div></div>
      <div class="agent"><div class="agent-name">③ SelfCorrectionAgent</div><div class="agent-desc">Detects tool failures, applies recovery strategies, retries automatically.</div></div>
      <div class="agent"><div class="agent-name">④ PlannerAgent</div><div class="agent-desc">Generates remediation plan with containment, eradication, recovery actions.</div></div>
      <div class="agent"><div class="agent-name">⑤ ExecutorAgent</div><div class="agent-desc">HITL gate — executes only after human approval. Full audit trail via MCP.</div></div>
    </div>
    <div class="mcp-note">🔌 MCP Server exposes tools: list_evidence · search_playbook · record_finding · audit_trail — every agent action is traceable + cryptographically verifiable</div>
  </div>
  <div class="right">
    <div class="r-header">
      <div class="r-title">user@siftguard — MCP Server initialization</div>
      <div class="r-sub">python main.py — Mon Jun 8 2026</div>
    </div>
    <div class="terminal">
<span class="b">user@siftguard</span><span>:~/siftguard$ </span><span class="g">python main.py</span>

<span class="g">  ✓ SIFTGuard MCP Server — online</span>
<span class="dim">    Tools registered: list_evidence, search_playbook,</span>
<span class="dim">    record_finding, run_tool, audit_trail  (5 tools)</span>

<span class="g">  ✓ Agents initialized:</span>
<span class="dim">    TriageAgent        · groq:llama-3.3-70b-versatile</span>
<span class="dim">    AnalyzerAgent      · forensic replay mode</span>
<span class="dim">    SelfCorrectionAgent · 3 recovery strategies</span>
<span class="dim">    PlannerAgent       · RAG-augmented playbook</span>
<span class="dim">    ExecutorAgent      · HITL gate enforced</span>

<span class="g">  ✓ Evidence artifacts discovered: 4</span>
<span class="dim">    memory/victim.mem           .mem   2.15 GB</span>
<span class="dim">    logs/Security.evtx          .evtx  21.0 MB</span>
<span class="dim">    logs/System.evtx            .evtx  10.5 MB</span>
<span class="dim">    disk/victim-disk.E01        .e01   53.69 GB</span>

<span class="y">  → Beginning 8-stage autonomous investigation...</span>
    </div>
  </div>
</div>
</body></html>"""

# ─── Slide: Architecture ─────────────────────────────────────────────────────
def slide_architecture():
    # We embed the arch diagram PNG via base64
    import base64
    arch_b64 = base64.b64encode(ARCH_PNG.read_bytes()).decode()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;flex-direction:column;overflow:hidden}}
.topbar{{background:linear-gradient(135deg,#1a237e 0%,#0d47a1 50%,#006064 100%);height:64px;display:flex;align-items:center;padding:0 40px;border-bottom:2px solid #1565c0}}
.logo{{color:#64b5f6;font-size:22px;font-weight:bold;letter-spacing:2px}}
.logo span{{color:#ef5350}}
.tag{{margin-left:auto;background:#1565c0;color:#90caf9;padding:6px 18px;border-radius:4px;font-size:13px;letter-spacing:1px}}
.body{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 60px;gap:24px}}
.section-label{{color:#58a6ff;font-size:12px;letter-spacing:3px;text-transform:uppercase}}
h2{{color:#ffffff;font-size:36px;font-weight:bold;text-align:center}}
h2 span{{color:#58a6ff}}
.arch-img{{max-width:1400px;max-height:720px;border-radius:8px;border:1px solid #21262d;box-shadow:0 8px 40px #00000080}}
</style></head><body>
<div class="topbar">
  <div class="logo">SIFT<span>Guard</span></div>
  <div style="color:#90caf9;font-size:13px;margin-left:24px">Autonomous DFIR · Multi-Agent Pipeline</div>
  <div class="tag">System Architecture</div>
</div>
<div class="body">
  <div class="section-label">How SIFTGuard Works</div>
  <h2>MCP Server + <span>5-Agent Pipeline</span> + SIFT Workstation</h2>
  <img class="arch-img" src="data:image/png;base64,{arch_b64}"/>
</div>
</body></html>"""

# ─── Slide: Outro ─────────────────────────────────────────────────────────────
def slide_outro():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden}}
.bg{{position:absolute;width:100%;height:100%;background:radial-gradient(ellipse at 50% 50%,#0d47a118 0%,transparent 70%)}}
.grid{{position:absolute;width:100%;height:100%;background-image:linear-gradient(#1565c008 1px,transparent 1px),linear-gradient(90deg,#1565c008 1px,transparent 1px);background-size:60px 60px}}
.center{{position:relative;text-align:center;width:100%}}
.title{{font-size:72px;font-weight:bold;letter-spacing:-2px}}
.title .sift{{color:#64b5f6}}.title .guard{{color:#ef5350}}
.tagline{{color:#90caf9;font-size:20px;margin-top:16px;letter-spacing:1px}}
.stats{{display:flex;gap:40px;justify-content:center;margin-top:48px}}
.stat{{text-align:center}}
.stat-val{{font-size:48px;font-weight:bold;color:#3fb950}}
.stat-label{{color:#8b949e;font-size:13px;margin-top:6px;letter-spacing:1px}}
.divider{{width:600px;height:1px;background:#21262d;margin:40px auto}}
.links{{display:flex;gap:48px;justify-content:center}}
.link{{color:#58a6ff;font-size:14px;letter-spacing:1px}}
.hackathon{{margin-top:32px;color:#3fb950;font-size:13px;letter-spacing:2px}}
.badge{{display:inline-block;background:#1b5e20;color:#c8e6c9;font-size:12px;letter-spacing:2px;padding:8px 24px;border-radius:3px;margin-top:16px;border:1px solid #2e7d32}}
</style></head><body>
<div class="bg"></div><div class="grid"></div>
<div class="center">
  <div class="title"><span class="sift">SIFT</span><span class="guard">Guard</span></div>
  <div class="tagline">From evidence to report — fully autonomous</div>
  <div class="stats">
    <div class="stat"><div class="stat-val">8</div><div class="stat-label">Pipeline Stages</div></div>
    <div class="stat"><div class="stat-val">5</div><div class="stat-label">AI Agents</div></div>
    <div class="stat"><div class="stat-val">6+</div><div class="stat-label">MITRE Techniques</div></div>
    <div class="stat"><div class="stat-val">100%</div><div class="stat-label">Audit Trail</div></div>
  </div>
  <div class="divider"></div>
  <div class="links">
    <div class="link">github.com/sodiq-code/siftguard</div>
    <div class="link">findevil.devpost.com</div>
    <div class="link">python main.py --help</div>
  </div>
  <div class="hackathon">FIND EVIL! 2026 Hackathon</div>
  <div class="badge">Try it: git clone · pip install -r requirements.txt · python main.py</div>
</div>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BUILD
# ═══════════════════════════════════════════════════════════════════════════════

SEGMENTS = [
    # (name, html_func_or_none, screenshot_key_or_none, badge_label, duration, use_scroll)
    ("00_intro",    slide_intro,         None,                        None,                               9,  False),
    ("01_problem",  slide_problem,       None,                        None,                               14, False),
    ("02_solution", slide_solution,      None,                        None,                               14, False),
    ("03_stage1",   None,  "sc1_banner_stage1.png",   "Stage 1/8 — Evidence Inventory",                 20, True),
    ("04_stage23",  None,  "sc2_triage_playbook.png", "Stage 2-3/8 — AI Triage + Playbook",             22, True),
    ("05_stage4",   None,  "sc3_selfcorrection.png",  "Stage 4/8 — Self-Correction Engine",             22, True),
    ("06_stage56",  None,  "sc4_findings_plan.png",   "Stage 4-5/8 — Findings + Recording",            22, True),
    ("07_stage78",  None,  "sc5_execution.png",       "Stage 6-7/8 — Remediation + HITL Execution",    18, True),
    ("08_audit",    None,  "sc6_complete.png",        "Stage 8/8 — Audit Trail + Report",               18, True),
    ("09_arch",     slide_architecture, None,                         None,                               14, False),
    ("10_outro",    slide_outro,         None,                        None,                               10, False),
]

clips = []
print("Building SIFTGuard demo video v4...")
print(f"  Output: {W}x{H} @ {FPS}fps")
print()

for seg_name, html_fn, shot_file, badge_label, duration, scroll in SEGMENTS:
    png_path = SLIDES / f"{seg_name}.png"
    mp4_path = CLIPS / f"{seg_name}.mp4"

    if shot_file:
        src_png = SHOTS / shot_file
        # Render a framed version at 1920×1080 wrapping the terminal screenshot
        print(f"  [frame] {seg_name} ← {shot_file}")

        # Load the terminal screenshot as a framed slide
        import base64
        img_b64 = base64.b64encode(src_png.read_bytes()).decode()

        frame_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0a0e17;font-family:'DejaVu Sans Mono','Courier New',monospace;display:flex;flex-direction:column;overflow:hidden}}
.topbar{{background:linear-gradient(135deg,#1a237e 0%,#0d47a1 50%,#006064 100%);height:56px;display:flex;align-items:center;padding:0 36px;border-bottom:2px solid #1565c0;flex-shrink:0}}
.logo{{color:#64b5f6;font-size:20px;font-weight:bold;letter-spacing:2px}}
.logo span{{color:#ef5350}}
.tag{{margin-left:auto;background:#1565c0;color:#90caf9;padding:5px 16px;border-radius:4px;font-size:12px;letter-spacing:1px}}
.body{{flex:1;display:flex;align-items:stretch;justify-content:stretch;padding:16px 24px 20px 24px;overflow:hidden}}
.term-frame{{width:100%;height:100%;object-fit:contain;object-position:top left;border-radius:8px;box-shadow:0 8px 48px #00000099;border:1px solid #30363d}}
</style></head><body>
<div class="topbar">
  <div class="logo">SIFT<span>Guard</span></div>
  <div style="color:#90caf9;font-size:12px;margin-left:20px">Autonomous DFIR · Multi-Agent Pipeline · Real Pipeline Output</div>
  <div class="tag">{badge_label}</div>
</div>
<div class="body">
  <img class="term-frame" src="data:image/png;base64,{img_b64}"/>
</div>
</body></html>"""

        html_file = SLIDES / f"{seg_name}.html"
        html_file.write_text(frame_html, encoding="utf-8")
        ok = chrome_render(str(html_file), str(png_path))
    else:
        print(f"  [slide] {seg_name}")
        html = html_fn()
        html_file = SLIDES / f"{seg_name}.html"
        html_file.write_text(html, encoding="utf-8")
        ok = chrome_render(str(html_file), str(png_path))

    if not ok or not png_path.exists():
        print(f"  ✗ render failed: {seg_name}")
        continue

    # Generate clip
    if scroll and shot_file:
        result = scroll_png_clip(png_path, mp4_path, duration=duration)
    else:
        result = png_to_clip(png_path, mp4_path, duration=duration)

    if result:
        print(f"  ✓ {seg_name}.mp4 ({duration}s)")
        clips.append(str(mp4_path))
    else:
        print(f"  ✗ clip failed: {seg_name}")

# ─── Stitch all clips ─────────────────────────────────────────────────────────
print()
print(f"Stitching {len(clips)} clips...")

concat_file = Path("/tmp/demo_concat.txt")
with open(concat_file, "w") as f:
    for c in clips:
        f.write(f"file '{c}'\n")

final_out = OUT_DIR / "siftguard_demo_v4.mp4"
stitch_cmd = [
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", str(concat_file),
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-preset", "medium", "-crf", "18",
    "-movflags", "+faststart",
    str(final_out)
]
result = subprocess.run(stitch_cmd, capture_output=True, text=True)
if final_out.exists():
    size_mb = final_out.stat().st_size / 1e6
    print(f"\n✓ Done: {final_out}")
    print(f"  Size: {size_mb:.1f} MB")
    # Print duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(final_out)],
        capture_output=True, text=True
    )
    dur = float(probe.stdout.strip()) if probe.stdout.strip() else 0
    print(f"  Duration: {int(dur//60)}m {int(dur%60)}s")
else:
    print(f"✗ Stitch failed:\n{result.stderr[-2000:]}")
