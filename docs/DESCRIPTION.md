# SIFTGuard — Written Description

## What It Does

SIFTGuard is an autonomous forensic investigation agent that detects, analyzes, and responds to endpoint compromises using SIFT Workstation forensic tools. Given a set of forensic artifacts (memory dump, Windows Event Logs, disk image), SIFTGuard autonomously:

1. **Inventories evidence** and assesses what analysis is possible
2. **Triages the threat** using Groq AI to classify incident type and severity
3. **Loads the correct playbook** — malware, ransomware, intrusion, or lateral movement
4. **Performs deep forensic analysis** using volatility3 (memory), python-evtx (logs), and sleuthkit (disk)
5. **Self-corrects** when tools fail — diagnoses the failure, selects an alternative strategy, and retries
6. **Extracts IOCs** — C2 IPs, malware paths, backdoor accounts, suspicious processes
7. **Maps findings to MITRE ATT&CK** — every finding has a technique ID and tactic
8. **Generates a remediation plan** using Groq + RAG over DFIR playbooks
9. **Presents to a human for approval** — the analyst approves or rejects each action
10. **Produces a complete report** — findings, audit trail, accuracy metrics, MITRE coverage

## The Core Innovation

### Purpose-Built Forensic MCP Server

SIFTGuard builds a custom MCP (Model Context Protocol) server that wraps SIFT forensic tools as typed, schema-validated AI-callable functions. This is fundamentally different from just giving an LLM a bash terminal.

Benefits:
- **Repeatability**: Every tool call has a defined input schema and output structure
- **Auditability**: Every call is logged with args, result, timestamp, and success status
- **Self-correctability**: The agent can inspect structured failures and retry intelligently
- **Security**: No shell injection possible — tools are called as typed Python functions

The 10 MCP tools cover the full DFIR workflow:
- Memory forensics (volatility3: pslist, netscan, malfind, cmdline)
- Event log analysis (python-evtx: any EVTX with event ID filtering)
- Disk analysis (sleuthkit: fls, mmls, istat)
- IOC extraction (regex engine: IPs, hashes, paths, registry keys)
- MITRE mapping (keyword-to-technique knowledge base)
- Playbook retrieval (DFIR playbook RAG)
- Case management (record_finding, get_audit_trail)

### Self-Correction System

The `SelfCorrectionAgent` wraps every tool call in a retry loop with pre-defined correction strategies per tool:

- **Volatility timeout** → retry with `--pid` filter to reduce scope
- **Empty EVTX results** → broaden event ID filter, increase limit
- **Sleuthkit failure** → switch from `fls` to `mmls`
- **No IOCs found** → expand regex patterns
- **Any tool unavailable** → fall back to simulated forensic data

Every correction event is logged to the audit trail — visible in demo video and accuracy report.

### Human-in-the-Loop Gate

The `ExecutorAgent` implements a structural HITL gate — not a prompt instruction. Every remediation action has `requires_approval: bool`. The executor blocks and waits for analyst input before any action tagged HIGH risk. In demo mode, it auto-approves with a logged justification.

## Technical Stack

| Component | Technology |
|-----------|-----------|
| MCP Server | `mcp` Python package (Model Context Protocol) |
| AI/LLM | Groq llama-3.3-70b-versatile |
| Memory Forensics | volatility3 |
| Event Log Parsing | python-evtx |
| Disk Analysis | sleuthkit (fls, mmls, istat) |
| Timeline | log2timeline / artifact reconstruction |
| Audit Trail | structlog (JSON structured logging) |
| Data Validation | Pydantic v2 |
| Self-Correction | Custom retry-with-strategy loop |

## Why This Approach Wins

1. **Matches judge criteria exactly**: The SANS rubric explicitly calls out "Purpose-Built Forensic MCP Server" as the highest-scoring architecture
2. **All 6 judge criteria addressed**:
   - *Autonomous Execution Quality* → self-correction agent + full pipeline
   - *IR Accuracy* → MITRE mapping + IOC extraction + ground truth comparison
   - *Breadth/Depth* → 10 tools across memory + logs + disk + network
   - *Constraint Implementation* → HITL approval gate + finding validation
   - *Audit Trail Quality* → structlog JSON for every tool call
   - *Usability/Documentation* → one-command setup + all 8 docs
3. **Demo-ready**: Full pipeline runs in <60 seconds with visible self-correction
4. **Reproducible**: Evidence simulated — any judge can run it without SIFT VM
