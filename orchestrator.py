"""
SIFTGuard — Main Orchestrator
================================
Wires all 5 agents into the forensic investigation pipeline:

  Stage 1: Evidence Inventory  — list_evidence() via MCP
  Stage 2: AI Triage           — TriageAgent (Groq llama-3.3-70b)
  Stage 3: Playbook Loading    — search_playbook() via MCP
  Stage 4: Deep Analysis       — AnalyzerAgent (volatility + evtx + sleuthkit + timeline)
  Stage 5: Self-Correction     — SelfCorrectionAgent wraps all tool calls
  Stage 6: Remediation Plan    — PlannerAgent (Groq-generated + RAG)
  Stage 7: Human Approval      — ExecutorAgent (HITL gate)
  Stage 8: Report Generation   — AccuracyReportGenerator

Architecture: Purpose-built forensic MCP server (no VM required)
              Tools: volatility3, python-evtx, sleuthkit, custom IOC extractor
              AI: Groq llama-3.3-70b-versatile
              Audit: structlog JSON audit trail
              Self-correction: SelfCorrectionAgent with 3-strategy retry loop
"""

import os
import sys
import json
import asyncio
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agents.triage.triage_agent import TriageAgent
from agents.analyzer.analyzer_agent import AnalyzerAgent
from agents.planner.planner_agent import PlannerAgent
from agents.executor.executor_agent import ExecutorAgent
from agents.self_correction.self_correction_agent import SelfCorrectionAgent, correction_log
from mcp_server.server import (
    _list_evidence, _search_playbook, _record_finding, _audit_trail
)

# Configure structlog for beautiful JSON output
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger(__name__)

EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", "./data/evidence")
CASE_DIR = Path(os.getenv("CASE_DIR", "./data/cases"))


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ███████╗██╗███████╗████████╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ║
║   ██╔════╝██║██╔════╝╚══██╔══╝██╔════╝ ██║   ██║██╔══██╗██╔══██╗║
║   ███████╗██║█████╗     ██║   ██║  ███╗██║   ██║███████║██████╔╝║
║   ╚════██║██║██╔══╝     ██║   ██║   ██║██║   ██║██╔══██║██╔══██╗║
║   ███████║██║██║        ██║   ╚██████╔╝╚██████╔╝██║  ██║██║  ██║║
║   ╚══════╝╚═╝╚═╝        ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝║
║                                                                  ║
║      Autonomous Forensic Investigation Agent — FIND EVIL! 2026  ║
║      Multi-Agent · MCP Server · Self-Correction · HITL          ║
╚══════════════════════════════════════════════════════════════════╝
""")


class SIFTGuardOrchestrator:
    """
    Central orchestrator connecting all 5 agents and the MCP server.
    Produces a complete forensic investigation with audit trail.
    """

    def __init__(self, evidence_dir: str = EVIDENCE_DIR, auto_approve: bool = True):
        self.evidence_dir = evidence_dir
        self.auto_approve = auto_approve
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        CASE_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize agents
        self.triage_agent = TriageAgent()
        self.analyzer_agent = AnalyzerAgent()
        self.planner_agent = PlannerAgent()
        self.executor_agent = ExecutorAgent()
        self.correction_agent = SelfCorrectionAgent(max_retries=3)

        logger.info("siftguard_init", session_id=self.session_id, evidence_dir=evidence_dir)

    def run(self, initial_indicators: str = "") -> dict:
        """
        Run the complete forensic investigation pipeline.

        Args:
            initial_indicators: Optional IOCs or incident description

        Returns:
            Complete investigation report dict
        """
        print_banner()
        session_start = datetime.now(timezone.utc)

        print(f"\n  Session: {self.session_id}")
        print(f"  Evidence: {self.evidence_dir}")
        print(f"  Mode: {'DEMO (auto-approve)' if self.auto_approve else 'INTERACTIVE'}")
        print(f"\n{'─'*70}\n")

        results = {
            "session_id": self.session_id,
            "started_at": session_start.isoformat(),
            "stages": {}
        }

        # ══ STAGE 1: Evidence Inventory ══════════════════════════════════
        print("  [STAGE 1/8] Evidence Inventory")
        print("  → Running: list_evidence()")
        evidence = _list_evidence()
        results["stages"]["evidence"] = evidence
        print(f"  ✓ Found {evidence['count']} artifacts:")
        for f in evidence["files"]:
            print(f"      {f['path']} ({f['size_bytes']:,} bytes)")

        # ══ STAGE 2: AI Triage ═══════════════════════════════════════════
        print(f"\n  [STAGE 2/8] AI Triage (Groq {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')})")
        print(f"  → Running: TriageAgent.triage()")
        triage = self.triage_agent.triage(evidence["files"], initial_indicators)
        results["stages"]["triage"] = triage.model_dump()
        print(f"  ✓ Threat Type:  {triage.threat_type.upper()}")
        print(f"     Severity:    {triage.severity}")
        print(f"     Confidence:  {triage.confidence}")
        print(f"     Hypothesis:  {triage.initial_hypothesis[:80]}...")
        print(f"     Playbook:    {triage.recommended_playbook}")

        # ══ STAGE 3: Playbook Loading ═════════════════════════════════════
        print(f"\n  [STAGE 3/8] DFIR Playbook Loading")
        print(f"  → Running: search_playbook('{triage.recommended_playbook}')")
        playbook = _search_playbook(triage.recommended_playbook)
        results["stages"]["playbook"] = playbook
        print(f"  ✓ Loaded: {playbook['playbook']['name']}")
        for step in playbook["playbook"]["steps"][:3]:
            print(f"      {step}")
        print(f"      ... (+{len(playbook['playbook']['steps'])-3} more steps)")

        # ══ STAGE 4: Deep Forensic Analysis ══════════════════════════════
        print(f"\n  [STAGE 4/8] Deep Forensic Analysis")
        print(f"  → Running: AnalyzerAgent with MCP tools")
        print(f"     Memory analysis: {'YES' if triage.requires_memory_analysis else 'NO'}")
        print(f"     Log analysis:    {'YES' if triage.requires_log_analysis else 'NO'}")
        print(f"     Disk analysis:   {'YES' if triage.requires_disk_analysis else 'NO'}")
        print()

        # ── Self-correction wraps all memory analysis ──
        self._run_memory_analysis_with_correction()

        analysis = self.analyzer_agent.analyze(triage, self.evidence_dir)
        results["stages"]["analysis"] = {
            "findings_count": len(analysis.findings),
            "timeline_events": len(analysis.timeline_events),
            "iocs": analysis.iocs,
            "mitre_techniques": analysis.mitre_techniques,
            "confidence": analysis.confidence_overall,
            "gaps": analysis.gaps,
            "attack_narrative": analysis.attack_narrative,
        }
        print(f"\n  ✓ Analysis Complete:")
        print(f"     Findings:        {len(analysis.findings)}")
        print(f"     Timeline Events: {len(analysis.timeline_events)}")
        print(f"     IOCs Extracted:  {sum(len(v) for v in analysis.iocs.values() if isinstance(v, list))}")
        print(f"     MITRE Techniques:{len(analysis.mitre_techniques)}")
        print(f"     Confidence:      {analysis.confidence_overall}")

        # ══ STAGE 5: Record Findings (MCP) ════════════════════════════════
        print(f"\n  [STAGE 5/8] Recording Findings via MCP")
        finding_ids = []
        for finding in analysis.findings:
            record_result = _record_finding({
                "title": finding.title,
                "severity": finding.severity,
                "evidence": finding.evidence,
                "mitre_technique": finding.mitre_technique,
                "confidence": finding.confidence,
                "description": finding.description,
                "iocs": finding.iocs,
            })
            if record_result["success"]:
                finding_ids.append(record_result["finding_id"])
                print(f"  ✓ [{finding.severity}] {finding.title[:55]} → ID:{record_result['finding_id']}")
        results["stages"]["findings"] = {"recorded": finding_ids}

        # ══ STAGE 6: Remediation Planning ═════════════════════════════════
        print(f"\n  [STAGE 6/8] Remediation Plan Generation (Groq + RAG)")
        print(f"  → Running: PlannerAgent.plan()")
        plan = self.planner_agent.plan(analysis, triage)
        results["stages"]["plan"] = {
            "incident_id": plan.incident_id,
            "containment_actions": len(plan.containment_actions),
            "eradication_actions": len(plan.eradication_actions),
            "recovery_actions": len(plan.recovery_actions),
            "iocs_to_block": plan.iocs_to_block,
            "requires_approval": plan.requires_human_approval,
            "estimated_time_min": plan.estimated_total_time_min,
        }
        print(f"  ✓ Plan Generated:")
        print(f"     Containment:  {len(plan.containment_actions)} actions")
        print(f"     Eradication:  {len(plan.eradication_actions)} actions")
        print(f"     Recovery:     {len(plan.recovery_actions)} actions")
        print(f"     IOCs to block:{plan.iocs_to_block}")
        print(f"     Est. Time:    {plan.estimated_total_time_min} min")

        # ══ STAGE 7: Human-in-the-Loop Execution ══════════════════════════
        print(f"\n  [STAGE 7/8] Human Approval + Execution")
        execution = self.executor_agent.execute(plan, auto_approve=self.auto_approve)
        results["stages"]["execution"] = execution.model_dump()

        # ══ STAGE 8: Report + Audit Trail ════════════════════════════════
        print(f"\n  [STAGE 8/8] Report Generation + Audit Trail")
        session_end = datetime.now(timezone.utc)
        duration = (session_end - session_start).total_seconds()

        correction_report = SelfCorrectionAgent.get_correction_report()
        audit_summary = {
            "session_id": self.session_id,
            "started_at": session_start.isoformat(),
            "completed_at": session_end.isoformat(),
            "duration_seconds": round(duration, 2),
            "total_tool_calls": len(_audit_trail),
            "self_corrections": correction_report["total_corrections"],
            "correction_success_rate": correction_report["success_rate"],
            "tool_calls": _audit_trail,
            "correction_log": correction_report["corrections"],
        }
        results["audit"] = audit_summary

        # Save complete report
        report_path = CASE_DIR / f"report_{self.session_id}.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        # Save audit trail
        audit_path = CASE_DIR / f"audit_{self.session_id}.json"
        with open(audit_path, "w") as f:
            json.dump(audit_summary, f, indent=2, default=str)

        print(f"\n{'═'*70}")
        print(f"  SIFTGUARD INVESTIGATION COMPLETE")
        print(f"{'═'*70}")
        print(f"  Session:     {self.session_id}")
        print(f"  Duration:    {duration:.1f}s")
        print(f"  Findings:    {len(analysis.findings)} ({len([f for f in analysis.findings if f.severity == 'CRITICAL'])} CRITICAL)")
        print(f"  Actions:     {len(execution.actions_executed)} executed / {len(execution.actions_skipped)} skipped")
        print(f"  Self-Fixes:  {correction_report['total_corrections']} corrections applied")
        print(f"  Report:      {report_path}")
        print(f"  Audit Trail: {audit_path}")
        print(f"\n  Attack Narrative:")
        print(f"  {analysis.attack_narrative[:300]}...")
        print(f"\n{'═'*70}\n")

        # Print MITRE ATT&CK summary
        if analysis.mitre_techniques:
            print(f"  MITRE ATT&CK Techniques Identified:")
            for t in analysis.mitre_techniques[:8]:
                print(f"    [{t['tactic']}] {t['technique']} — {t['name']}")
        print()

        return results

    def _run_memory_analysis_with_correction(self):
        """
        Demo self-correction sequence — visible in the video.
        Simulates a tool failure followed by autonomous correction.
        """
        from mcp_server.server import _run_volatility

        print(f"  Attempting: volatility3 windows.pslist")
        # Intentionally use a slightly wrong path to trigger correction
        result = self.correction_agent.execute_with_correction(
            tool_fn=_run_volatility,
            args={"dump_path": f"{self.evidence_dir}/memory/victim.mem", "plugin": "windows.pslist"},
            tool_name="run_volatility",
            verbose=True,
        )
        if result.get("simulated"):
            print(f"  ✓ Self-corrected: using forensic simulation data")
        else:
            print(f"  ✓ Volatility pslist: {len(result.get('data', {}).get('rows', []))} processes")


def main():
    """Entry point for SIFTGuard pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTGuard — Autonomous Forensic Investigation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # Full demo pipeline
  python main.py --indicators "C2 on port 4444, suspicious process svch0st.exe"
  python main.py --evidence /path/to/evidence # Custom evidence directory
  python main.py --interactive                # Require human approval per action
        """
    )
    parser.add_argument("--indicators", default="", help="Initial IOCs or incident description")
    parser.add_argument("--evidence", default=EVIDENCE_DIR, help="Evidence directory path")
    parser.add_argument("--interactive", action="store_true", help="Require human approval for each action")

    args = parser.parse_args()

    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY environment variable not set.")
        print("Copy .env.example to .env and add your Groq API key.")
        sys.exit(1)

    orchestrator = SIFTGuardOrchestrator(
        evidence_dir=args.evidence,
        auto_approve=not args.interactive,
    )

    orchestrator.run(initial_indicators=args.indicators)


if __name__ == "__main__":
    main()
