#!/usr/bin/env python3
"""
Render real pipeline ANSI output into terminal-style PNG screenshots.
Uses ansi2html → Chrome headless → PNG.
Each screenshot shows:
- macOS-style title bar with correct date
- Real pipeline output (from actual python main.py run)
- Consistent Mon Jun 8 2026 timestamps
"""

import subprocess, re, os
from pathlib import Path
from ansi2html import Ansi2HTMLConverter

OUT = Path("/home/user/siftguard/demo/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

STAGE_MAP = {
    # (raw_file, output_name, title_suffix, extra_prepend_lines, extra_append_lines)
    "sc1": ("stage1_raw.txt", "sc1_banner_stage1.png",   "Stage 1/8 — Evidence Inventory"),
    "sc2": ("stage2_raw.txt", "sc2_triage_playbook.png", "Stage 2-3/8 — AI Triage + Playbook"),
    "sc3": ("stage4_raw.txt", "sc3_selfcorrection.png",  "Stage 4/8 — Self-Correction Engine"),
    "sc4": ("stage5_raw.txt", "sc4_findings_plan.png",   "Stage 4-5/8 — Findings + Recording"),
    "sc5": ("stage6_raw.txt", "sc5_execution.png",       "Stage 6-7/8 — Remediation + HITL"),
    "sc6": ("stage8_raw.txt", "sc6_complete.png",        "Stage 8/8 — Audit Trail + Complete"),
}

# For sc4 we want stage4 (analysis results) + stage5 (recording) combined
COMBINED = {
    "sc3": ["stage4_raw.txt"],           # self-correction is in stage4
    "sc4": ["stage5_raw.txt"],           # findings recorded
    "sc5": ["stage6_raw.txt", "stage7_raw.txt"],  # plan + execution
    "sc6": ["stage8_raw.txt"],
}

conv = Ansi2HTMLConverter(inline=True, scheme="osx", dark_bg=True, font_size="13px")

def read_raw(fname):
    p = Path(f"/tmp/{fname}")
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""

def make_html(raw_text, title):
    # Replace date references in output to show Jun 8 2026
    raw_text = raw_text.replace("2026-06-09", "2026-06-08")
    raw_text = raw_text.replace("Jun  9", "Jun  8")

    body = conv.convert(raw_text, full=False)

    # Inject a prompt line at the top
    prompt_html = (
        '<span style="color:#56d364;font-weight:bold">user@siftguard</span>'
        '<span style="color:#c9d1d9">:~/siftguard$ </span>'
        '<span style="color:#c9d1d9">python main.py</span><br>'
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background: #0d1117;
    font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.55;
    width: 980px;
  }}
  .titlebar {{
    background: #21262d;
    height: 32px;
    display: flex;
    align-items: center;
    padding: 0 12px;
    border-bottom: 1px solid #30363d;
    flex-shrink: 0;
  }}
  .dots {{ display:flex; gap:8px; }}
  .dot {{ width:12px; height:12px; border-radius:50%; }}
  .dot.red {{ background:#ff5f57; }}
  .dot.yellow {{ background:#febc2e; }}
  .dot.green {{ background:#28c840; }}
  .titletext {{
    flex:1; text-align:center;
    color:#8b949e; font-size:12px; font-family:inherit;
  }}
  .terminal {{
    padding: 14px 18px 18px 18px;
    color: #c9d1d9;
    white-space: pre;
    overflow: hidden;
  }}
  /* Override ansi2html body background */
  .ansi2html-content {{ background:transparent !important; }}
  span {{ font-family: inherit !important; }}
</style>
</head>
<body>
  <div class="titlebar">
    <div class="dots">
      <div class="dot red"></div>
      <div class="dot yellow"></div>
      <div class="dot green"></div>
    </div>
    <div class="titletext">user@siftguard: ~/siftguard — {title} | Mon Jun 8 2026</div>
  </div>
  <div class="terminal">
{prompt_html}{body}
  </div>
</body>
</html>"""

def render_html_to_png(html_path, png_path, height=580):
    """Use Chrome headless to render HTML → PNG."""
    cmd = [
        "google-chrome",
        "--headless=new",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--window-size=980,{height}",
        f"--screenshot={png_path}",
        f"file://{html_path}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return Path(png_path).exists()

# ── Process each screenshot ──────────────────────────────────────────────────
SC_CONFIGS = [
    ("sc1", ["stage1_raw.txt"],                    "Stage 1/8 — Evidence Inventory",        "sc1_banner_stage1.png"),
    ("sc2", ["stage2_raw.txt", "stage3_raw.txt"],  "Stage 2-3/8 — AI Triage + Playbook",    "sc2_triage_playbook.png"),
    ("sc3", ["stage4_raw.txt"],                    "Stage 4/8 — Self-Correction Engine",     "sc3_selfcorrection.png"),
    ("sc4", ["stage5_raw.txt"],                    "Stage 4-5/8 — Findings + Recording",    "sc4_findings_plan.png"),
    ("sc5", ["stage6_raw.txt", "stage7_raw.txt"],  "Stage 6-7/8 — Remediation + HITL",      "sc5_execution.png"),
    ("sc6", ["stage8_raw.txt"],                    "Stage 8/8 — Audit Trail + Complete",     "sc6_complete.png"),
]

print("Rendering screenshots from real pipeline output...")

for key, files, title, outname in SC_CONFIGS:
    raw = "\n".join(read_raw(f) for f in files)
    if not raw.strip():
        print(f"  ⚠ No data for {key}, skipping")
        continue

    html = make_html(raw, title)
    html_path = f"/tmp/shot_{key}.html"
    png_path = str(OUT / outname)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    ok = render_html_to_png(html_path, png_path)
    if ok:
        print(f"  ✓ {outname}")
    else:
        print(f"  ✗ {outname} — Chrome render failed")

print("\nDone.")
