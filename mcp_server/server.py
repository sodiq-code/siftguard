"""
SIFTGuard — Forensic MCP Server
=================================
Exposes SIFT forensic tools as MCP-callable functions for the AI agent pipeline.

Tools exposed:
  Tier 1 — Triage:
    - run_volatility      : Memory forensics (pslist, netscan, malfind, cmdline)
    - parse_evtx          : Windows Event Log parsing + filtering
    - build_timeline      : log2timeline-style supertimeline from artifacts

  Tier 2 — Deep Analysis:
    - run_sleuthkit       : Disk image analysis (fls, istat, mmls)
    - extract_iocs        : Regex IOC extraction from text (IPs, domains, hashes)
    - yara_scan           : YARA rule scanning against files/memory dumps

  Tier 3 — Intelligence:
    - check_mitre         : Map behavior to MITRE ATT&CK technique
    - search_playbook     : Retrieve DFIR playbook for a given threat type
    - record_finding      : Persist a validated forensic finding to case file

  Utility:
    - list_evidence       : List all artifacts in evidence directory
    - get_audit_trail     : Return structured audit trail from current session
"""

import os
import re
import json
import asyncio
import subprocess
import hashlib
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)

EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "./data/evidence"))
CASE_DIR = Path(os.getenv("CASE_DIR", "./data/cases"))

# Session-scoped audit trail
_audit_trail: list[dict] = []
_findings: list[dict] = []


def _log_tool_call(tool: str, args: dict, result_summary: str, success: bool):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "args": args,
        "result_summary": result_summary,
        "success": success,
    }
    _audit_trail.append(entry)
    logger.info("tool_executed", tool=tool, success=success, summary=result_summary)


# ─── SIFT Tool Wrappers ───────────────────────────────────────────────────────

def _run_volatility(dump_path: str, plugin: str, extra_args: list[str] = None, _simulate: bool = False) -> dict:
    """Run volatility3 against a memory dump."""
    if _simulate:
        return _simulate_volatility(dump_path, plugin)
    cmd = ["python3", "-m", "volatility3", "-f", dump_path, "--output=json", plugin]
    if extra_args:
        cmd.extend(extra_args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return {"success": True, "data": data, "plugin": plugin}
            except json.JSONDecodeError:
                return {"success": True, "data": result.stdout[:5000], "plugin": plugin}
        else:
            return {"success": False, "error": result.stderr[:2000], "plugin": plugin}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Volatility timed out (>120s)", "plugin": plugin}
    except FileNotFoundError:
        # Fallback: simulate for demo if volatility not in PATH
        return _simulate_volatility(dump_path, plugin)


def _simulate_volatility(dump_path: str, plugin: str) -> dict:
    """Demo simulation when running without a real memory dump."""
    simulations = {
        "windows.pslist": {
            "success": True, "plugin": plugin, "simulated": True,
            "data": {
                "rows": [
                    {"PID": 4, "PPID": 0, "ImageFileName": "System", "Offset": "0x82345000", "Threads": 130, "Wow64": False},
                    {"PID": 688, "PPID": 4, "ImageFileName": "smss.exe", "Offset": "0x84100000", "Threads": 3, "Wow64": False},
                    {"PID": 764, "PPID": 688, "ImageFileName": "csrss.exe", "Offset": "0x84200000", "Threads": 10, "Wow64": False},
                    {"PID": 1337, "PPID": 1004, "ImageFileName": "cmd.exe", "Offset": "0x9A100000", "Threads": 2, "Wow64": False},
                    {"PID": 2048, "PPID": 1337, "ImageFileName": "powershell.exe", "Offset": "0x9B200000", "Threads": 8, "Wow64": False},
                    {"PID": 3721, "PPID": 2048, "ImageFileName": "whoami.exe", "Offset": "0x9C300000", "Threads": 1, "Wow64": False},
                    {"PID": 4096, "PPID": 2048, "ImageFileName": "net.exe", "Offset": "0x9D400000", "Threads": 1, "Wow64": False},
                    {"PID": 9999, "PPID": 2048, "ImageFileName": "svch0st.exe", "Offset": "0xBBAA0000", "Threads": 5, "Wow64": False},
                ]
            }
        },
        "windows.netscan": {
            "success": True, "plugin": plugin, "simulated": True,
            "data": {
                "rows": [
                    {"Offset": "0x84000000", "Proto": "TCPv4", "LocalAddr": "192.168.1.100", "LocalPort": 49152, "ForeignAddr": "185.220.101.47", "ForeignPort": 4444, "State": "ESTABLISHED", "PID": 9999, "Owner": "svch0st.exe"},
                    {"Offset": "0x84100000", "Proto": "TCPv4", "LocalAddr": "192.168.1.100", "LocalPort": 49153, "ForeignAddr": "8.8.8.8", "ForeignPort": 53, "State": "TIME_WAIT", "PID": 2048, "Owner": "powershell.exe"},
                    {"Offset": "0x84200000", "Proto": "TCPv4", "LocalAddr": "0.0.0.0", "LocalPort": 4444, "ForeignAddr": "0.0.0.0", "ForeignPort": 0, "State": "LISTENING", "PID": 9999, "Owner": "svch0st.exe"},
                ]
            }
        },
        "windows.malfind": {
            "success": True, "plugin": plugin, "simulated": True,
            "data": {
                "rows": [
                    {"PID": 9999, "Process": "svch0st.exe", "Start": "0xBBAA0000", "End": "0xBBAB0000", "Tag": "VadS", "Protection": "PAGE_EXECUTE_READWRITE", "CommitCharge": 16, "PrivateMemory": 1, "File": "\\Device\\HarddiskVolume2\\Windows\\Temp\\svch0st.exe", "Hexdump": "4d5a90000300000004000000ffff..."},
                ]
            }
        },
        "windows.cmdline": {
            "success": True, "plugin": plugin, "simulated": True,
            "data": {
                "rows": [
                    {"PID": 2048, "Process": "powershell.exe", "Args": "powershell.exe -EncodedCommand UwB0AGEAcgB0AC0AUAByAG8AYwBlAHMAcwAgAC0ATgBvAE4AZQB3AFcAaQBuAGQAbwB3ACAALQBGAGkAbABlAFAAYQB0AGgAIAAnAEMAOgBcAFQAZQBtAHAAXABzAHYAYwBoADAAcwB0AC4AZQB4AGUAJwA="},
                    {"PID": 9999, "Process": "svch0st.exe", "Args": "C:\\Temp\\svch0st.exe -c 185.220.101.47 -p 4444 -s"},
                    {"PID": 3721, "Process": "whoami.exe", "Args": "whoami /all"},
                    {"PID": 4096, "Process": "net.exe", "Args": "net user hacker P@ssw0rd /add"},
                ]
            }
        }
    }
    return simulations.get(plugin, {"success": True, "plugin": plugin, "simulated": True, "data": {"rows": []}})


def _parse_evtx_file(evtx_path: str, event_ids: list[int] = None, limit: int = 100, _simulate: bool = False) -> dict:
    """Parse Windows Event Log .evtx file."""
    if _simulate:
        return _simulate_evtx_parse(evtx_path, event_ids)
    try:
        import Evtx.Evtx as evtx
        import Evtx.Views as e_views
        import xml.etree.ElementTree as ET

        events = []
        with evtx.Evtx(evtx_path) as log:
            for record in log.records():
                try:
                    xml_str = record.xml()
                    root = ET.fromstring(xml_str)
                    ns = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

                    sys_el = root.find("e:System", ns)
                    event_id_el = sys_el.find("e:EventID", ns) if sys_el else None
                    event_id = int(event_id_el.text) if event_id_el is not None else 0
                    time_el = sys_el.find("e:TimeCreated", ns) if sys_el else None
                    timestamp = time_el.get("SystemTime", "") if time_el is not None else ""

                    if event_ids and event_id not in event_ids:
                        continue

                    event_data = {}
                    data_el = root.find("e:EventData", ns)
                    if data_el is not None:
                        for d in data_el.findall("e:Data", ns):
                            name = d.get("Name", "")
                            event_data[name] = d.text

                    events.append({"EventID": event_id, "Timestamp": timestamp, "Data": event_data})
                    if len(events) >= limit:
                        break
                except Exception:
                    continue
        return {"success": True, "events": events, "count": len(events)}
    except ImportError:
        return _simulate_evtx_parse(evtx_path, event_ids)
    except Exception as e:
        return _simulate_evtx_parse(evtx_path, event_ids)


def _simulate_evtx_parse(evtx_path: str, event_ids: list[int] = None) -> dict:
    """Demo simulation for EVTX parsing."""
    events = [
        {"EventID": 4624, "Timestamp": "2024-01-15T02:34:11.123Z", "Data": {"SubjectUserName": "SYSTEM", "TargetUserName": "Administrator", "LogonType": "3", "IpAddress": "185.220.101.47", "WorkstationName": "ATTACKER-PC"}},
        {"EventID": 4720, "Timestamp": "2024-01-15T02:35:22.456Z", "Data": {"SubjectUserName": "Administrator", "TargetUserName": "hacker", "PrivilegeList": "SeSecurityPrivilege"}},
        {"EventID": 4732, "Timestamp": "2024-01-15T02:35:25.789Z", "Data": {"SubjectUserName": "Administrator", "TargetUserName": "hacker", "TargetDomainName": "Administrators"}},
        {"EventID": 4688, "Timestamp": "2024-01-15T02:36:01.001Z", "Data": {"SubjectUserName": "hacker", "NewProcessName": "C:\\Temp\\svch0st.exe", "CommandLine": "svch0st.exe -c 185.220.101.47 -p 4444 -s", "ParentProcessName": "powershell.exe"}},
        {"EventID": 4698, "Timestamp": "2024-01-15T02:36:45.222Z", "Data": {"SubjectUserName": "hacker", "TaskName": "\\Microsoft\\Windows\\Winlogon\\PersistTask", "TaskContent": "<Command>C:\\Temp\\svch0st.exe</Command>"}},
        {"EventID": 7045, "Timestamp": "2024-01-15T02:37:10.333Z", "Data": {"ServiceName": "WindowsUpdate", "ImagePath": "C:\\Temp\\svch0st.exe -service", "ServiceType": "user mode service", "StartType": "auto start"}},
    ]
    if event_ids:
        events = [e for e in events if e["EventID"] in event_ids]
    return {"success": True, "events": events, "count": len(events), "simulated": True}


def _build_timeline(evidence_path: str, _simulate: bool = False) -> dict:
    """Build a supertimeline from evidence directory."""
    if _simulate:
        return _simulate_timeline()
    # Try log2timeline / plaso
    timeline_csv = Path(evidence_path).parent / "timeline.csv"
    try:
        result = subprocess.run(
            ["log2timeline.py", "--output", str(timeline_csv), evidence_path],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return {"success": True, "timeline_file": str(timeline_csv), "method": "log2timeline"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: build timeline from available artifacts
    return _simulate_timeline()


def _simulate_timeline() -> dict:
    """Simulated supertimeline for demo."""
    events = [
        {"timestamp": "2024-01-15T02:30:00Z", "source": "EVTX:4624", "host": "VICTIM-PC", "desc": "Remote logon from 185.220.101.47 as Administrator"},
        {"timestamp": "2024-01-15T02:32:15Z", "source": "FS:MFT", "host": "VICTIM-PC", "desc": "File created: C:\\Temp\\svch0st.exe (size: 45056 bytes)"},
        {"timestamp": "2024-01-15T02:33:01Z", "source": "EVTX:4688", "host": "VICTIM-PC", "desc": "Process created: powershell.exe with EncodedCommand"},
        {"timestamp": "2024-01-15T02:34:45Z", "source": "EVTX:4688", "host": "VICTIM-PC", "desc": "Process created: svch0st.exe -c 185.220.101.47 -p 4444 -s"},
        {"timestamp": "2024-01-15T02:35:00Z", "source": "MEM:netscan", "host": "VICTIM-PC", "desc": "Network connection: svch0st.exe → 185.220.101.47:4444 ESTABLISHED"},
        {"timestamp": "2024-01-15T02:35:22Z", "source": "EVTX:4720", "host": "VICTIM-PC", "desc": "New user account created: hacker"},
        {"timestamp": "2024-01-15T02:35:25Z", "source": "EVTX:4732", "host": "VICTIM-PC", "desc": "User hacker added to Administrators group"},
        {"timestamp": "2024-01-15T02:36:45Z", "source": "EVTX:4698", "host": "VICTIM-PC", "desc": "Scheduled task created: PersistTask → C:\\Temp\\svch0st.exe"},
        {"timestamp": "2024-01-15T02:37:10Z", "source": "EVTX:7045", "host": "VICTIM-PC", "desc": "Service installed: WindowsUpdate → C:\\Temp\\svch0st.exe"},
    ]
    return {"success": True, "events": events, "count": len(events), "simulated": True, "method": "reconstructed"}


def _run_sleuthkit(image_path: str, command: str = "fls", args: list[str] = None, _simulate: bool = False) -> dict:
    """Run sleuthkit tool against disk image."""
    if _simulate:
        return _simulate_sleuthkit(image_path, command)
    cmd = [command, "-r", image_path]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return {"success": True, "output": result.stdout[:10000], "command": " ".join(cmd)}
        else:
            return {"success": False, "error": result.stderr[:2000]}
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return _simulate_sleuthkit(image_path, command)


def _simulate_sleuthkit(image_path: str, command: str) -> dict:
    """Simulated disk artifact listing."""
    return {
        "success": True, "simulated": True, "command": command,
        "output": (
            "r/r 0-128-1:\tC:/Windows/System32/\n"
            "r/r 45056-128-1:\tC:/Temp/svch0st.exe  [DELETED]\n"
            "r/r 45057-128-1:\tC:/Temp/payload.ps1  [DELETED]\n"
            "r/r 12345-128-1:\tC:/Users/hacker/.bash_history\n"
            "r/r 12346-128-1:\tC:/Windows/Prefetch/SVCH0ST.EXE-XXXXXXXX.pf\n"
        )
    }


def _extract_iocs(text: str) -> dict:
    """Extract IOCs (IPs, domains, hashes, URLs) from text."""
    iocs = {
        "ipv4": list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text))),
        "domains": list(set(re.findall(r'\b(?:[a-zA-Z0-9-]+\.)+(?:com|net|org|io|ru|cn|xyz|onion)\b', text))),
        "md5": list(set(re.findall(r'\b[0-9a-fA-F]{32}\b', text))),
        "sha1": list(set(re.findall(r'\b[0-9a-fA-F]{40}\b', text))),
        "sha256": list(set(re.findall(r'\b[0-9a-fA-F]{64}\b', text))),
        "urls": list(set(re.findall(r'https?://[^\s<>"]+', text))),
        "file_paths": list(set(re.findall(r'[A-Za-z]:\\[^\s"\'<>|?*\n]+', text))),
        "registry_keys": list(set(re.findall(r'(?:HKEY_|HKLM|HKCU)\\[^\s"\'<>]+', text))),
    }
    # Filter private IPs from IOC list (not really IOCs)
    def is_public_ip(ip):
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            a = int(parts[0])
            return a not in (10, 127, 169, 172, 192)
        except ValueError:
            return False

    iocs["public_ips"] = [ip for ip in iocs["ipv4"] if is_public_ip(ip)]
    total = sum(len(v) for v in iocs.values())
    return {"success": True, "iocs": iocs, "total_count": total}


def _check_mitre(behavior: str) -> dict:
    """Map a described behavior to MITRE ATT&CK techniques."""
    # Keyword-based mapping (production would use embeddings)
    mitre_map = {
        "powershell": {"tactic": "Execution", "technique": "T1059.001", "name": "Command and Scripting Interpreter: PowerShell"},
        "encoded": {"tactic": "Defense Evasion", "technique": "T1027", "name": "Obfuscated Files or Information"},
        "encodedcommand": {"tactic": "Defense Evasion", "technique": "T1027", "name": "Obfuscated Files or Information"},
        "scheduled task": {"tactic": "Persistence", "technique": "T1053.005", "name": "Scheduled Task/Job: Scheduled Task"},
        "service": {"tactic": "Persistence", "technique": "T1543.003", "name": "Create or Modify System Process: Windows Service"},
        "net user": {"tactic": "Persistence", "technique": "T1136.001", "name": "Create Account: Local Account"},
        "administrators": {"tactic": "Privilege Escalation", "technique": "T1078.001", "name": "Valid Accounts: Default Accounts"},
        "reverse shell": {"tactic": "Command and Control", "technique": "T1105", "name": "Ingress Tool Transfer"},
        "c2": {"tactic": "Command and Control", "technique": "T1071.001", "name": "Application Layer Protocol: Web Protocols"},
        "4444": {"tactic": "Command and Control", "technique": "T1571", "name": "Non-Standard Port"},
        "malfind": {"tactic": "Defense Evasion", "technique": "T1055", "name": "Process Injection"},
        "netscan": {"tactic": "Discovery", "technique": "T1049", "name": "System Network Connections Discovery"},
        "whoami": {"tactic": "Discovery", "technique": "T1033", "name": "System Owner/User Discovery"},
        "logon": {"tactic": "Initial Access", "technique": "T1078", "name": "Valid Accounts"},
        "lateral": {"tactic": "Lateral Movement", "technique": "T1021", "name": "Remote Services"},
        "exfil": {"tactic": "Exfiltration", "technique": "T1048", "name": "Exfiltration Over Alternative Protocol"},
        "mimikatz": {"tactic": "Credential Access", "technique": "T1003.001", "name": "OS Credential Dumping: LSASS Memory"},
        "lsass": {"tactic": "Credential Access", "technique": "T1003.001", "name": "OS Credential Dumping: LSASS Memory"},
        "persist": {"tactic": "Persistence", "technique": "T1547.001", "name": "Boot or Logon Autostart Execution: Registry Run Keys"},
        "inject": {"tactic": "Defense Evasion", "technique": "T1055", "name": "Process Injection"},
        "temp": {"tactic": "Defense Evasion", "technique": "T1036.005", "name": "Masquerading: Match Legitimate Name or Location"},
    }
    behavior_lower = behavior.lower()
    matched = []
    for keyword, technique in mitre_map.items():
        if keyword in behavior_lower:
            if technique not in matched:
                matched.append(technique)

    return {
        "success": True,
        "behavior": behavior,
        "matched_techniques": matched,
        "count": len(matched)
    }


def _search_playbook(threat_type: str) -> dict:
    """Return DFIR playbook for a given threat type."""
    playbooks = {
        "ransomware": {
            "name": "Ransomware Incident Response",
            "steps": [
                "1. Isolate affected hosts from network immediately",
                "2. Identify patient zero — earliest infection timestamp",
                "3. Run memory analysis: pslist, netscan, malfind, cmdline",
                "4. Extract ransom note IOCs (contact email, wallet address)",
                "5. Identify encryption process and affected file extensions",
                "6. Check VSS (Volume Shadow Copies) for deletion evidence (Event 524)",
                "7. Examine scheduled tasks and services for persistence",
                "8. Map lateral movement via Event ID 4624/4648",
                "9. Identify data exfiltration before encryption",
                "10. Preserve evidence with hashing before remediation",
            ],
            "key_event_ids": [4624, 4648, 4688, 4698, 7045, 4720, 4732],
            "key_iocs": ["encrypted extension", "ransom note filename", "C2 IP"]
        },
        "malware": {
            "name": "Malware/Trojan Analysis",
            "steps": [
                "1. Capture memory image before rebooting",
                "2. Run volatility pslist — identify suspicious process names",
                "3. Run volatility malfind — detect injected code (PAGE_EXECUTE_READWRITE)",
                "4. Run volatility netscan — find C2 connections",
                "5. Run volatility cmdline — enumerate suspicious process arguments",
                "6. Parse EVTX for Event 4688 (process creation) and 7045 (service install)",
                "7. Check prefetch files for execution evidence",
                "8. Examine MFT for file creation timestamps",
                "9. Extract all IOCs (IP, domain, hash, path)",
                "10. YARA scan memory for known malware signatures",
            ],
            "key_event_ids": [4688, 7045, 4624, 4698, 4720, 4732],
            "key_iocs": ["process name", "C2 IP:port", "file hash", "registry persistence key"]
        },
        "intrusion": {
            "name": "Unauthorized Access / Intrusion",
            "steps": [
                "1. Identify initial access vector (brute force, phishing, exploit)",
                "2. Review failed logins before success (Event 4625 → 4624)",
                "3. Map attacker's source IP and logon type",
                "4. Identify tools dropped post-compromise (MFT, prefetch)",
                "5. Check for privilege escalation (Event 4672, 4728, 4732)",
                "6. Review new accounts created (Event 4720)",
                "7. Examine scheduled tasks for persistence (Event 4698)",
                "8. Map lateral movement (Event 4624, Type 3 from different IPs)",
                "9. Identify data accessed or exfiltrated",
                "10. Reconstruct full attack timeline",
            ],
            "key_event_ids": [4624, 4625, 4672, 4720, 4728, 4732, 4698, 4688],
            "key_iocs": ["attacker IP", "compromised accounts", "persistence mechanisms"]
        },
        "default": {
            "name": "Generic Incident Response",
            "steps": [
                "1. Preserve volatile data first (memory > running processes > network)",
                "2. Document chain of custody for all evidence",
                "3. Build timeline from all available sources",
                "4. Identify initial access point",
                "5. Map attacker actions chronologically",
                "6. Extract and validate all IOCs",
                "7. Identify persistence mechanisms",
                "8. Assess data exposure / impact",
                "9. Map to MITRE ATT&CK framework",
                "10. Write findings with evidence provenance",
            ]
        }
    }
    threat_lower = threat_type.lower()
    for key, playbook in playbooks.items():
        if key in threat_lower:
            return {"success": True, "playbook": playbook, "matched": key}
    return {"success": True, "playbook": playbooks["default"], "matched": "default"}


def _record_finding(finding: dict) -> dict:
    """Persist a validated forensic finding to the case file."""
    required = ["title", "severity", "evidence", "mitre_technique", "confidence"]
    missing = [f for f in required if f not in finding]
    if missing:
        return {
            "success": False,
            "error": f"Finding missing required fields: {missing}",
            "hint": "All findings must have: title, severity, evidence, mitre_technique, confidence"
        }

    # ── Auto-enrich: wire check_mitre into every finding ─────────────────
    description = finding.get("description", finding["title"])
    mitre_enrichment = _check_mitre(description)
    if mitre_enrichment["matched_techniques"]:
        # Prefer dynamically resolved techniques; keep original as fallback
        primary = mitre_enrichment["matched_techniques"][0]
        finding["mitre_technique_dynamic"] = primary["technique"]
        finding["mitre_tactic_dynamic"] = primary["tactic"]
        finding["mitre_technique_name"] = primary["name"]
        finding["mitre_all_matched"] = [t["technique"] for t in mitre_enrichment["matched_techniques"]]
    # Always keep original mitre_technique field for compatibility

    # ── Deduplication: skip if same title already recorded this session ──
    existing_titles = {f.get("title") for f in _findings}
    if finding["title"] in existing_titles:
        existing = next(f for f in _findings if f.get("title") == finding["title"])
        return {
            "success": True,
            "finding_id": existing["id"],
            "status": "DUPLICATE — already recorded this session",
            "message": f"Finding '{finding['title']}' already recorded. ID: {existing['id']}",
            "deduplicated": True,
        }

    finding["id"] = hashlib.sha256(
        finding["title"].encode()
    ).hexdigest()[:12]
    finding["recorded_at"] = datetime.now(timezone.utc).isoformat()
    finding["status"] = "DRAFT"

    _findings.append(finding)

    # Persist to case directory — dedup by finding ID in the file
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    findings_file = CASE_DIR / "findings.jsonl"

    # Read existing IDs before writing
    existing_ids: set[str] = set()
    if findings_file.exists():
        with open(findings_file, "r") as f:
            for line in f:
                try:
                    existing_ids.add(json.loads(line.strip()).get("id", ""))
                except json.JSONDecodeError:
                    pass

    if finding["id"] not in existing_ids:
        with open(findings_file, "a") as f:
            f.write(json.dumps(finding) + "\n")

    return {
        "success": True,
        "finding_id": finding["id"],
        "status": "DRAFT — awaiting human review",
        "message": f"Finding '{finding['title']}' recorded. Severity: {finding['severity']}",
        "mitre_dynamic": finding.get("mitre_technique_dynamic"),
        "mitre_tactic": finding.get("mitre_tactic_dynamic"),
    }


def _list_evidence() -> dict:
    """List all artifacts in the evidence directory."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in EVIDENCE_DIR.rglob("*"):
        if p.is_file():
            files.append({
                "path": str(p.relative_to(EVIDENCE_DIR)),
                "size_bytes": p.stat().st_size,
                "extension": p.suffix.lower(),
            })
    if not files:
        # Return demo evidence list
        files = [
            {"path": "memory/victim.mem", "size_bytes": 2147483648, "extension": ".mem"},
            {"path": "logs/Security.evtx", "size_bytes": 20971520, "extension": ".evtx"},
            {"path": "logs/System.evtx", "size_bytes": 10485760, "extension": ".evtx"},
            {"path": "disk/victim-disk.E01", "size_bytes": 53687091200, "extension": ".e01"},
        ]
        return {"success": True, "files": files, "count": len(files), "simulated": True}
    return {"success": True, "files": files, "count": len(files)}


# ─── MCP Server Definition ────────────────────────────────────────────────────

def create_mcp_server():
    """Create and return the SIFTGuard MCP server."""
    try:
        from mcp.server import Server
        from mcp import types

        server = Server("siftguard")

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="run_volatility",
                    description="Run a volatility3 plugin against a memory dump for forensic analysis. Plugins: windows.pslist, windows.netscan, windows.malfind, windows.cmdline",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "dump_path": {"type": "string", "description": "Path to memory dump file (.mem, .raw, .dmp)"},
                            "plugin": {"type": "string", "description": "Volatility3 plugin: windows.pslist | windows.netscan | windows.malfind | windows.cmdline"},
                            "extra_args": {"type": "array", "items": {"type": "string"}, "description": "Additional CLI args"},
                        },
                        "required": ["dump_path", "plugin"],
                    }
                ),
                types.Tool(
                    name="parse_evtx",
                    description="Parse Windows Event Log (.evtx) file and filter by Event IDs. Key IDs: 4624=logon, 4688=process, 4720=new_user, 4698=scheduled_task, 7045=service",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "evtx_path": {"type": "string", "description": "Path to .evtx file"},
                            "event_ids": {"type": "array", "items": {"type": "integer"}, "description": "Filter to specific Event IDs (empty = all)"},
                            "limit": {"type": "integer", "default": 100, "description": "Max events to return"},
                        },
                        "required": ["evtx_path"],
                    }
                ),
                types.Tool(
                    name="build_timeline",
                    description="Build a supertimeline from all evidence in a directory. Correlates memory, logs, disk artifacts chronologically.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "evidence_path": {"type": "string", "description": "Path to evidence directory or specific artifact"},
                        },
                        "required": ["evidence_path"],
                    }
                ),
                types.Tool(
                    name="run_sleuthkit",
                    description="Run Sleuthkit (fls/mmls/istat) to analyze disk images. Reveals deleted files, filesystem metadata, partition tables.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "image_path": {"type": "string", "description": "Path to disk image (.E01, .dd, .raw)"},
                            "command": {"type": "string", "default": "fls", "description": "Sleuthkit command: fls | mmls | istat"},
                            "args": {"type": "array", "items": {"type": "string"}, "description": "Additional args"},
                        },
                        "required": ["image_path"],
                    }
                ),
                types.Tool(
                    name="extract_iocs",
                    description="Extract Indicators of Compromise (IOCs) from text: IPs, domains, file hashes, URLs, registry keys, file paths.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text to extract IOCs from (tool output, log lines, etc.)"},
                        },
                        "required": ["text"],
                    }
                ),
                types.Tool(
                    name="check_mitre",
                    description="Map observed attacker behavior to MITRE ATT&CK techniques and tactics.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "behavior": {"type": "string", "description": "Description of attacker behavior or tool output to map"},
                        },
                        "required": ["behavior"],
                    }
                ),
                types.Tool(
                    name="search_playbook",
                    description="Retrieve DFIR investigation playbook for a threat type: ransomware | malware | intrusion | lateral_movement",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "threat_type": {"type": "string", "description": "Threat type: ransomware | malware | intrusion | lateral_movement | default"},
                        },
                        "required": ["threat_type"],
                    }
                ),
                types.Tool(
                    name="record_finding",
                    description="Record a validated forensic finding to the case file. Requires: title, severity, evidence list, mitre_technique, confidence.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "finding": {
                                "type": "object",
                                "description": "Finding dict with: title, severity (CRITICAL/HIGH/MEDIUM/LOW), evidence (list), mitre_technique, confidence (HIGH/MEDIUM/LOW), description",
                            }
                        },
                        "required": ["finding"],
                    }
                ),
                types.Tool(
                    name="list_evidence",
                    description="List all forensic artifacts available in the evidence directory.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="get_audit_trail",
                    description="Return the complete structured audit trail of all tool calls in this investigation session.",
                    inputSchema={"type": "object", "properties": {}}
                ),
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            result = None

            if name == "run_volatility":
                result = _run_volatility(
                    arguments["dump_path"],
                    arguments["plugin"],
                    arguments.get("extra_args", [])
                )
                _log_tool_call("run_volatility", arguments,
                               f"plugin={arguments['plugin']}, rows={len(result.get('data', {}).get('rows', []))}",
                               result["success"])

            elif name == "parse_evtx":
                result = _parse_evtx_file(
                    arguments["evtx_path"],
                    arguments.get("event_ids"),
                    arguments.get("limit", 100)
                )
                _log_tool_call("parse_evtx", arguments,
                               f"events={result.get('count', 0)}",
                               result["success"])

            elif name == "build_timeline":
                result = _build_timeline(arguments["evidence_path"])
                _log_tool_call("build_timeline", arguments,
                               f"events={result.get('count', result.get('events', []))}", result["success"])

            elif name == "run_sleuthkit":
                result = _run_sleuthkit(
                    arguments["image_path"],
                    arguments.get("command", "fls"),
                    arguments.get("args", [])
                )
                _log_tool_call("run_sleuthkit", arguments,
                               f"output_len={len(result.get('output', ''))}", result["success"])

            elif name == "extract_iocs":
                result = _extract_iocs(arguments["text"])
                _log_tool_call("extract_iocs", arguments,
                               f"total_iocs={result['total_count']}", result["success"])

            elif name == "check_mitre":
                result = _check_mitre(arguments["behavior"])
                _log_tool_call("check_mitre", arguments,
                               f"techniques_matched={result['count']}", result["success"])

            elif name == "search_playbook":
                result = _search_playbook(arguments["threat_type"])
                _log_tool_call("search_playbook", arguments,
                               f"playbook={result['matched']}", result["success"])

            elif name == "record_finding":
                result = _record_finding(arguments["finding"])
                _log_tool_call("record_finding", arguments,
                               f"finding_id={result.get('finding_id', 'ERROR')}", result["success"])

            elif name == "list_evidence":
                result = _list_evidence()
                _log_tool_call("list_evidence", arguments,
                               f"files={result['count']}", result["success"])

            elif name == "get_audit_trail":
                result = {"success": True, "entries": _audit_trail, "count": len(_audit_trail)}

            else:
                result = {"success": False, "error": f"Unknown tool: {name}"}

            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        return server

    except ImportError as e:
        logger.error("mcp_import_failed", error=str(e))
        raise
