# SIFTGuard — Dataset Documentation

## Overview

SIFTGuard operates against forensic evidence datasets in standard DFIR formats. This document describes the dataset types supported, the simulated dataset used in demo mode, and guidance for investigators using real evidence.

---

## Supported Evidence Formats

| Format | Extension | Tool Used | Description |
|--------|-----------|-----------|-------------|
| Windows Memory Dump | `.mem`, `.raw`, `.dmp` | Volatility3 | Full physical memory captures from Windows systems |
| Windows Event Log | `.evtx` | python-evtx | Windows Security, System, Application event logs |
| Disk Image (Expert Witness) | `.E01`, `.Ex01` | Sleuthkit (`fls`, `mmls`) | Encase forensic disk images |
| Raw Disk Image | `.dd`, `.img`, `.iso` | Sleuthkit | Raw bit-for-bit disk copies |
| Network Capture | `.pcap`, `.pcapng` | (planned) | Packet captures for network forensics |

---

## Demo Dataset (Simulation Mode)

When real evidence files are absent, SIFTGuard activates **forensic simulation mode** — generating realistic DFIR artifacts that mirror a real intrusion scenario. This allows the full pipeline to run and be evaluated without requiring evidence files.

### Simulated Scenario: `APT Lateral Movement + Persistence`

**Victim Environment:**
- OS: Windows Server 2019
- Hostname: `CORP-WIN-SRV01`
- Incident Date: 2024-01-15

**Simulated Evidence Files:**

```
data/evidence/
├── memory/
│   └── victim.mem          (2 GB simulated Windows memory dump)
├── logs/
│   ├── Security.evtx       (20 MB — 11,500+ events)
│   └── System.evtx         (10 MB — 6,000+ events)
└── disk/
    └── victim-disk.E01     (50 GB simulated disk image)
```

### Simulated Forensic Findings

**Memory Analysis** (via `run_volatility` simulation):
```
PID   PPID  Name             Create Time
----  ----  ---------------  -------------------
4     0     System           2024-01-15 00:00:01
1032  4     smss.exe         2024-01-15 00:00:02
...
3847  2912  svch0st.exe      2024-01-15 02:31:15  ← MALICIOUS (typosquatted svchost)
3851  3847  cmd.exe          2024-01-15 02:31:22  ← Spawned by malware
```

**Event Log Findings** (via `parse_evtx` simulation):

| Event ID | Timestamp | Description | Severity |
|----------|-----------|-------------|----------|
| 4624 | 2024-01-15 02:30:00Z | Logon Type 3 from 185.220.101.47 as Administrator | HIGH |
| 4720 | 2024-01-15 02:33:00Z | Account Created: `hacker` | CRITICAL |
| 4722 | 2024-01-15 02:33:01Z | Account `hacker` Enabled | CRITICAL |
| 7045 | 2024-01-15 02:35:00Z | New Service Installed: `WindowsUpdate` → `C:\Temp\svch0st.exe` | CRITICAL |
| 4698 | 2024-01-15 02:37:10Z | Scheduled Task Created: `PersistTask` | HIGH |

**Disk Analysis** (via `run_sleuthkit` simulation):
```
r/r 12345: $MFT
r/r 23456: Windows/System32/svch0st.exe   ← Malicious binary (typosquatted)
r/r 23457: Temp/svch0st.exe               ← Dropped payload
r/r 34567: Users/hacker/NTUSER.DAT        ← Backdoor account profile
```

---

## Indicators of Compromise (IOCs)

| Type | Value | Source |
|------|-------|--------|
| IP Address (C2) | `185.220.101.47` | Event Log 4624, Memory |
| File Path | `C:\Temp\svch0st.exe` | Disk, Memory, Service Registry |
| Account | `hacker` | Event Log 4720/4722 |
| Service Name | `WindowsUpdate` (malicious) | Event Log 7045 |
| Scheduled Task | `PersistTask` | Event Log 4698 |
| Process | `svch0st.exe` (PID 3847) | Memory pslist |

---

## MITRE ATT&CK Mapping

| Technique | ID | Tactic | Evidence |
|-----------|-----|--------|---------|
| Valid Accounts | T1078 | Initial Access | Admin login from external IP |
| Create Account | T1136.001 | Persistence | `hacker` account creation |
| New Service | T1543.003 | Persistence | `WindowsUpdate` service |
| Scheduled Task | T1053.005 | Persistence | `PersistTask` |
| Process Injection | T1055 | Defense Evasion | `svch0st.exe` typosquatting |
| Remote Services | T1021 | Lateral Movement | Type 3 logon |

---

## Using Real Evidence

To run SIFTGuard against real forensic evidence:

```
data/evidence/
├── memory/
│   └── <hostname>.mem          # Windows memory dump (WinPmem, DumpIt, etc.)
├── logs/
│   ├── Security.evtx           # Export from Windows Event Viewer
│   ├── System.evtx
│   └── Application.evtx
└── disk/
    └── <hostname>-disk.E01     # FTK Imager or dd image
```

SIFTGuard auto-detects real files and uses live Volatility3/Sleuthkit analysis instead of simulation.

---

## Dataset Size & Scope

| Metric | Value |
|--------|-------|
| Simulated Events | ~11,500 (Security EVTX) + ~6,000 (System EVTX) |
| Timeline Datapoints | 9 reconstructed events |
| IOCs Extracted | 3 (1 IP, 1 file path, 1 account) |
| MITRE Techniques Mapped | 6 |
| Evidence Coverage | Memory + Logs + Disk (full triage) |
