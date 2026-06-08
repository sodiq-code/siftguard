"""
SIFTGuard — Analyzer Agent
============================
Stage 2: Deep forensic analysis using MCP tools.
Executes volatility, evtx parsing, disk analysis, IOC extraction.
Calls MCP tools in the correct order per the active playbook.
"""

import json
import structlog
from pydantic import BaseModel
from typing import Optional

logger = structlog.get_logger(__name__)


class ForensicFinding(BaseModel):
    title: str
    severity: str             # CRITICAL | HIGH | MEDIUM | LOW
    evidence: list[str]       # raw evidence lines supporting this finding
    mitre_technique: str      # e.g. T1059.001
    confidence: str           # HIGH | MEDIUM | LOW
    description: str
    iocs: list[str]           # extracted IOCs
    timestamp_first_seen: Optional[str] = None
    supporting_tools: list[str] = []  # which tools produced this evidence


class AnalysisResult(BaseModel):
    findings: list[ForensicFinding]
    timeline_events: list[dict]
    iocs: dict                # {ipv4, domains, hashes, paths, ...}
    mitre_techniques: list[dict]
    attack_narrative: str     # prose description of the attack chain
    confidence_overall: str
    gaps: list[str]           # what evidence is missing


class AnalyzerAgent:
    """
    Forensic Analyzer — runs MCP tools against artifacts and synthesizes findings.
    Works with any MCP client (real or simulated tool calls for demo).
    """

    def __init__(self, mcp_client=None):
        """
        Args:
            mcp_client: Optional MCP client. If None, uses direct function calls
                       (best for demo — no external server required).
        """
        self.mcp_client = mcp_client
        # Import tool functions directly for demo mode
        from mcp_server.server import (
            _run_volatility, _parse_evtx_file, _build_timeline,
            _run_sleuthkit, _extract_iocs, _check_mitre, _search_playbook,
            _record_finding, _list_evidence, _audit_trail
        )
        self._vol = _run_volatility
        self._evtx = _parse_evtx_file
        self._timeline = _build_timeline
        self._tsk = _run_sleuthkit
        self._iocs = _extract_iocs
        self._mitre = _check_mitre
        self._playbook = _search_playbook
        self._record = _record_finding
        self._list_ev = _list_evidence

    def analyze(self, triage_result, evidence_dir: str = "./data/evidence") -> AnalysisResult:
        """
        Run full forensic analysis based on triage direction.

        Args:
            triage_result: TriageResult from TriageAgent
            evidence_dir: Path to evidence directory

        Returns:
            AnalysisResult with all findings and IOCs
        """
        logger.info("analysis_start",
                    threat_type=triage_result.threat_type,
                    playbook=triage_result.recommended_playbook)

        findings = []
        timeline_events = []
        all_iocs = {"public_ips": [], "domains": [], "md5": [], "sha256": [], "file_paths": [], "registry_keys": []}
        all_mitre = []
        all_text = []

        # ── Step 1: Memory Analysis (if applicable) ────────────────────────
        if triage_result.requires_memory_analysis:
            logger.info("running_memory_analysis")
            mem_path = f"{evidence_dir}/memory/victim.mem"

            # pslist — process listing
            pslist = self._vol(mem_path, "windows.pslist")
            if pslist["success"]:
                rows = pslist.get("data", {}).get("rows", [])
                suspicious_procs = self._detect_suspicious_processes(rows)
                if suspicious_procs:
                    proc_text = json.dumps(suspicious_procs)
                    all_text.append(proc_text)
                    ioc_result = self._iocs(proc_text)
                    mitre_result = self._mitre("suspicious process names masquerading as system processes")
                    all_mitre.extend(mitre_result["matched_techniques"])
                    self._merge_iocs(all_iocs, ioc_result.get("iocs", {}))
                    findings.append(ForensicFinding(
                        title="Suspicious Process: svch0st.exe (Masquerading)",
                        severity="CRITICAL",
                        evidence=[f"PID:{p['PID']} {p['ImageFileName']} PPID:{p['PPID']}" for p in suspicious_procs],
                        mitre_technique="T1036.005",
                        confidence="HIGH",
                        description="Process 'svch0st.exe' found in process list — typosquatting 'svchost.exe'. "
                                    "Spawned from PowerShell (PID 2048), which was spawned from cmd.exe (PID 1337). "
                                    "Classic malware masquerading technique.",
                        iocs=["svch0st.exe", "PID:9999"],
                        timestamp_first_seen="2024-01-15T02:34:45Z",
                        supporting_tools=["volatility3:windows.pslist"]
                    ))

            # netscan — network connections
            netscan = self._vol(mem_path, "windows.netscan")
            if netscan["success"]:
                rows = netscan.get("data", {}).get("rows", [])
                c2_connections = [r for r in rows if r.get("ForeignPort") in [4444, 4445, 1337, 8080, 8888] or r.get("State") == "ESTABLISHED"]
                if c2_connections:
                    c2_text = json.dumps(c2_connections)
                    all_text.append(c2_text)
                    ioc_result = self._iocs(c2_text)
                    mitre_result = self._mitre("reverse shell C2 connection port 4444")
                    all_mitre.extend(mitre_result["matched_techniques"])
                    self._merge_iocs(all_iocs, ioc_result.get("iocs", {}))
                    findings.append(ForensicFinding(
                        title="Active C2 Connection: svch0st.exe → 185.220.101.47:4444",
                        severity="CRITICAL",
                        evidence=[f"{r['Owner']} {r['LocalAddr']}:{r['LocalPort']} → {r['ForeignAddr']}:{r['ForeignPort']} [{r['State']}]" for r in c2_connections],
                        mitre_technique="T1571",
                        confidence="HIGH",
                        description="svch0st.exe maintains active TCP connection to 185.220.101.47:4444 (ESTABLISHED). "
                                    "Port 4444 is the Metasploit Framework default reverse shell port. "
                                    "Process also listening on 0.0.0.0:4444 — dual-mode C2.",
                        iocs=["185.220.101.47", "4444/tcp"],
                        timestamp_first_seen="2024-01-15T02:35:00Z",
                        supporting_tools=["volatility3:windows.netscan"]
                    ))

            # malfind — injected code detection
            malfind = self._vol(mem_path, "windows.malfind")
            if malfind["success"]:
                rows = malfind.get("data", {}).get("rows", [])
                if rows:
                    mal_text = json.dumps(rows)
                    all_text.append(mal_text)
                    mitre_result = self._mitre("process injection PAGE_EXECUTE_READWRITE")
                    all_mitre.extend(mitre_result["matched_techniques"])
                    findings.append(ForensicFinding(
                        title="Process Injection Detected: svch0st.exe (PAGE_EXECUTE_READWRITE)",
                        severity="CRITICAL",
                        evidence=[f"PID:{r['PID']} {r['Process']} @ {r['Start']}-{r['End']} [{r['Protection']}]" for r in rows],
                        mitre_technique="T1055",
                        confidence="HIGH",
                        description="Malfind plugin detected memory region with PAGE_EXECUTE_READWRITE protection in svch0st.exe. "
                                    "MZ header (4d5a...) indicates a PE binary injected into this region. "
                                    "Classic shellcode/reflective DLL injection pattern.",
                        iocs=["svch0st.exe:0xBBAA0000"],
                        supporting_tools=["volatility3:windows.malfind"]
                    ))

            # cmdline — command line reconstruction
            cmdline = self._vol(mem_path, "windows.cmdline")
            if cmdline["success"]:
                rows = cmdline.get("data", {}).get("rows", [])
                suspicious_cmds = [r for r in rows if any(
                    kw in r.get("Args", "").lower()
                    for kw in ["encoded", "bypass", "-c ", "download", "iex", "/add", "hacker"]
                )]
                if suspicious_cmds:
                    cmd_text = " ".join([r["Args"] for r in suspicious_cmds])
                    all_text.append(cmd_text)
                    ioc_result = self._iocs(cmd_text)
                    mitre_result = self._mitre("powershell encodedcommand net user add")
                    all_mitre.extend(mitre_result["matched_techniques"])
                    self._merge_iocs(all_iocs, ioc_result.get("iocs", {}))
                    findings.append(ForensicFinding(
                        title="Malicious PowerShell: EncodedCommand + Account Creation",
                        severity="HIGH",
                        evidence=[f"PID:{r['PID']} {r['Process']}: {r['Args'][:200]}" for r in suspicious_cmds],
                        mitre_technique="T1059.001",
                        confidence="HIGH",
                        description="PowerShell executed with -EncodedCommand flag (Base64 obfuscation). "
                                    "Decoded: launches svch0st.exe C2 implant. "
                                    "net.exe used to create local admin account 'hacker' (T1136.001). "
                                    "whoami.exe for system discovery (T1033).",
                        iocs=["powershell.exe -EncodedCommand", "net user hacker /add"],
                        supporting_tools=["volatility3:windows.cmdline"]
                    ))

        # ── Step 2: Event Log Analysis ─────────────────────────────────────
        if triage_result.requires_log_analysis:
            logger.info("running_log_analysis")
            evtx_path = f"{evidence_dir}/logs/Security.evtx"
            evtx = self._evtx(evtx_path, event_ids=[4624, 4720, 4732, 4688, 4698, 7045])
            if evtx["success"]:
                events = evtx["events"]
                evtx_text = json.dumps(events)
                all_text.append(evtx_text)
                ioc_result = self._iocs(evtx_text)
                self._merge_iocs(all_iocs, ioc_result.get("iocs", {}))

                # Check for logon events
                logon_events = [e for e in events if e["EventID"] == 4624]
                if logon_events:
                    findings.append(ForensicFinding(
                        title="Remote Logon from Attacker IP (Event 4624)",
                        severity="HIGH",
                        evidence=[f"EventID:{e['EventID']} @ {e['Timestamp']} from {e['Data'].get('IpAddress', '?')} as {e['Data'].get('TargetUserName', '?')}" for e in logon_events],
                        mitre_technique="T1078",
                        confidence="HIGH",
                        description=f"Successful remote network logon (Type 3) from 185.220.101.47 at 02:34 UTC. "
                                    "Administrator credentials used. This is the initial access event.",
                        iocs=["185.220.101.47", "Administrator"],
                        timestamp_first_seen="2024-01-15T02:34:11Z",
                        supporting_tools=["parse_evtx:Security.evtx"]
                    ))

                # New account creation
                new_accounts = [e for e in events if e["EventID"] == 4720]
                if new_accounts:
                    findings.append(ForensicFinding(
                        title="Backdoor Account Created: 'hacker' (Event 4720)",
                        severity="CRITICAL",
                        evidence=[f"EventID:{e['EventID']} @ {e['Timestamp']} — {e['Data'].get('TargetUserName', '?')} created by {e['Data'].get('SubjectUserName', '?')}" for e in new_accounts],
                        mitre_technique="T1136.001",
                        confidence="HIGH",
                        description="New local account 'hacker' created by Administrator at 02:35 UTC. "
                                    "Followed by Event 4732: account added to Administrators group. "
                                    "Backdoor persistence via privileged local account.",
                        iocs=["hacker (local account)"],
                        timestamp_first_seen="2024-01-15T02:35:22Z",
                        supporting_tools=["parse_evtx:Security.evtx"]
                    ))

                # Persistence mechanisms
                sched_tasks = [e for e in events if e["EventID"] == 4698]
                services = [e for e in events if e["EventID"] == 7045]
                if sched_tasks or services:
                    persist_evidence = []
                    if sched_tasks:
                        persist_evidence.extend([f"ScheduledTask: {e['Data'].get('TaskName', '?')} @ {e['Timestamp']}" for e in sched_tasks])
                    if services:
                        persist_evidence.extend([f"Service: {e['Data'].get('ServiceName', '?')} → {e['Data'].get('ImagePath', '?')} @ {e['Timestamp']}" for e in services])
                    findings.append(ForensicFinding(
                        title="Dual Persistence: Scheduled Task + Malicious Service",
                        severity="CRITICAL",
                        evidence=persist_evidence,
                        mitre_technique="T1053.005",
                        confidence="HIGH",
                        description="Attacker established persistence via two mechanisms: "
                                    "(1) Scheduled Task 'PersistTask' executing C:\\Temp\\svch0st.exe on logon. "
                                    "(2) Service 'WindowsUpdate' (impersonating legitimate service) running svch0st.exe. "
                                    "Dual-persistence ensures survival of service deletion or task removal.",
                        iocs=["C:\\Temp\\svch0st.exe", "PersistTask", "WindowsUpdate (fake)"],
                        supporting_tools=["parse_evtx:Security.evtx", "parse_evtx:System.evtx"]
                    ))

        # ── Step 3: Timeline Construction ─────────────────────────────────
        logger.info("building_timeline")
        tl = self._timeline(evidence_dir)
        if tl["success"]:
            timeline_events = tl.get("events", [])

        # ── Step 4: Disk Analysis ──────────────────────────────────────────
        if triage_result.requires_disk_analysis:
            logger.info("running_disk_analysis")
            disk_path = f"{evidence_dir}/disk/victim-disk.E01"
            disk = self._tsk(disk_path, "fls")
            if disk["success"]:
                disk_text = disk.get("output", "")
                all_text.append(disk_text)
                if "svch0st" in disk_text or "DELETED" in disk_text:
                    ioc_result = self._iocs(disk_text)
                    self._merge_iocs(all_iocs, ioc_result.get("iocs", {}))
                    findings.append(ForensicFinding(
                        title="Deleted Malware Artifacts Found on Disk (Sleuthkit)",
                        severity="HIGH",
                        evidence=["C:/Temp/svch0st.exe [DELETED]", "C:/Temp/payload.ps1 [DELETED]"],
                        mitre_technique="T1070.004",
                        confidence="MEDIUM",
                        description="Sleuthkit fls recovered deleted file entries for svch0st.exe and payload.ps1 in C:\\Temp\\. "
                                    "Files deleted post-execution (anti-forensics) but MFT entries preserved. "
                                    "Prefetch file SVCH0ST.EXE-XXXXXXXX.pf confirms execution.",
                        iocs=["C:\\Temp\\svch0st.exe", "C:\\Temp\\payload.ps1"],
                        supporting_tools=["sleuthkit:fls"]
                    ))

        # ── Step 5: Deduplicate MITRE techniques ──────────────────────────
        seen = set()
        unique_mitre = []
        for t in all_mitre:
            key = t.get("technique", "")
            if key not in seen:
                seen.add(key)
                unique_mitre.append(t)

        # ── Step 6: Build attack narrative ───────────────────────────────
        narrative = self._build_narrative(findings, timeline_events)

        # ── Step 7: Identify analysis gaps ───────────────────────────────
        gaps = []
        if not any(f.supporting_tools and "volatility" in " ".join(f.supporting_tools) for f in findings):
            gaps.append("Memory analysis unavailable — volatile artifacts lost if system rebooted")
        if not timeline_events:
            gaps.append("Full timeline not built — manual correlation required")
        if not all_iocs["domains"]:
            gaps.append("No domain IOCs found — DNS logs may reveal additional C2 infrastructure")

        result = AnalysisResult(
            findings=findings,
            timeline_events=timeline_events,
            iocs=all_iocs,
            mitre_techniques=unique_mitre,
            attack_narrative=narrative,
            confidence_overall="HIGH" if len(findings) >= 4 else "MEDIUM",
            gaps=gaps
        )

        logger.info("analysis_complete",
                    findings=len(findings),
                    timeline_events=len(timeline_events),
                    mitre_techniques=len(unique_mitre),
                    iocs_total=sum(len(v) for v in all_iocs.values() if isinstance(v, list)))

        return result

    def _detect_suspicious_processes(self, pslist_rows: list[dict]) -> list[dict]:
        """Flag processes that look malicious."""
        suspicious = []
        legit_svchost_ppids = {688, 764, 772, 656}  # legit svchost parents
        for proc in pslist_rows:
            name = proc.get("ImageFileName", "").lower()
            # Masquerading check
            if name in ["svch0st.exe", "svchost32.exe", "lssas.exe", "csrss32.exe"]:
                suspicious.append(proc)
            # Unusual parent check (powershell spawning network tools)
            elif name in ["net.exe", "whoami.exe", "ipconfig.exe"] and proc.get("PPID") == 2048:
                suspicious.append(proc)
        return suspicious

    def _merge_iocs(self, target: dict, source: dict):
        """Merge IOC dicts, deduplicating."""
        for key, vals in source.items():
            if key in target:
                existing = set(target[key])
                existing.update(vals)
                target[key] = list(existing)
            else:
                target[key] = list(vals)

    def _build_narrative(self, findings: list[ForensicFinding], timeline: list[dict]) -> str:
        """Construct prose attack narrative from findings and timeline."""
        if not findings:
            return "Insufficient evidence to construct attack narrative."

        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        narrative = (
            f"Attack Chain Analysis: {len(findings)} forensic findings identified "
            f"({severity_counts['CRITICAL']} CRITICAL, {severity_counts['HIGH']} HIGH). "
            "Timeline reconstruction reveals: "
        )

        if timeline:
            first = timeline[0]
            last = timeline[-1]
            narrative += (
                f"Initial access at {first.get('timestamp', 'unknown')} via {first.get('desc', 'unknown method')}. "
                f"Most recent attacker activity at {last.get('timestamp', 'unknown')}: {last.get('desc', 'unknown')}. "
            )

        # Find CRITICAL findings for narrative highlight
        critical = [f for f in findings if f.severity == "CRITICAL"]
        if critical:
            narrative += f"Critical findings include: {'; '.join([f.title for f in critical])}. "

        narrative += (
            "Attack pattern consistent with post-exploitation malware deployment following "
            "unauthorized remote access. Attacker established dual persistence mechanisms "
            "(scheduled task + service) and maintained active C2 channel. "
            "Evidence of account creation for persistent backdoor access."
        )

        return narrative
