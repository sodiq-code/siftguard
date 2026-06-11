# SIFTGuard — Try-It-Out Instructions

> **Platform:** Designed and tested for **SANS SIFT Workstation** (Ubuntu 22.04 LTS base).  
> SIFT Workstation has volatility3, sleuthkit, and python-evtx pre-installed — SIFTGuard integrates directly with these tools via its Custom MCP Server.

---

## Option A — SIFT Workstation (Recommended for Judges)

This is the intended deployment environment. Download the SIFT Workstation OVA from [SANS](https://www.sans.org/tools/sift-workstation/) and boot it, or use a SIFT-provisioned Linux host.

### 1. Clone the Repository

```bash
git clone https://github.com/sodiq-code/siftguard.git
cd siftguard
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** On SIFT Workstation, `volatility3` and `sleuthkit` are pre-installed system-wide. SIFTGuard auto-detects them. `pip install -r requirements.txt` only adds the Python orchestration layer.

### 4. Configure API Key

```bash
cp .env.example .env
# Edit .env and set your Groq API key (free at console.groq.com):
# GROQ_API_KEY=gsk_your_key_here
```

### 5. Run the Demo

```bash
python main.py
```

The full 8-stage pipeline runs in ~5 seconds with deterministic demo output.

---

## Option B — Generic Ubuntu/Debian (Non-SIFT)

If you don't have SIFT Workstation, install the required forensic tools manually:

```bash
# Sleuthkit
sudo apt update && sudo apt install -y sleuthkit

# Volatility3
pip install volatility3

# python-evtx (also installed via requirements.txt)
pip install python-evtx
```

Then follow steps 1–5 above. All other behavior is identical.

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
   data/evidence/memory/victim.mem        ← Volatility3 memory image
   data/evidence/logs/Security.evtx       ← Windows Event Log
   data/evidence/disk/victim-disk.E01     ← Disk image (Sleuthkit)
   ```

2. Disable demo mode in `.env`:
   ```
   DEMO_MODE=false
   ```

3. Run normally:
   ```bash
   python main.py
   ```

SIFTGuard auto-detects real evidence and invokes live SIFT tools. No code changes needed.

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
| `DEMO_MODE` | `true` | Auto-approve + use simulated evidence |
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
| Volatility3 fails on real evidence | Expected on non-SIFT hosts — pipeline self-corrects |
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
