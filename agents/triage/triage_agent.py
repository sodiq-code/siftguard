"""
SIFTGuard — Triage Agent
=========================
Stage 1: Receives raw evidence artifact paths, determines threat type,
severity, and which investigation playbook to follow.
Uses Groq llama-3.3-70b-versatile for AI-powered triage.
"""

import os
import json
import structlog
from groq import Groq
from pydantic import BaseModel
from typing import Optional

logger = structlog.get_logger(__name__)


class TriageResult(BaseModel):
    threat_type: str           # ransomware | malware | intrusion | lateral_movement | unknown
    severity: str              # CRITICAL | HIGH | MEDIUM | LOW
    confidence: str            # HIGH | MEDIUM | LOW
    summary: str               # 1-paragraph human-readable summary
    recommended_playbook: str  # which playbook to load
    requires_memory_analysis: bool
    requires_disk_analysis: bool
    requires_log_analysis: bool
    priority_artifacts: list[str]  # which artifacts to analyze first
    initial_hypothesis: str    # attacker objective hypothesis


class TriageAgent:
    """
    AI-powered forensic triage using Groq.
    Analyzes evidence manifest + any initial indicators to determine
    investigation direction before deep analysis begins.
    """

    SYSTEM_PROMPT = """You are an elite DFIR (Digital Forensics and Incident Response) triage analyst.
Given a list of forensic artifacts and any initial indicators, you must:
1. Classify the incident type (ransomware, malware/trojan, intrusion, lateral movement, insider threat, unknown)
2. Assess severity (CRITICAL/HIGH/MEDIUM/LOW) based on potential impact
3. Recommend the correct investigation playbook
4. Prioritize which artifacts to analyze first
5. State your initial hypothesis about attacker objectives

Be concise, precise, and evidence-based. Do NOT speculate beyond what artifacts suggest.
Respond ONLY with valid JSON matching the exact schema provided."""

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ── Deterministic demo result — reproducible output matching the demo video ──
    DEMO_RESULT = TriageResult(
        threat_type="malware",
        severity="CRITICAL",
        confidence="HIGH",
        summary=(
            "Memory dump analysis reveals a typosquatted process svch0st.exe maintaining "
            "an active reverse shell to 185.220.101.47:4444 (Metasploit default). "
            "Windows Security logs confirm backdoor account creation (Event 4720), "
            "scheduled persistence (Event 4698), and malicious service installation (Event 7045). "
            "PowerShell base64 encoded commands indicate staged payload delivery. "
            "Assessment: Active hands-on-keyboard intrusion with full persistence established."
        ),
        recommended_playbook="malware",
        requires_memory_analysis=True,
        requires_disk_analysis=True,
        requires_log_analysis=True,
        priority_artifacts=[
            "data/evidence/memory/victim.mem",
            "data/evidence/logs/Security.evtx",
            "data/evidence/disk/victim-disk.E01",
        ],
        initial_hypothesis=(
            "Threat actor gained initial access via phishing, deployed Metasploit reverse shell "
            "through typosquatted svchost process, established persistence via scheduled task and "
            "malicious service, and created backdoor admin account for lateral movement."
        ),
    )

    def triage(self, evidence_manifest: list[dict], initial_indicators: str = "") -> TriageResult:
        """
        Triage based on evidence manifest and optional initial IOCs.

        Args:
            evidence_manifest: List of dicts with {path, size_bytes, extension}
            initial_indicators: Any known IOCs or symptoms

        Returns:
            TriageResult with investigation direction
        """
        logger.info("triage_start", artifacts=len(evidence_manifest))

        # Demo mode: return deterministic result for reproducible demo output
        if os.getenv("DEMO_MODE", "false").lower() == "true":
            logger.info("triage_complete",
                        threat_type=self.DEMO_RESULT.threat_type,
                        severity=self.DEMO_RESULT.severity,
                        confidence=self.DEMO_RESULT.confidence,
                        mode="demo")
            return self.DEMO_RESULT

        artifact_summary = "\n".join([
            f"  - {e['path']} ({e['extension']}, {e['size_bytes']:,} bytes)"
            for e in evidence_manifest
        ])

        prompt = f"""Forensic evidence available:
{artifact_summary}

Initial indicators / symptoms:
{initial_indicators or 'None provided — blind triage required'}

Respond with JSON:
{{
  "threat_type": "malware|ransomware|intrusion|lateral_movement|insider|unknown",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "confidence": "HIGH|MEDIUM|LOW",
  "summary": "1-paragraph triage summary",
  "recommended_playbook": "malware|ransomware|intrusion|default",
  "requires_memory_analysis": true,
  "requires_disk_analysis": true,
  "requires_log_analysis": true,
  "priority_artifacts": ["list", "of", "artifact", "paths"],
  "initial_hypothesis": "Attacker objective hypothesis"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = json.loads(response.choices[0].message.content)
            result = TriageResult(**raw)
            logger.info("triage_complete",
                        threat_type=result.threat_type,
                        severity=result.severity,
                        confidence=result.confidence)
            return result

        except Exception as e:
            logger.warning("triage_ai_failed", error=str(e), fallback="rule_based")
            return self._rule_based_triage(evidence_manifest, initial_indicators)

    def _rule_based_triage(self, evidence_manifest: list[dict], indicators: str) -> TriageResult:
        """Fallback rule-based triage when AI call fails."""
        extensions = {e["extension"] for e in evidence_manifest}
        has_memory = any(ext in extensions for ext in [".mem", ".raw", ".dmp", ".vmem"])
        has_logs = any(ext in extensions for ext in [".evtx", ".log"])
        has_disk = any(ext in extensions for ext in [".e01", ".dd", ".img"])

        ind_lower = indicators.lower()
        if "ransom" in ind_lower or ".encrypted" in ind_lower:
            threat = "ransomware"
        elif "reverse shell" in ind_lower or "c2" in ind_lower or "backdoor" in ind_lower:
            threat = "malware"
        elif "login" in ind_lower or "brute" in ind_lower or "unauthorized" in ind_lower:
            threat = "intrusion"
        else:
            threat = "malware"

        return TriageResult(
            threat_type=threat,
            severity="HIGH",
            confidence="MEDIUM",
            summary=f"Rule-based triage: {threat} suspected. Memory={'yes' if has_memory else 'no'}, Logs={'yes' if has_logs else 'no'}, Disk={'yes' if has_disk else 'no'}",
            recommended_playbook=threat,
            requires_memory_analysis=has_memory,
            requires_disk_analysis=has_disk,
            requires_log_analysis=has_logs,
            priority_artifacts=[e["path"] for e in evidence_manifest[:3]],
            initial_hypothesis="Attacker may have gained unauthorized access and deployed malicious tooling."
        )
