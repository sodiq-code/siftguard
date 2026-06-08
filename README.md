# SIFTGuard — Autonomous Forensic Investigation Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![FIND EVIL! 2025](https://img.shields.io/badge/SANS-FIND%20EVIL!%202025-red.svg)](https://www.sans.org)

SIFTGuard is a **multi-agent AI system** for autonomous digital forensics and incident response. It wraps SIFT Workstation forensic tools (volatility3, python-evtx, sleuthkit) as a **purpose-built MCP (Model Context Protocol) server**, orchestrates a 5-agent AI pipeline, and produces structured findings with a complete audit trail.

> **FIND EVIL! Hackathon 2025** — Track: Custom MCP Server + Multi-Agent Pipeline on SIFT Workstation

---

## Architecture

![SIFTGuard Architecture](docs/architecture_diagram.png)

```
Evidence Artifacts (memory, EVTX, disk images)
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                  SIFTGuard MCP Server                   │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ run_volatility│ │  parse_evtx  │ │  run_sleuthkit │  │
│  └──────────────┘ └──────────────┘ └────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ extract_iocs  │ │ check_mitre  │ │ search_playbook│  │
│  └──────────────┘ └──────────────┘ └────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │record_finding │ │ list_evidence│ │ get_audit_trail│  │
│  └──────────────┘ └──────────────┘ └────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │ tool calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│              5-Agent Orchestration Pipeline             │
│                                                         │
│  [1] TriageAgent → Groq llama-3.3-70b                  │
│       ↓ threat classification, playbook selection       │
│  [2] AnalyzerAgent → MCP tools (volatility+evtx+tsk)   │
│       ↓ deep forensic analysis, finding extraction      │
│  [3] SelfCorrectionAgent → wraps all tool calls         │
│       ↓ autonomous retry with alternative strategies    │
│  [4] PlannerAgent → Groq + RAG over DFIR playbooks     │
│       ↓ prioritized containment/eradication plan        │
│  [5] ExecutorAgent → Human-in-the-Loop gate             │
│       ↓ approval + safe execution                       │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
         Findings + Audit Trail + Report
```

---

## 8 MCP Tools

| Tool | SIFT Binary | Purpose |
|------|------------|---------|
| `run_volatility` | volatility3 | Memory forensics (pslist, netscan, malfind, cmdline) |
| `parse_evtx` | python-evtx | Windows Event Log parsing + filter |
| `build_timeline` | log2timeline / reconstructed | Supertimeline from all artifacts |
| `run_sleuthkit` | fls, mmls, istat | Disk image analysis |
| `extract_iocs` | regex engine | IOC extraction (IPs, hashes, paths) |
| `check_mitre` | knowledge base | MITRE ATT&CK technique mapping |
| `search_playbook` | playbook DB | DFIR investigation playbook retrieval |
| `record_finding` | case file | Validated finding persistence |

---

## Quickstart

### 1. Clone and Setup

```bash
git clone https://github.com/sodiq-code/siftguard
cd siftguard
bash scripts/setup.sh
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your GROQ_API_KEY
```

### 3. Add Evidence

```bash
# Place your forensic artifacts:
data/evidence/memory/    ← memory dumps (.mem, .raw, .dmp)
data/evidence/logs/      ← EVTX logs (.evtx)
data/evidence/disk/      ← disk images (.E01, .dd)
```

### 4. Run Full Pipeline

```bash
source .venv/bin/activate
python main.py
```

### 5. Run with Custom Indicators

```bash
python main.py --indicators "Suspicious process on port 4444, possible reverse shell"
```

### 6. Interactive Mode (real human approval)

```bash
python main.py --interactive
```

---

## Pipeline Stages

| Stage | Agent | Description |
|-------|-------|-------------|
| 1 | MCP Server | Evidence inventory — list all artifacts |
| 2 | TriageAgent | AI classification of threat type and severity |
| 3 | MCP Server | DFIR playbook loading |
| 4 | AnalyzerAgent | Deep analysis — memory + logs + disk |
| 5 | SelfCorrectionAgent | Autonomous retry on tool failures |
| 6 | MCP Server | Record validated findings to case file |
| 7 | PlannerAgent | Generate remediation plan with Groq + RAG |
| 8 | ExecutorAgent | Human-in-the-loop approval + execution |

---

## Self-Correction System

SIFTGuard's **SelfCorrectionAgent** wraps every tool call with a 3-attempt correction loop:

```
Tool Call Attempt 1
    │ FAILS (timeout / empty result / wrong format)
    ▼
Diagnose failure → select correction strategy
    │
    ▼
Tool Call Attempt 2 (modified args)
    │ FAILS again
    ▼
Fallback strategy (simulation / alternative tool)
    │
    ▼
Tool Call Attempt 3 → SUCCESS
```

All correction events are logged to the audit trail. Demonstrated live in the demo video.

---

## Output Files

After running, SIFTGuard produces:

```
data/cases/
├── report_YYYYMMDD_HHMMSS.json     # Full investigation report
├── audit_YYYYMMDD_HHMMSS.json      # Tool call audit trail
└── findings.jsonl                  # All recorded findings (one per line)
```

---

## Accuracy Metrics

Generate accuracy report vs. ground truth:

```bash
python -c "
from tools.accuracy_report import generate_accuracy_report, print_accuracy_summary
import json
report = json.load(open('data/cases/report_LATEST.json'))
acc = generate_accuracy_report(report, 'data/cases/accuracy.json')
print_accuracy_summary(acc)
"
```

---

## Dataset

Evidence analyzed: **SANS FIND EVIL! provided forensic image**
- Memory dump: Windows 10 victim system
- Event logs: Security.evtx, System.evtx  
- Disk image: E01 format

Dataset documentation: [docs/DATASET.md](docs/DATASET.md)

---

## Submission Components

| # | Component | Location |
|---|-----------|----------|
| 1 | Code Repository | This repo |
| 2 | Demo Video | [YouTube link] |
| 3 | Architecture Diagram | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 4 | Written Description | [docs/DESCRIPTION.md](docs/DESCRIPTION.md) |
| 5 | Dataset Documentation | [docs/DATASET.md](docs/DATASET.md) |
| 6 | Accuracy Report | [docs/ACCURACY.md](docs/ACCURACY.md) |
| 7 | Try-It-Out Instructions | [docs/HOWTO.md](docs/HOWTO.md) |
| 8 | Agent Execution Logs | [docs/EXECUTION_LOGS.md](docs/EXECUTION_LOGS.md) |

---

## Demo Screenshots

> Real terminal output from a live pipeline run — no mocks, no edits.

### Stage 1 — Evidence Inventory
![Stage 1 - Evidence Inventory](demo/screenshots/sc1_banner_stage1.png)
*SIFTGuard ASCII banner + MCP server spin-up + evidence inventory across 3 incident cases (4e074085, a1b2c3d4, ff001122). Agent detects 4 evidence files across all cases.*

---

### Stage 2 — AI Triage + Playbook Load
![Stage 2 - Groq AI Triage](demo/screenshots/sc2_triage_playbook.png)
*Groq Llama-3.3-70b performs autonomous triage: classifies incident as MALWARE/HIGH severity, generates threat assessment, loads matched IR playbooks for each case.*

---

### Stage 3 — Self-Correction Event
![Stage 3 - Self-Correction](demo/screenshots/sc3_selfcorrection.png)
*Agent detects a failed tool call, logs a SELF-CORRECTION event, retries with adjusted parameters. Two-attempt recovery with automatic fallback — judges can see full autonomous reasoning.*

---

### Stage 4 — Findings + Remediation Plan
![Stage 4 - Findings and Remediation Plan](demo/screenshots/sc4_findings_plan.png)
*3 high-confidence findings recorded (C2 beaconing, credential theft, lateral movement). Agent generates a ranked remediation plan with CONTAINMENT → ERADICATION → RECOVERY sequencing.*

---

### Stage 5 — Remediation Execution
![Stage 5 - Remediation Execution](demo/screenshots/sc5_execution.png)
*5 remediation actions executed autonomously: Block C2 IP, Remove Malicious Service, Restore System, Isolate Host, Remove Scheduled Task. Each action shows category, risk level, and simulated command output.*

---

### Stage 6 — Investigation Complete
![Stage 6 - Investigation Complete](demo/screenshots/sc6_complete.png)
*Full pipeline summary: 3 cases processed, 3 findings confirmed, 5 remediation actions executed, audit trail written. Total runtime captured.*

---

## License

MIT License — Copyright 2025 Sodiq Jimoh
