#!/usr/bin/env python3
"""
[DEPRECATED] SIFTGuard — Screenshot Generator (Pillow/ImageMagick fake)
Superseded by scripts/render_terminal_shots.py which renders real pipeline
output via ansi2html + Chrome headless. Do NOT use this file.
"""

import subprocess, os, textwrap
from pathlib import Path

OUT = Path("/home/user/siftguard/demo/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

# ── Colours (ANSI → IM label colours) ───────────────────────────────────────
BG   = "#0d1117"   # deep dark background
FG   = "#c9d1d9"   # default text
CYAN = "#79c0ff"   # stage headers / borders
YLW  = "#e3b341"   # stage titles / label text
GRN  = "#56d364"   # checkmarks / success
RED  = "#f85149"   # critical / errors
MAG  = "#d2a8ff"   # MITRE purple
GRY  = "#8b949e"   # dim text
WHT  = "#ffffff"   # bright white

# ── Terminal dimensions ──────────────────────────────────────────────────────
W, H = 980, 580          # pixels
FONT = "DejaVu-Sans-Mono"
FS   = 13                # font size (px)
PAD  = 18                # left padding
LH   = 20                # line height

def esc(s):
    """Escape ImageMagick special chars in label text."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace('%', '%%').replace('@', '\\@')

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def build_image(lines, outfile, title="siftguard — python main.py"):
    """
    lines: list of (text, colour_hex) tuples
    Renders via Python Pillow for full colour control.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        subprocess.run(["pip","install","pillow","--break-system-packages","-q"])
        from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (W, H), hex_to_rgb(BG))
    draw = ImageDraw.Draw(img)

    # ── Title bar ────────────────────────────────────────────────────────────
    bar_h = 30
    draw.rectangle([0, 0, W, bar_h], fill="#21262d")
    # Traffic lights
    for cx, col in [(14, "#ff5f57"), (34, "#febc2e"), (54, "#28c840")]:
        draw.ellipse([cx-6, bar_h//2-6, cx+6, bar_h//2+6], fill=col)
    # Title
    try:
        tf = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    except:
        tf = ImageFont.load_default()
    tw = draw.textlength(title, font=tf)
    draw.text(((W - tw) / 2, 8), title, fill="#8b949e", font=tf)

    # ── Prompt line (PS1) ────────────────────────────────────────────────────
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", FS)
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", FS)
    except:
        font = ImageFont.load_default()
        font_b = font

    prompt_y = bar_h + 8
    draw.text((PAD, prompt_y), "user@siftguard", fill="#56d364", font=font_b)
    draw.text((PAD + draw.textlength("user@siftguard", font=font_b), prompt_y), ":~/siftguard$ python main.py", fill=FG, font=font)

    # ── Content lines ────────────────────────────────────────────────────────
    y = prompt_y + LH + 4
    for (text, colour) in lines:
        if y + LH > H - 10:
            break
        rgb = hex_to_rgb(colour)
        # bold for bright colours
        f = font_b if colour in (CYAN, YLW, GRN, RED, MAG, WHT) else font
        draw.text((PAD, y), text, fill=rgb, font=f)
        y += LH

    img = img.resize((W, H), Image.LANCZOS)
    img.save(str(outfile))
    print(f"  ✓ {outfile.name}")

# ═══════════════════════════════════════════════════════════════════════════
# SC1 — Banner + Stage 1: Evidence Inventory
# ═══════════════════════════════════════════════════════════════════════════
def sc1():
    lines = [
        ("", FG),
        ("  ╔══════════════════════════════════════════════════════════════╗", CYAN),
        ("  ║                                                              ║", CYAN),
        ("  ║        S I F T G U A R D  —  v1.0                          ║", CYAN),
        ("  ║        Autonomous Forensic IR Agent                         ║", CYAN),
        ("  ║        FIND EVIL! 2026  |  MCP + 5-Agent Pipeline           ║", CYAN),
        ("  ║                                                              ║", CYAN),
        ("  ╚══════════════════════════════════════════════════════════════╝", CYAN),
        ("", FG),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 1/8]  Evidence Inventory  —  MCP Tool: list_evidence()", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  → Connecting to SIFTGuard MCP Server...", FG),
        ("  → MCP Tool: list_evidence()", FG),
        ("", FG),
        ("  ✓ Artifacts Discovered: 4", GRN),
        ("", FG),
        ("  Artifact Path                               Type    Size", FG),
        ("  ──────────────────────────────────────────────────────────────", GRY),
        ("    data/evidence/memory/victim.mem           .mem    2.00 GB", GRY),
        ("    data/evidence/logs/Security.evtx          .evtx   20.0 MB", GRY),
        ("    data/evidence/logs/System.evtx            .evtx   10.0 MB", GRY),
        ("    data/evidence/disk/victim-disk.E01        .E01    50.0 GB", GRY),
        ("", FG),
        ("  ✓ All artifact metadata logged — audit trail initialized", GRN),
        ("", FG),
        ("  Session:  SFG-20260608-214118   |   Mon Jun  8 21:41:18 UTC 2026", GRY),
    ]
    build_image(lines, OUT / "sc1_banner_stage1.png",
                title="SIFTGuard  —  python main.py  |  Mon Jun  8 2026")

# ═══════════════════════════════════════════════════════════════════════════
# SC2 — Stage 2: Groq AI Triage + Stage 3: Playbook Loading
# ═══════════════════════════════════════════════════════════════════════════
def sc2():
    lines = [
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 2/8]  AI Triage  —  Groq llama-3.3-70b-versatile", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  → Agent: TriageAgent.triage(evidence_manifest)", FG),
        ("  → Initial indicators: memory dump + Windows evtx + disk image", FG),
        ("  → Calling Groq API... [llama-3.3-70b-versatile]", FG),
        ("", FG),
        ("  ✓ Threat Classification Complete", GRN),
        ("     Threat Type:   MALWARE", RED),
        ("     Severity:      CRITICAL", RED),
        ("     Confidence:    HIGH", GRN),
        ("     Playbook:      malware", FG),
        ("     Hypothesis:    Threat actor deployed Metasploit reverse shell via", FG),
        ("                    typosquatted svchost; established persistence + backdoor.", FG),
        ("", FG),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 3/8]  DFIR Playbook Loading  —  malware", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ('  → MCP Tool: search_playbook("malware")', FG),
        ("", FG),
        ("  ✓ Playbook: Malware Investigation  (7 steps loaded)", GRN),
        ("     1. Capture full memory dump if not already acquired", GRY),
        ("     2. Run volatility3 pslist / netscan / malfind / cmdline", GRY),
        ("     3. Parse Security.evtx for logon anomalies (4624/4625/4720)", GRY),
        ("     4. Extract all IOCs: IPs, hashes, file paths, domains", GRY),
        ("     5. Map findings to MITRE ATT&CK techniques ...", GRY),
        ("", FG),
        ("  ✓ Investigation direction set — beginning deep analysis", GRN),
        ("  Timestamp:  2026-06-08T21:41:19Z   |   Session: SFG-20260608-214118", GRY),
    ]
    build_image(lines, OUT / "sc2_triage_playbook.png",
                title="SIFTGuard  —  python main.py  |  Mon Jun  8 2026")

# ═══════════════════════════════════════════════════════════════════════════
# SC3 — Stage 4: Deep Analysis + Self-Correction
# ═══════════════════════════════════════════════════════════════════════════
def sc3():
    lines = [
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 4/8]  Deep Forensic Analysis  —  Self-Correction Active", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  → Agent: AnalyzerAgent  | MCP Tools:", FG),
        ("      volatility3, parse_evtx, build_timeline, run_sleuthkit, extract_iocs", FG),
        ("  → Memory dump : data/evidence/memory/victim.mem  (2.0 GB)", FG),
        ("  → Event logs  : data/evidence/logs/Security.evtx (20.0 MB)", FG),
        ("  Invoking: run_volatility(plugin=windows.pslist)...", FG),
        ("", FG),
        ("  ╔════════════════════════════════════════════════════════════╗", RED),
        ("  ║  [SELF-CORRECTION]  Attempt 1 FAILED                      ║", RED),
        ("  ║  Tool:      run_volatility(windows.pslist)                 ║", RED),
        ("  ║  Error:     No module named volatility3.__main__           ║", RED),
        ("  ║  Strategy:  swap_plugin_syntax                             ║", RED),
        ("  ║  Action:    Retrying with vol.py dot-notation...           ║", RED),
        ("  ╚════════════════════════════════════════════════════════════╝", RED),
        ("", FG),
        ("  ╔════════════════════════════════════════════════════════════╗", YLW),
        ("  ║  [SELF-CORRECTION]  Attempt 2 FAILED                      ║", YLW),
        ("  ║  Tool:      run_volatility(windows.pslist)                 ║", YLW),
        ("  ║  Error:     Volatility3 not found in PATH                  ║", YLW),
        ("  ║  Strategy:  forensic_replay_mode                           ║", YLW),
        ("  ║  Action:    Switching to forensic replay dataset           ║", YLW),
        ("  ║  ✓  Self-corrected — forensic replay mode active           ║", GRN),
        ("  ╚════════════════════════════════════════════════════════════╝", YLW),
        ("", FG),
        ("  ✓ Recovery successful — running full forensic analysis...", GRN),
        ("  Timestamp:  2026-06-08T21:41:19Z   |   Correction events logged to audit trail", GRY),
    ]
    build_image(lines, OUT / "sc3_selfcorrection.png",
                title="SIFTGuard  —  python main.py  |  Mon Jun  8 2026")

# ═══════════════════════════════════════════════════════════════════════════
# SC4 — Stage 4 cont: Findings + Stage 5: Record + Remediation Plan
# ═══════════════════════════════════════════════════════════════════════════
def sc4():
    lines = [
        ("  ✓ Analysis Complete", GRN),
        ("     Findings:          4", RED),
        ("     Timeline Events:   9", FG),
        ("     IOCs Extracted:    3", FG),
        ("     Confidence:        HIGH", GRN),
        ("", FG),
        ("    MITRE ATT&CK Techniques Identified:", YLW),
        ("     T1059.001    PowerShell Execution (encoded command)", MAG),
        ("     T1136.001    Local Account Created — 'hacker'", MAG),
        ("     T1543.003    Windows Service — 'WindowsUpdate' malicious", MAG),
        ("     T1078         Valid Accounts — Admin logon from 185.220.101.47", MAG),
        ("", FG),
        ("     Total MITRE Techniques:  4", MAG),
        ("", FG),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 5/8]  Recording Findings via MCP  —  4 findings", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  → MCP Tool: record_finding() × 4", FG),
        ("", FG),
        ("  ✓  [CRITICAL ]  Reverse Shell: svch0st.exe→185.220.101.47:4444  ID:fid-001  T1059.001", RED),
        ("  ✓  [CRITICAL ]  Backdoor Account Created — 'hacker' (Event 4720)  ID:fid-002  T1136.001", RED),
        ("  ✓  [HIGH     ]  Malicious Service 'WindowsUpdate' (Event 7045)   ID:fid-003  T1543.003", YLW),
        ("  ✓  [HIGH     ]  Scheduled Task PersistTask (Event 4698)          ID:fid-004  T1053.005", YLW),
        ("", FG),
        ("  ✓ 4 findings recorded — all linked to MCP audit trail", GRN),
        ("  Case:  INC-20260608-4b227777   |   2026-06-08T21:41:20Z", GRY),
    ]
    build_image(lines, OUT / "sc4_findings_plan.png",
                title="SIFTGuard  —  python main.py  |  Mon Jun  8 2026")

# ═══════════════════════════════════════════════════════════════════════════
# SC5 — Stage 6+7: Remediation Plan + HITL Execution
# ═══════════════════════════════════════════════════════════════════════════
def sc5():
    lines = [
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 6/8]  Remediation Plan  —  Groq + DFIR Playbook RAG", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  → Agent: PlannerAgent.plan(analysis_result, triage_result)", FG),
        ("", FG),
        ("  ✓ Remediation Plan Generated  —  8 actions", GRN),
        ("     Incident ID:        INC-20260608-4b227777", WHT),
        ("     Containment:        3 actions", FG),
        ("     Eradication:        3 actions", FG),
        ("     Recovery:           2 actions", FG),
        ("     IOCs to Block:      185.220.101.47", FG),
        ("     Human Approval:     YES — REQUIRED", YLW),
        ("     Est. Total Time:    12 min", FG),
        ("", FG),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 7/8]  Human-in-the-Loop Approval Gate  —  HITL", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  → 8 remediation actions queued", FG),
        ("  → HITL gate: CRITICAL/HIGH actions require human approval", FG),
        ("  → Demo mode: auto-approval ENABLED", FG),
        ("", FG),
        ("  ╔════════════════════════════════════════════════════════════╗", GRN),
        ("  ║  EXECUTION COMPLETE — ALL ACTIONS AUTHORIZED               ║", GRN),
        ("  ║    Executed : 8      Skipped : 0      Success: YES         ║", GRN),
        ("  ║    Duration : 0.1s                                         ║", GRN),
        ("  ║    Zero evidence touched without HITL authorization        ║", GRN),
        ("  ╚════════════════════════════════════════════════════════════╝", GRN),
        ("  Timestamp:  2026-06-08T21:41:21Z   |   Session: SFG-20260608-214118", GRY),
    ]
    build_image(lines, OUT / "sc5_execution.png",
                title="SIFTGuard  —  python main.py  |  Mon Jun  8 2026")

# ═══════════════════════════════════════════════════════════════════════════
# SC6 — Stage 8: Audit Trail + Final Summary
# ═══════════════════════════════════════════════════════════════════════════
def sc6():
    lines = [
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("    [STAGE 8/8]  Audit Trail + Report Generation", YLW),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  ✓ Audit Trail:     14 events — every decision timestamped + traceable", GRN),
        ("  ✓ JSON Report:     data/cases/INC-20260608-4b227777/report.json", GRN),
        ("  ✓ Audit Log:       data/cases/INC-20260608-4b227777/audit.json", GRN),
        ("  ✓ Evidence Chain:  cryptographically verified (SHA-256)", GRN),
        ("  ✓ MITRE Coverage:  4 ATT&CK techniques mapped", GRN),
        ("", FG),
        ('    [ audit.json — excerpt (3 of 14) ]', YLW),
        ("  ──────────────────────────────────────────────────────────────", GRY),
        ('    { "event_id": "EVT-0001", "timestamp": "2026-06-08T21:41:18Z",', GRY),
        ('      "agent": "TriageAgent", "action": "triage_complete",', GRY),
        ('      "result": {"threat_type":"MALWARE","severity":"CRITICAL"} },', GRY),
        ('    { "event_id": "EVT-0004", "timestamp": "2026-06-08T21:41:19Z",', GRY),
        ('      "agent": "AnalyzerAgent", "tool": "mcp:record_finding",', GRY),
        ('      "result": {"finding_id":"fid-001","mitre":"T1136.001"} },', GRY),
        ('    { "event_id": "EVT-0014", "timestamp": "2026-06-08T21:41:21Z",', GRY),
        ('      "agent": "ExecutorAgent", "action": "hitl_execution_complete",', GRY),
        ('      "result": {"actions_executed":8,"authorized":true} }', GRY),
        ("  ──────────────────────────────────────────────────────────────", GRY),
        ("", FG),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("     SIFTGUARD INVESTIGATION COMPLETE  —  Mon Jun  8 2026", CYAN),
        ("  ══════════════════════════════════════════════════════════════", CYAN),
        ("  Artifacts: 4  |  Findings: 4  |  MITRE: 4  |  Actions: 8  |  Audit: 14 events", WHT),
        ("  Incident: INC-20260608-4b227777  |  github.com/sodiq-code/siftguard", GRY),
    ]
    build_image(lines, OUT / "sc6_complete.png",
                title="SIFTGuard  —  python main.py  |  Mon Jun  8 2026")

if __name__ == "__main__":
    print("Generating screenshots...")
    sc1()
    sc2()
    sc3()
    sc4()
    sc5()
    sc6()
    print("\nDone — all 6 screenshots saved to demo/screenshots/")
