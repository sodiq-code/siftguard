# SIFTGuard — Accuracy Report

## Executive Summary

SIFTGuard was evaluated against a simulated APT intrusion scenario (Windows lateral movement + persistence). The pipeline identified **3/3 critical attack indicators** with **LOW confidence** (appropriate given simulation mode), successfully contained the threat via 5 automated remediation actions, and maintained a complete audit trail with 2 self-correction events documented.

**Honest note:** This evaluation runs entirely in `DEMO_MODE=true`. SIFT binaries (volatility3, Sleuthkit) are not fully installed in this environment — tool outputs are deterministic simulations, not live forensic analysis. All findings, IOCs, and remediation plans are realistic but synthetic. The pipeline architecture, agent logic, self-correction mechanics, and audit trail are fully real.

---

## Evaluation Scenario

**Scenario:** APT actor gains remote access to Windows Server, creates a backdoor account, and installs dual persistence mechanisms (malicious service + scheduled task).

**Ground Truth (Known IOCs):**
1. Remote logon from malicious IP `185.220.101.47`
2. Backdoor account `hacker` created (Event 4720)
3. Malicious service `WindowsUpdate` → `C:\Temp\svch0st.exe` (Event 7045)
4. Scheduled task `PersistTask` for persistence (Event 4698)
5. Suspicious process `svch0st.exe` (typosquatted svchost) in memory

---

## Detection Accuracy

### Findings Detection

| Finding | Detected | Severity | Correct? |
|---------|----------|----------|---------|
| Remote logon from 185.220.101.47 | ✅ Yes | HIGH | ✅ |
| Backdoor account `hacker` (Event 4720) | ✅ Yes | CRITICAL | ✅ |
| Dual persistence (service + task) | ✅ Yes | CRITICAL | ✅ |

**Detection Rate: 3/3 = 100%** — against the simulated scenario the pipeline was designed for.  
**Caveat:** These findings are pre-seeded in simulation mode. Against a novel real-world case, detection rate would depend on tool availability and real Volatility3/Sleuthkit output.

### Findings Data Integrity Note

`data/cases/findings.jsonl` contains **8 entries** representing **4 unique findings** — each recorded twice because the pipeline was run twice during development. This is a known bug (no deduplication check before `record_finding()`). Unique finding IDs: `find_4e074085_001`, `find_4e074085_002`, `find_a1b2c3d4_001`, `find_ff001122_001`.

### IOC Extraction

| IOC Type | Value | Extracted | Correct? |
|----------|-------|-----------|---------|
| IP (C2) | `185.220.101.47` | ✅ | ✅ |
| File Path | `C:\Temp\svch0st.exe` | ✅ | ✅ |
| Account | `hacker` | ✅ (in finding) | ✅ |
| Hash | None | ❌ | ❌ — Sleuthkit simulation returns file paths, not hashes |
| Domain | None | N/A | N/A |

**IOC Extraction Rate: 3/5 relevant IOC types** — file hashes are not extracted. The `run_sleuthkit` tool in simulation mode returns `fls`-style file listings; it does not compute or extract cryptographic hashes from the disk image.

### MITRE ATT&CK Mapping

| Status | Detail |
|--------|--------|
| Hardcoded per-finding techniques (simulation) | **4** — T1078, T1136.001, T1053.005, T1070.004 |
| Dynamic `check_mitre` tool auto-mapping | **0** |

In DEMO_MODE, each simulated finding carries a hardcoded MITRE technique ID (visible in Stage 5/8 terminal output and Stage 8/8 audit summary: "4 ATT&CK techniques mapped"). These tags are pre-assigned in the simulation fixtures — they are not resolved at runtime by the `check_mitre` tool. The `check_mitre` tool exists in `tools/mcp_tools.py` and performs keyword-lookup against a technique knowledge base, but it is not wired into the `record_finding()` call path. Against real evidence, MITRE auto-mapping would require wiring `check_mitre` into the Analyzer agent output — this is a known gap.

### Timeline Reconstruction

| Expected Event | Reconstructed | Timestamp Correct? |
|---------------|---------------|-------------------|
| Initial access (4624) | ✅ | ✅ 2024-01-15T02:30:00Z |
| Account creation (4720) | ✅ | ✅ 2024-01-15T02:33:00Z |
| Service install (7045) | ✅ | ✅ 2024-01-15T02:35:00Z |
| Task creation (4698) | ✅ | ✅ 2024-01-15T02:37:10Z |

**Caveat:** Timeline events are simulated — the timestamps are deterministic fixtures embedded in the EVTX simulation, not parsed from a real `.evtx` file.

---

## AI Triage Accuracy

| Metric | Value | Notes |
|--------|-------|-------|
| Threat Classification | `unknown` | LLM conservative without malware samples |
| Severity Assessment | `MEDIUM` | Reasonable given available evidence |
| Confidence | `LOW` | Correct — memory sim, no real dump |
| Playbook Selected | `default` | Correct (no specific threat type confirmed) |
| Priority Artifacts | Memory, Security.evtx | ✅ Correct prioritization |

**Triage Notes:** `LOW` confidence is intentional and appropriate — the LLM correctly reflects uncertainty when running against simulated vs. real forensic data. The `unknown` threat type classification is honest; without real malware signatures or behavioral analysis, a definitive family assignment would be fabricated.

---

## Remediation Plan Accuracy

| Action | Appropriate? | Covers Ground Truth? |
|--------|-------------|---------------------|
| Block C2 IP `185.220.101.47` | ✅ | ✅ Containment |
| Isolate affected host | ✅ | ✅ Containment |
| Remove service `WindowsUpdate` | ✅ | ✅ Eradication |
| Delete `C:\Temp\svch0st.exe` | ✅ | ✅ Eradication |
| Remove scheduled task `PersistTask` | ✅ | ✅ Eradication |

**Plan Coverage: 5/5 actions appropriate for the simulated scenario.**  
Note: The plan does not include disabling the backdoor account `hacker` — this is a gap. A complete remediation would require account remediation as a 6th action.

---

## Self-Correction Performance

| Event | Tool | Failure | Strategy | Outcome |
|-------|------|---------|----------|---------|
| 1 | `run_volatility` | `volatility3.__main__` not executable | `swap_plugin_syntax` | ❌ Still failed |
| 2 | `run_volatility` | Same error | `fallback_to_simulation` | ✅ Succeeded |

**Self-Correction Success Rate: 1/2 strategies succeeded = task eventually completed.**  
The first strategy (`swap_plugin_syntax`) failed — this is real behavior, not cleaned up for the demo. The second strategy (`fallback_to_simulation`) correctly escalated to simulation mode and the pipeline continued. Both events are in the audit trail.

---

## Pipeline Performance

| Metric | Value |
|--------|-------|
| Total Runtime | ~3–4 seconds |
| Stages Completed | 8/8 |
| Unique Findings | 4 |
| findings.jsonl entries | 8 (4 findings × 2 runs — duplicate bug) |
| Remediation Actions Executed | 5 |
| Self-Corrections | 2 |
| Audit Trail | Complete |
| Report Generated | ✅ JSON |

---

## False Positive Analysis

| Category | FP Count | Notes |
|----------|----------|-------|
| Forensic findings | 0 confirmed | All 3 findings match the seeded scenario |
| IOC extractions | 0 confirmed | Regex extraction against simulated output |
| MITRE mappings | 0 false positives | 4 hardcoded simulation fixtures match the known scenario |
| Remediation actions | 1 gap | Account `hacker` not included in plan |

**Limitation:** Because the entire pipeline runs against deterministic simulation output, false positive analysis against a real adversarial dataset is not possible in the current evaluation. The simulation was designed to match the findings — this is by construction, not validation.

---

## Audit Trail Completeness

| Requirement | Satisfied |
|-------------|-----------|
| Session ID on all events | ✅ |
| Timestamps on all log entries | ✅ |
| Tool call inputs logged | ✅ |
| Self-correction events logged | ✅ |
| Remediation actions logged | ✅ |
| Approval decisions logged | ✅ |
| Final report generated | ✅ JSON |
| Immutable audit JSON | ✅ |

---

## Evidence Integrity

All MCP tool calls in SIFTGuard are read-only operations — the MCP server exposes no write, delete, or modify functions against evidence files. Original evidence data cannot be altered through the tool interface by architectural design, not prompt instruction. No spoliation testing was performed against adversarial inputs — this is a known gap.

---

## Limitations & Known Gaps

1. **MITRE ATT&CK Mapping:** 4 technique IDs (T1078, T1136.001, T1053.005, T1070.004) appear in simulation output as hardcoded fixtures per finding. Dynamic `check_mitre` tool auto-mapping is not wired into the `record_finding()` call path — zero runtime auto-mapping against novel data.

2. **Simulation Mode:** `DEMO_MODE=true` in `.env`. Volatility3 and Sleuthkit return fixture data, not real forensic analysis. Real SIFT Workstation with actual evidence files required for production use.

3. **Duplicate Findings Bug:** `findings.jsonl` accumulates entries across runs with no deduplication. Running `python main.py` twice produces 8 entries for 4 findings. Fix: add finding ID check before `record_finding()`.

4. **Hash Extraction:** No cryptographic file hashes extracted. `run_sleuthkit` simulation returns `fls`-style directory listings only.

5. **Network Analysis:** No PCAP parsing. DNS-based C2 and network IOCs beyond IPs would require a pcap module.

6. **Account Remediation Gap:** Remediation plan does not include disabling the backdoor account `hacker` — incomplete eradication for the given scenario.

---

## Summary Scores (Self-Assessment)

| Criterion | Score | Justification |
|-----------|-------|--------------|
| Detection Rate | 100% (simulation) | All 3/3 seeded findings detected — not validated against novel real-world data |
| IOC Accuracy | 60% | 3/5 IOC types extracted; no hash extraction |
| MITRE Coverage | 4 techniques (simulation fixtures) | Hardcoded per finding in DEMO_MODE; dynamic `check_mitre` not wired into pipeline |
| Timeline Accuracy | N/A | Fixtures only — no real EVTX parsing in demo |
| Plan Correctness | ~83% | 5/6 required actions included (missing account disable) |
| Self-Correction | ✅ Functional | 1/2 strategies succeeded; task completed via fallback |
| Audit Completeness | 100% | Full chain of custody maintained across all stages |
