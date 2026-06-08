# SIFTGuard — Architecture

## System Overview

SIFTGuard implements **Approach #2: Purpose-Built Forensic MCP Server** — the architecture SANS judges explicitly identify as most sound for this challenge.

The system has three layers:

1. **MCP Tool Layer** — 10 forensic tools wrapping SIFT binaries
2. **Agent Orchestration Layer** — 5 specialized AI agents
3. **Human-in-the-Loop Layer** — approval gate + audit trail

## Full Architecture Diagram

```
╔═══════════════════════════════════════════════════════════════════╗
║                    EVIDENCE LAYER                                 ║
║   Memory Dump (.mem)  │  EVTX Logs  │  Disk Image (.E01)         ║
╚═══════════════════════════════════════════════════════════════════╝
                            │
                            ▼
╔═══════════════════════════════════════════════════════════════════╗
║                  SIFTGuard MCP Server                            ║
║                                                                   ║
║  Tier 1 — Triage Tools:                                          ║
║  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────┐ ║
║  │  list_evidence   │  │  search_playbook│  │   check_mitre   │ ║
║  └──────────────────┘  └─────────────────┘  └─────────────────┘ ║
║                                                                   ║
║  Tier 2 — Analysis Tools:                                        ║
║  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────┐ ║
║  │  run_volatility  │  │   parse_evtx    │  │  run_sleuthkit  │ ║
║  │  (pslist,netscan │  │  (Security.evtx │  │  (fls, mmls,    │ ║
║  │  malfind,cmdline)│  │   System.evtx)  │  │   istat)        │ ║
║  └──────────────────┘  └─────────────────┘  └─────────────────┘ ║
║  ┌──────────────────┐  ┌─────────────────┐                       ║
║  │  extract_iocs    │  │  build_timeline │                       ║
║  │  (regex engine)  │  │  (log2timeline  │                       ║
║  │                  │  │   + reconstruct)│                       ║
║  └──────────────────┘  └─────────────────┘                       ║
║                                                                   ║
║  Tier 3 — Case Management:                                       ║
║  ┌──────────────────┐  ┌─────────────────┐                       ║
║  │  record_finding  │  │ get_audit_trail │                       ║
║  │  (JSONL persist) │  │ (structlog JSON)│                       ║
║  └──────────────────┘  └─────────────────┘                       ║
╚═══════════════════════════════════════════════════════════════════╝
                            │
                            │  tool calls (direct function calls
                            │  in demo; MCP transport in production)
                            ▼
╔═══════════════════════════════════════════════════════════════════╗
║               AGENT ORCHESTRATION LAYER                          ║
║                                                                   ║
║  Stage 1: TriageAgent                                            ║
║  ┌───────────────────────────────────────────────────────────┐   ║
║  │  Input: evidence_manifest, initial_indicators             │   ║
║  │  LLM: Groq llama-3.3-70b-versatile                       │   ║
║  │  Output: threat_type, severity, playbook, hypothesis      │   ║
║  └───────────────────────────────────────────────────────────┘   ║
║                            │                                      ║
║                            ▼                                      ║
║  Stage 2: AnalyzerAgent (wraps MCP tools)                        ║
║  ┌───────────────────────────────────────────────────────────┐   ║
║  │  Memory:  volatility pslist → netscan → malfind → cmdline│   ║
║  │  Logs:    parse_evtx (4624,4688,4720,4732,4698,7045)     │   ║
║  │  Disk:    sleuthkit fls (deleted file recovery)          │   ║
║  │  IOC:     extract_iocs from all tool output              │   ║
║  │  MITRE:   check_mitre for each behavioral indicator      │   ║
║  │  Output:  ForensicFinding[] + timeline + IOC dict        │   ║
║  └───────────────────────────────────────────────────────────┘   ║
║                            │                                      ║
║                            ▼                                      ║
║  Stage 3: SelfCorrectionAgent (wraps EVERY tool call)            ║
║  ┌───────────────────────────────────────────────────────────┐   ║
║  │  Attempt 1: tool(original_args) → FAIL                  │   ║
║  │  Diagnose: timeout / empty / wrong format                │   ║
║  │  Strategy: swap_plugin / broaden_filter / fallback       │   ║
║  │  Attempt 2: tool(corrected_args) → SUCCESS               │   ║
║  │  All events logged to correction_log[]                   │   ║
║  └───────────────────────────────────────────────────────────┘   ║
║                            │                                      ║
║                            ▼                                      ║
║  Stage 4: PlannerAgent                                           ║
║  ┌───────────────────────────────────────────────────────────┐   ║
║  │  Input: AnalysisResult (findings + IOCs + MITRE)         │   ║
║  │  RAG: DFIR playbook lookup                               │   ║
║  │  LLM: Groq llama-3.3-70b                                │   ║
║  │  Output: RemediationPlan (containment + eradication)     │   ║
║  └───────────────────────────────────────────────────────────┘   ║
║                            │                                      ║
║                            ▼                                      ║
║  Stage 5: ExecutorAgent (HUMAN-IN-THE-LOOP)                      ║
║  ┌───────────────────────────────────────────────────────────┐   ║
║  │  For each action requiring approval:                     │   ║
║  │    DEMO MODE: auto-approve (simulates SRE approval)      │   ║
║  │    INTERACTIVE: analyst types y/N per action             │   ║
║  │  Approval records logged with timestamp + approver       │   ║
║  └───────────────────────────────────────────────────────────┘   ║
╚═══════════════════════════════════════════════════════════════════╝
                            │
                            ▼
╔═══════════════════════════════════════════════════════════════════╗
║                    OUTPUT LAYER                                   ║
║                                                                   ║
║  findings.jsonl          — all findings (DRAFT status)           ║
║  report_SESSION.json     — complete investigation report          ║
║  audit_SESSION.json      — structured tool call audit trail       ║
║  accuracy.json           — TP/FP/FN metrics vs ground truth      ║
╚═══════════════════════════════════════════════════════════════════╝
```

## Key Design Decisions

### Why Purpose-Built MCP Server?

The MCP server wraps SIFT tools as typed, schema-validated functions. Benefits:
- **Repeatable**: Same tool, same args, same output schema every time
- **Auditable**: Every call logged with args + result summary + timestamp
- **Self-correctable**: Agent can inspect failure and retry with different args
- **Judge-visible**: All 10 tools listed in MCP handshake — inspectable

### Why 5 Separate Agents?

Separation of concerns enables:
- Each agent has a single responsibility (triage ≠ analysis ≠ planning)
- Self-correction works per-agent, not globally
- Human approval gate is explicit and documentable

### Why Groq llama-3.3-70b?

- Fast inference (critical for live demo)
- JSON mode for structured output
- No hallucination on forensic schemas (tested)
- Free tier available for judges to test

### Self-Correction Architecture

```
execute_with_correction(tool_fn, args, tool_name):
  for attempt in 1..MAX_RETRIES:
    result = tool_fn(**current_args)
    if is_successful(result, tool_name):
      return result
    strategy = find_strategy(tool_name, result)
    log_correction_event(strategy)
    current_args = strategy.transform(current_args)
  return last_result
```

All correction events → `correction_log[]` → printed to terminal + saved to audit.

### Human-in-the-Loop Design

The HITL gate is **structural**, not prompt-based:
- `requires_approval: bool` is set per-action during planning
- `ExecutorAgent.execute()` checks this flag before every action
- Demo mode: auto-approves with logged justification
- Interactive mode: blocks waiting for analyst `y/N`
- All approval decisions saved with timestamp + approver identity

## Data Flow

```
Evidence files
    │ list_evidence()
    ▼
Manifest dict
    │ TriageAgent.triage()
    ▼
TriageResult (threat_type, severity, playbook)
    │ search_playbook()
    ▼
Playbook steps loaded
    │ AnalyzerAgent.analyze() [wrapped in SelfCorrectionAgent]
    │   ├── run_volatility(pslist) → process list
    │   ├── run_volatility(netscan) → network connections
    │   ├── run_volatility(malfind) → injected code
    │   ├── run_volatility(cmdline) → command lines
    │   ├── parse_evtx(Security.evtx, [4624,4720,4732,4688,4698,7045])
    │   ├── build_timeline(evidence_dir)
    │   ├── run_sleuthkit(disk.E01, fls)
    │   ├── extract_iocs(all_tool_output)
    │   └── check_mitre(each_behavior)
    ▼
AnalysisResult (findings[], timeline[], iocs, mitre_techniques)
    │ record_finding() per finding
    ▼
findings.jsonl
    │ PlannerAgent.plan()
    ▼
RemediationPlan (containment[] + eradication[] + recovery[])
    │ ExecutorAgent.execute()
    ▼
ExecutionResult (actions_executed, approvals, audit)
    │ generate_accuracy_report()
    ▼
accuracy.json + report.json + audit.json
```
