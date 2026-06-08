# SIFTGuard — Try-It-Out Instructions

## Quick Start (5 minutes)

### Prerequisites

- Python 3.10+
- Git
- A Groq API key (free at [console.groq.com](https://console.groq.com))

### 1. Clone the Repository

```bash
git clone https://github.com/sodiq-code/siftguard.git
cd siftguard
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Key

```bash
cp .env.example .env
# Edit .env and set your Groq API key:
# GROQ_API_KEY=gsk_your_key_here
```

### 5. Run the Demo

```bash
python main.py
```

That's it. The full 8-stage pipeline runs automatically in ~5 seconds.

---

## What You'll See

```
[STAGE 1/8] Evidence Inventory      ← Discovers forensic artifacts
[STAGE 2/8] AI Triage               ← Groq LLM classifies the incident
[STAGE 3/8] DFIR Playbook Loading   ← Selects IR strategy
[STAGE 4/8] Deep Forensic Analysis  ← Memory, logs, disk analysis
[STAGE 5/8] Recording Findings      ← MCP server persists findings
[STAGE 6/8] Remediation Planning    ← AI generates containment plan
[STAGE 7/8] Human Approval          ← HITL gate (auto-approved in demo)
[STAGE 8/8] Report Generation       ← JSON report + audit trail
```

Output files are saved to `data/cases/`:
- `report_<session_id>.json` — full investigation report
- `audit_<session_id>.json` — immutable audit trail with self-correction log

---

## Running with Real Evidence

1. Place evidence in `data/evidence/`:
   ```
   data/evidence/memory/victim.mem
   data/evidence/logs/Security.evtx
   data/evidence/disk/victim-disk.E01
   ```

2. Ensure SIFT tools are available (or install on SIFT Workstation):
   ```bash
   # Volatility3
   pip install volatility3
   
   # Sleuthkit
   sudo apt install sleuthkit
   
   # python-evtx
   pip install python-evtx
   ```

3. Run normally:
   ```bash
   python main.py
   ```

SIFTGuard detects real evidence and uses live analysis. No code changes needed.

---

## Running the MCP Server Standalone

SIFTGuard includes a standalone MCP server that exposes all 10 forensic tools over SSE transport:

```bash
python -m mcp_server.server
# Server starts at http://localhost:8765
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `list_evidence` | Discover forensic artifacts in evidence directory |
| `run_volatility` | Execute Volatility3 memory analysis plugins |
| `parse_evtx` | Parse Windows Event Log files |
| `run_sleuthkit` | Run Sleuthkit filesystem analysis |
| `extract_iocs` | Extract IPs, domains, hashes from raw text |
| `search_playbook` | Query DFIR playbook knowledge base |
| `record_finding` | Persist a forensic finding (MCP resource) |
| `query_findings` | Retrieve recorded findings |
| `generate_timeline` | Build chronological attack timeline |
| `build_report` | Compile full investigation report |

---

## Human-in-the-Loop (HITL) Mode

To require real human approval before executing remediation actions:

```bash
# In .env:
DEMO_MODE=false
APPROVAL_TIMEOUT=300    # 5 minutes to approve/deny
```

When running, the executor will pause and prompt:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[APPROVAL REQUIRED] Block C2 IP
Risk: HIGH
Approve this action? [y/n]:
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Required. Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | LLM model for triage + planning |
| `EVIDENCE_DIR` | `./data/evidence` | Path to forensic evidence |
| `CASE_DIR` | `./data/cases` | Output directory for reports |
| `DEMO_MODE` | `true` | Auto-approve remediation actions |
| `APPROVAL_TIMEOUT` | `0` | Seconds to wait for human approval |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_RETRY_ATTEMPTS` | `3` | Self-correction retry limit |

---

## Running Tests

```bash
# Quick smoke test (no API key needed)
python -c "from mcp_server.server import list_evidence; print(list_evidence())"

# Full pipeline test
python main.py

# Accuracy report
python tools/accuracy_report.py
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: groq` | Run `pip install -r requirements.txt` |
| `AuthenticationError: Invalid API Key` | Set correct `GROQ_API_KEY` in `.env` |
| Volatility3 fails | Expected — pipeline self-corrects and uses simulation |
| No output in `data/cases/` | Check write permissions on `data/` directory |
| `JSONDecodeError` from Groq | Transient; re-run — LLM occasionally malforms JSON |

---

## Requirements

```
groq>=0.9.0
mcp>=1.0.0
python-dotenv>=1.0.0
structlog>=24.0.0
pydantic>=2.0.0
python-evtx>=0.7.4
volatility3>=2.5.0
```
