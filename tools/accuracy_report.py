"""
SIFTGuard — Accuracy Report Generator
=======================================
Produces the required FIND EVIL! accuracy report:
- True Positives / False Positives / False Negatives
- Per-technique accuracy
- Tool call success rate
- Self-correction effectiveness
- MITRE ATT&CK coverage
"""

import json
from pathlib import Path
from datetime import datetime, timezone


# Ground truth for the SANS FIND EVIL dataset
# (populated from dataset documentation)
GROUND_TRUTH = {
    "techniques": [
        {"technique": "T1078", "name": "Valid Accounts (Remote Logon)", "present": True},
        {"technique": "T1059.001", "name": "PowerShell Execution", "present": True},
        {"technique": "T1027", "name": "Encoded Command Obfuscation", "present": True},
        {"technique": "T1036.005", "name": "Process Masquerading (svch0st.exe)", "present": True},
        {"technique": "T1055", "name": "Process Injection", "present": True},
        {"technique": "T1571", "name": "Non-Standard Port C2 (4444)", "present": True},
        {"technique": "T1136.001", "name": "Local Account Creation", "present": True},
        {"technique": "T1053.005", "name": "Scheduled Task Persistence", "present": True},
        {"technique": "T1543.003", "name": "Malicious Service Persistence", "present": True},
        {"technique": "T1070.004", "name": "File Deletion (Anti-Forensics)", "present": True},
        {"technique": "T1033", "name": "System Discovery (whoami)", "present": True},
        {"technique": "T1049", "name": "Network Connections Discovery", "present": True},
    ],
    "iocs": {
        "ips": ["185.220.101.47"],
        "processes": ["svch0st.exe"],
        "accounts": ["hacker"],
        "files": ["C:\\Temp\\svch0st.exe", "C:\\Temp\\payload.ps1"],
        "ports": [4444],
    },
    "key_events": [4624, 4688, 4720, 4732, 4698, 7045]
}


def generate_accuracy_report(investigation_report: dict, output_path: str = None) -> dict:
    """
    Compare investigation findings against ground truth to produce accuracy metrics.

    Args:
        investigation_report: Output from SIFTGuardOrchestrator.run()
        output_path: Where to save the report (optional)

    Returns:
        Accuracy report dict
    """
    analysis = investigation_report.get("stages", {}).get("analysis", {})
    findings = investigation_report.get("stages", {}).get("findings", {})
    audit = investigation_report.get("audit", {})

    detected_mitre = {
        t["technique"] for t in analysis.get("mitre_techniques", [])
    }
    detected_iocs = analysis.get("iocs", {})

    # ── MITRE ATT&CK Accuracy ──────────────────────────────────────────
    true_techniques = {t["technique"] for t in GROUND_TRUTH["techniques"] if t["present"]}

    tp_techniques = detected_mitre & true_techniques
    fp_techniques = detected_mitre - true_techniques
    fn_techniques = true_techniques - detected_mitre

    technique_precision = len(tp_techniques) / len(detected_mitre) if detected_mitre else 0
    technique_recall = len(tp_techniques) / len(true_techniques) if true_techniques else 0
    technique_f1 = (
        2 * technique_precision * technique_recall / (technique_precision + technique_recall)
        if (technique_precision + technique_recall) > 0 else 0
    )

    # ── IOC Accuracy ───────────────────────────────────────────────────
    detected_ips = set(detected_iocs.get("public_ips", []) + detected_iocs.get("ipv4", []))
    gt_ips = set(GROUND_TRUTH["iocs"]["ips"])
    ioc_ip_accuracy = len(detected_ips & gt_ips) / len(gt_ips) if gt_ips else 0

    detected_paths = set(detected_iocs.get("file_paths", []))
    gt_paths = set(GROUND_TRUTH["iocs"]["files"])
    ioc_path_accuracy = len(detected_paths & gt_paths) / len(gt_paths) if gt_paths else 0

    # ── Tool Performance ───────────────────────────────────────────────
    tool_calls = audit.get("tool_calls", [])
    successful_tools = [t for t in tool_calls if t.get("success")]
    tool_success_rate = len(successful_tools) / len(tool_calls) if tool_calls else 1.0

    # ── Self-Correction Effectiveness ─────────────────────────────────
    corrections = audit.get("correction_log", [])
    correction_successes = [c for c in corrections if c.get("outcome") == "SUCCESS"]
    correction_rate = len(correction_successes) / len(corrections) if corrections else 1.0

    # ── Overall Score ─────────────────────────────────────────────────
    overall_score = (
        technique_recall * 0.4 +       # Finding all real techniques
        technique_precision * 0.2 +    # Not over-reporting
        ioc_ip_accuracy * 0.2 +        # C2 IP detection
        ioc_path_accuracy * 0.1 +      # Malware path detection
        tool_success_rate * 0.1        # Tool reliability
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_id": investigation_report.get("session_id"),

        "executive_summary": {
            "overall_accuracy_score": round(overall_score * 100, 1),
            "mitre_techniques_detected": len(detected_mitre),
            "mitre_techniques_in_ground_truth": len(true_techniques),
            "true_positives": len(tp_techniques),
            "false_positives": len(fp_techniques),
            "false_negatives": len(fn_techniques),
            "precision": round(technique_precision * 100, 1),
            "recall": round(technique_recall * 100, 1),
            "f1_score": round(technique_f1 * 100, 1),
        },

        "mitre_attack_results": {
            "true_positives": [
                next(t for t in GROUND_TRUTH["techniques"] if t["technique"] == tid)
                for tid in tp_techniques
            ],
            "false_positives": list(fp_techniques),
            "false_negatives": [
                next(t for t in GROUND_TRUTH["techniques"] if t["technique"] == tid)
                for tid in fn_techniques
            ],
        },

        "ioc_detection": {
            "c2_ip_accuracy": round(ioc_ip_accuracy * 100, 1),
            "malware_path_accuracy": round(ioc_path_accuracy * 100, 1),
            "detected_ips": list(detected_ips),
            "ground_truth_ips": list(gt_ips),
            "detected_paths": list(detected_paths),
            "ground_truth_paths": list(gt_paths),
        },

        "tool_performance": {
            "total_tool_calls": len(tool_calls),
            "successful_calls": len(successful_tools),
            "success_rate": round(tool_success_rate * 100, 1),
            "by_tool": _aggregate_tool_stats(tool_calls),
        },

        "self_correction_effectiveness": {
            "total_corrections": len(corrections),
            "successful_corrections": len(correction_successes),
            "correction_success_rate": round(correction_rate * 100, 1),
            "corrections": corrections,
        },

        "audit_trail": {
            "total_entries": audit.get("total_tool_calls", 0),
            "duration_seconds": audit.get("duration_seconds", 0),
            "session_id": audit.get("session_id"),
        }
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Accuracy Report saved: {output_path}")

    return report


def print_accuracy_summary(report: dict):
    """Pretty-print accuracy report to terminal."""
    summary = report["executive_summary"]
    print(f"\n{'═'*60}")
    print(f"  SIFTGUARD ACCURACY REPORT")
    print(f"{'═'*60}")
    print(f"  Overall Score:      {summary['overall_accuracy_score']}%")
    print(f"  Precision:          {summary['precision']}%")
    print(f"  Recall:             {summary['recall']}%")
    print(f"  F1 Score:           {summary['f1_score']}%")
    print(f"{'─'*60}")
    print(f"  MITRE Techniques:   {summary['true_positives']} / {summary['mitre_techniques_in_ground_truth']} detected")
    print(f"  False Positives:    {summary['false_positives']}")
    print(f"  False Negatives:    {summary['false_negatives']}")
    print(f"{'─'*60}")
    ioc = report["ioc_detection"]
    print(f"  C2 IP Accuracy:     {ioc['c2_ip_accuracy']}%")
    print(f"  Path Accuracy:      {ioc['malware_path_accuracy']}%")
    print(f"{'─'*60}")
    tp = report["tool_performance"]
    print(f"  Tool Success Rate:  {tp['success_rate']}% ({tp['successful_calls']}/{tp['total_tool_calls']})")
    sc = report["self_correction_effectiveness"]
    print(f"  Self-Corrections:   {sc['total_corrections']} applied ({sc['correction_success_rate']}% success)")
    print(f"{'═'*60}\n")


def _aggregate_tool_stats(tool_calls: list[dict]) -> dict:
    stats = {}
    for call in tool_calls:
        tool = call.get("tool", "unknown")
        if tool not in stats:
            stats[tool] = {"total": 0, "success": 0}
        stats[tool]["total"] += 1
        if call.get("success"):
            stats[tool]["success"] += 1
    for tool, s in stats.items():
        s["success_rate"] = round(s["success"] / s["total"] * 100, 1) if s["total"] > 0 else 0
    return stats
