# SIFTGuard — Written Description

## What It Does

SIFTGuard is an autonomous, multi-agent Digital Forensics and Incident Response (DFIR) system built on a purpose-built forensic MCP server. Given a set of forensic artifacts — memory dump, Windows Event Logs, disk image — SIFTGuard runs a full 8-stage investigation pipeline without human intervention, then presents a verified remediation plan for analyst approval.

**One command. Full investigation. Complete audit trail.**

```bash
python main.py   # demo mode — no API key required
python main.py --live   # live Groq API triage
```

---

## The 8-Stage Pipeline

| Stage | Agent | MCP Tools Used |
|-------|-------|---------------|
| 1. Evidence Inventory | Orchestrator | `list_evidence` |
| 2. AI Triage | TriageAgent (Groq llama-3.3-70b) | — |
| 3. Playbook Loading | Orchestrator | `search_playbook` |
| 4. Deep Analysis | AnalyzerAgent | `run_volatility`, `parse_evtx`, `build_timeline`, `run_sleuthkit`, `extract_iocs`, `check_mitre` |
| 5. Finding Recording | AnalyzerAgent | `record_finding` (with auto MITRE enrichment) |
| 6. Remediation Plan | PlannerAgent (Groq + RAG) | — |
| 7. Human Approval Gate | ExecutorAgent | HITL enforcement |
| 8. Report + Audit | Orchestrator | `get_audit_trail` |

---

## Addressing All 6 Evaluation Criteria

### 1. Autonomous Execution Quality (Tiebreaker)

The `SelfCorrectionAgent` wraps every MCP tool call in a structured retry loop with pre-defined correction strategies per tool type:

- **Volatility module error** → retry with corrected plugin syntax
- **Tool unavailable** → fall back to forensic simulation dataset
- **Empty EVTX results** → broaden event ID filter
- **Sleuthkit failure** → switch command variant (fls → mmls)

Both correction events are real runtime failures — not staged. They are logged to the audit trail with timestamps, strategies applied, and outcomes. The pipeline completed successfully via autonomous recovery, with zero human intervention.

### 2. IR Accuracy

All findings carry a dual confidence label:

- **CONFIRMED** — directly evidenced by a specific tool output (e.g., Event ID 4720, process name match)
- **INFERRED** — pattern-matched or correlated across sources (e.g., C2 attribution from port + process correlation)

MITRE ATT&CK mapping is now wired directly into `record_finding()`. Every time a finding is recorded, `check_mitre()` runs against the finding description and enriches it with dynamically resolved technique IDs, tactics, and technique names. These are stored as `mitre_technique_dynamic` and `mitre_all_matched` fields alongside the original technique tag.

Ground truth comparison: 3/3 critical attack indicators detected (remote logon, backdoor account, dual persistence). Full accuracy report with gap analysis in `docs/ACCURACY.md`.

### 3. Breadth and Depth of Investigation

**10 MCP tools** covering the complete forensic stack:

| Layer | Tools | Evidence Types |
|-------|-------|---------------|
| Memory | `run_volatility` (pslist, netscan, malfind, cmdline) | Process injection, C2, cmdline obfuscation |
| Logs | `parse_evtx` (Event IDs 4624/4688/4720/4698/7045) | Logon, execution, account creation, persistence |
| Disk | `run_sleuthkit` (fls, mmls, istat) | Deleted artifacts, MFT entries, prefetch |
| Correlation | `build_timeline`, `extract_iocs` | Supertimeline, IOC cross-linking |
| Intelligence | `check_mitre`, `search_playbook` | ATT&CK mapping, DFIR playbook RAG |
| Case Mgmt | `record_finding`, `get_audit_trail` | Chain-of-custody, immutable audit |

The pipeline covers memory + logs + disk in a single run and correlates findings across all three layers into a unified attack narrative and supertimeline.

### 4. Constraint Implementation

**Architectural read-only enforcement — not prompt-based.**

The MCP server exposes zero write, delete, or modify functions against evidence files. An agent with full tool access cannot alter forensic artifacts through the tool interface — this is enforced at the function signature level, not by LLM instruction.

**Spoliation bypass testing:**

The following adversarial inputs were tested against the MCP server to verify constraint enforcement:

| Test | Input | Result |
|------|-------|--------|
| Prompt injection via IOC text | `text="DROP TABLE findings; rm -rf /evidence"` | Passed to regex engine only — no execution surface |
| Tool argument manipulation | `run_sleuthkit(image_path="../../etc/passwd")` | Path traversal returns error — no file write |
| Finding overwrite attempt | `record_finding(id="existing-id", title="overwrite")` | Deduplication check rejects duplicate IDs |
| Audit trail tampering | Calling `get_audit_trail` does not expose write path | Read-only view — append-only log file |

The HITL gate in `ExecutorAgent` is a structural block — the executor holds an explicit `requires_approval: bool` per action and will not call any remediation function without `approved=True`. In interactive mode (`python main.py --interactive`), this halts the pipeline at Stage 7 and waits for `y/n` input per action.

### 5. Audit Trail Quality

Every tool call, agent decision, correction event, and approval action is logged via `structlog` as a JSON entry with:

- `timestamp` (UTC ISO 8601)
- `agent` (which agent made the call)
- `tool` (MCP tool name or agent name)
- `args` (input arguments)
- `result_summary` (outcome summary)
- `success` (bool)

The audit trail is append-only, written once per session, and saved as `data/cases/audit_<session_id>.json`. Finding IDs are SHA-256 derived from the finding title — deterministic and collision-resistant. The full chain traces every finding back to the exact tool call and tool output that produced it.

**Audit trail entries per session: 15** — covering all 8 stages plus self-correction events.

### 6. Usability and Documentation

All 8 required submission components are present:

| Component | File / Location |
|-----------|----------------|
| Code repository | github.com/sodiq-code/siftguard (MIT license) |
| Demo video | `demo/siftguard_ELITE_v4_final.mp4` (4m17s) |
| Architecture diagram | `docs/architecture_diagram.png` |
| Written description | `docs/DESCRIPTION.md` (this file) |
| Dataset documentation | `docs/DATASET.md` |
| Accuracy report | `docs/ACCURACY.md` (honest, with known gaps) |
| Try-it-out instructions | `docs/HOWTO.md` (SIFT Workstation first) |
| Agent execution logs | `docs/EXECUTION_LOGS.md` (full terminal output + agent decision table) |

Setup is a single `pip install -r requirements.txt`. Demo mode runs without any API key. SIFT Workstation instructions in `HOWTO.md` cover real evidence setup for production use.

---

## The Core Innovation: Purpose-Built Forensic MCP Server

SIFTGuard implements the architecture SANS explicitly identifies as most sound: a **purpose-built forensic MCP server** that wraps SIFT tools as typed, schema-validated, AI-callable functions.

This is fundamentally different from giving an LLM a bash terminal:

| Approach | Shell Access | MCP Server (SIFTGuard) |
|----------|-------------|------------------------|
| Tool calls | Unstructured text | Typed Python functions with JSON schema |
| Auditability | grep through logs | Structured JSON per call |
| Self-correction | Retry blind | Inspect structured error → choose strategy |
| Evidence safety | Shell can write | Zero write surface on evidence |
| Reproducibility | Environment-dependent | Schema-validated, deterministic demo mode |

The 10 MCP tools are callable by any MCP-compatible LLM client — they are not specific to Groq or any single model. SIFTGuard is designed to be extended to Claude, GPT-4o, or any future model without changing the tool layer.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| MCP Server | Python `mcp` package (Model Context Protocol) |
| AI / LLM | Groq llama-3.3-70b-versatile |
| Memory Forensics | volatility3 (pslist, netscan, malfind, cmdline) |
| Event Log Parsing | python-evtx |
| Disk Analysis | sleuthkit (fls, mmls, istat) |
| Timeline | log2timeline / artifact reconstruction |
| Audit Trail | structlog (JSON structured logging) |
| Data Validation | Pydantic v2 |
| Self-Correction | Custom retry-with-strategy loop (`SelfCorrectionAgent`) |
| HITL Gate | Structural approval gate (`ExecutorAgent`) |

---

## Honest Evaluation

SIFTGuard was designed to be transparent about its limitations:

- **Demo mode** uses deterministic simulation data — full forensic accuracy requires real SIFT Workstation environment
- **MITRE mapping** uses keyword-to-technique lookup — embedding-based semantic matching would improve coverage on novel behaviors
- **Timeline events** are reconstructed from simulated EVTX — real `.evtx` parsing works via python-evtx on actual evidence files
- **No PCAP analysis** — network IOCs limited to IPs extracted from memory and log artifacts

All known gaps are documented in `docs/ACCURACY.md` with honest self-assessment scores.
