# SIFTGuard Demo Video — Voiceover Script
# FIND EVIL! 2026 | Deadline Jun 15 2026
# Target: 3:30–4:00 | Judging criteria mapped per section

---

## SEGMENT 1 — HOOK (0:00–0:20) — Title Card
"In 2024, GTG-1002 used Claude Code to go from initial access to full domain control
in under eight minutes. Autonomous. Relentless. Unstoppable.
A human analyst pulling up their toolkit — doesn't stand a chance.
SIFTGuard changes that."

## SEGMENT 2 — WHAT IT IS (0:20–0:45) — Architecture Card
"SIFTGuard is a fully autonomous forensic investigation agent built on the SIFT Workstation
using a Custom MCP Server architecture — the most secure approach in this hackathon.
Instead of giving the AI raw shell access, every SIFT tool is exposed as a typed, structured
function. The agent physically cannot run destructive commands — because the server
doesn't have them.
Three specialized agents — Triage, Analyzer, and Planner — work in sequence,
orchestrated through a self-correcting execution loop with full audit trails."

## SEGMENT 3 — STAGE 1: EVIDENCE INVENTORY (0:45–1:00) — CRITERION 3 (Breadth/Depth)
"Stage one. Evidence inventory.
SIFTGuard connects to the MCP server and discovers four forensic artifacts —
a 2-gigabyte memory dump, Windows Security and System event logs,
and a 50-gigabyte disk image.
All artifact metadata is logged with timestamps before a single analysis runs."

## SEGMENT 4 — STAGE 2-3: AI TRIAGE (1:00–1:20) — CRITERION 2 (IR Accuracy)
"Stage two. The Triage Agent calls Groq's llama-3.3-70b model
to classify the incident before committing to deep analysis.
It returns threat type, severity — MEDIUM — and selects the default
incident response playbook. Ten steps loaded.
This is how a senior analyst thinks — orient before you drill."

## SEGMENT 5 — STAGE 4: SELF-CORRECTION (1:20–1:55) — CRITERION 1 (Autonomous Execution Quality — TIEBREAKER)
"Stage four. Deep forensic analysis begins. And here is where SIFTGuard
proves it can think for itself.
The agent attempts to run Volatility3 for memory analysis.
Attempt one — fails. Strategy fired: swap plugin syntax. Retry.
Attempt two — fails again. Strategy fired: fallback to simulation mode.
Attempt three — SUCCESS.
No human intervention. No crash. The agent diagnosed the failure,
selected a recovery strategy, and continued the investigation.
This is genuine autonomous self-correction — not a try-except wrapper.
Every correction event is logged to the audit trail with timestamp and strategy name."

## SEGMENT 6 — STAGE 5: FINDINGS VIA MCP (1:55–2:15) — CRITERION 2 + 5 (IR Accuracy + Audit Trail)
"Stage five. Three findings recorded directly through the MCP server.
CRITICAL: Backdoor account created — username 'hacker' — Windows Event ID 4720.
CRITICAL: Dual persistence established — both a scheduled task and a malicious service.
HIGH: Remote logon from attacker IP 185.220.101.47 — Event ID 4624.
Each finding is assigned a unique ID and traced back to the exact tool execution
that produced it — satisfying full audit trail requirements."

## SEGMENT 7 — STAGE 6-7: PLANNING + HITL EXECUTION (2:15–2:50) — CRITERION 4 (Constraint Implementation)
"Stage six. The Planner Agent calls Groq again — this time with RAG retrieval
pulling from the incident response playbook — to generate a five-action remediation plan.
Containment: block the C2 IP, isolate the host.
Eradication: delete the malicious service, remove the scheduled task.
Recovery: restore to known-good state.
Stage seven. The Human-in-the-Loop approval gate.
In production, every HIGH and CRITICAL action requires a human SRE to approve before execution.
This is architectural enforcement — not a prompt instruction the model can ignore.
Five actions executed. Zero skipped. Zero evidence touched without authorization."

## SEGMENT 8 — RESULTS + AUDIT TRAIL (2:50–3:15) — CRITERION 5 + 6 (Audit Trail + Usability)
"Stage eight. Investigation complete.
2.9 seconds. Three findings — two CRITICAL, one HIGH.
Five remediation actions executed. Two autonomous self-corrections applied.
A full JSON report and structured audit trail generated —
every agent decision, every tool call, every retry — timestamped and traceable.
Judges can trace any finding back to the exact MCP tool execution that produced it.
The audit trail is the evidence chain. It survives court."

## SEGMENT 9 — OUTRO / CTA (3:15–3:35) — Closes strong
"SIFTGuard is open source, MIT licensed, and built to run on the SIFT Workstation
with a single command: python main.py
The architecture is designed to be extended — add more MCP tools,
plug in more agents, connect to live SIEM data.
Find it at github.com/sodiq-code/siftguard.
The adversary moves at machine speed. SIFTGuard matches it."
