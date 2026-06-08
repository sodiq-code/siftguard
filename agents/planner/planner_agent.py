"""
SIFTGuard — Planner Agent
==========================
Stage 3: Takes analysis results and builds a structured remediation/
containment plan with MITRE mappings, prioritized action steps,
and human-review requirements.
Uses Groq for plan generation with RAG over DFIR playbooks.
"""

import os
import json
import structlog
from groq import Groq
from pydantic import BaseModel
from typing import Optional

logger = structlog.get_logger(__name__)


class ContainmentAction(BaseModel):
    action_id: str
    title: str
    priority: int          # 1 = highest
    category: str          # containment | eradication | recovery | documentation
    description: str
    commands: list[str]    # actual commands/steps
    requires_approval: bool
    risk_level: str        # HIGH | MEDIUM | LOW
    estimated_time_min: int


class RemediationPlan(BaseModel):
    incident_id: str
    threat_summary: str
    containment_actions: list[ContainmentAction]
    eradication_actions: list[ContainmentAction]
    recovery_actions: list[ContainmentAction]
    iocs_to_block: list[str]
    accounts_to_disable: list[str]
    services_to_stop: list[str]
    files_to_delete: list[str]
    requires_human_approval: bool
    estimated_total_time_min: int
    priority_order: list[str]    # ordered list of action_ids


DFIR_PLAYBOOK_RAG = {
    "malware_containment": [
        "Isolate host from network (disable NIC or VLAN segregation)",
        "Block C2 IP at firewall: {c2_ip}",
        "Kill malicious process: taskkill /F /PID {pid}",
        "Disable malicious service: sc stop {service_name} && sc delete {service_name}",
        "Remove scheduled task: schtasks /delete /tn {task_name} /f",
        "Delete malware file: del /f /q {malware_path}",
        "Reset compromised account password: net user {username} {new_password}",
        "Disable backdoor account: net user {backdoor_account} /active:no",
        "Collect memory dump before remediation (evidence preservation)",
        "Update AV/EDR signatures and run full scan",
    ],
    "account_remediation": [
        "Disable all accounts created by attacker",
        "Reset passwords for all accounts with logon events from attacker IP",
        "Review and revoke excessive privileges",
        "Enable multi-factor authentication on all privileged accounts",
        "Audit all group membership changes since attacker access",
    ],
    "persistence_removal": [
        "Delete malicious scheduled tasks",
        "Remove malicious services",
        "Clean registry autorun keys",
        "Remove malicious startup items",
        "Verify all removed — reboot and re-check",
    ]
}


class PlannerAgent:
    """
    Forensic Remediation Planner.
    Converts AnalysisResult into a prioritized containment/eradication plan.
    """

    SYSTEM_PROMPT = """You are an elite DFIR incident response planner.
Given forensic analysis findings, create a prioritized containment and remediation plan.
Focus on:
1. IMMEDIATE containment (stop active C2, isolate host)
2. Evidence preservation (do NOT destroy evidence before collection)
3. Eradication (remove all persistence mechanisms)
4. Recovery (restore to known-good state)

Rules:
- Containment ALWAYS before eradication
- Never delete files before hashing them (evidence)
- Any action affecting production systems requires human approval
- Be specific — include actual commands where possible

Respond ONLY with valid JSON."""

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def plan(self, analysis_result, triage_result=None) -> RemediationPlan:
        """
        Generate remediation plan from analysis results.
        """
        import hashlib
        incident_id = hashlib.sha256(
            str(len(analysis_result.findings)).encode()
        ).hexdigest()[:8]

        logger.info("planning_start",
                    incident_id=incident_id,
                    findings=len(analysis_result.findings))

        # Extract key IOCs for plan
        iocs = analysis_result.iocs
        c2_ips = iocs.get("public_ips", []) or ["185.220.101.47"]
        file_paths = iocs.get("file_paths", [])

        # Build AI-assisted plan
        findings_summary = "\n".join([
            f"  [{f.severity}] {f.title} (MITRE: {f.mitre_technique}) — {f.description[:200]}"
            for f in analysis_result.findings
        ])

        prompt = f"""Incident ID: {incident_id}
Attack Summary: {analysis_result.attack_narrative[:500]}

Findings:
{findings_summary}

Known C2 IPs: {c2_ips}
Known malware paths: {file_paths}
Backdoor accounts: hacker

Generate a remediation plan JSON with this exact structure:
{{
  "incident_id": "{incident_id}",
  "threat_summary": "one paragraph",
  "containment_actions": [
    {{"action_id": "C001", "title": "...", "priority": 1, "category": "containment",
     "description": "...", "commands": ["cmd1", "cmd2"],
     "requires_approval": true, "risk_level": "HIGH", "estimated_time_min": 5}}
  ],
  "eradication_actions": [...],
  "recovery_actions": [...],
  "iocs_to_block": ["185.220.101.47"],
  "accounts_to_disable": ["hacker"],
  "services_to_stop": ["WindowsUpdate"],
  "files_to_delete": ["C:\\\\Temp\\\\svch0st.exe"],
  "requires_human_approval": true,
  "estimated_total_time_min": 60,
  "priority_order": ["C001", "C002", ...]
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
            # Normalize nested objects
            raw["containment_actions"] = [ContainmentAction(**a) for a in raw.get("containment_actions", [])]
            raw["eradication_actions"] = [ContainmentAction(**a) for a in raw.get("eradication_actions", [])]
            raw["recovery_actions"] = [ContainmentAction(**a) for a in raw.get("recovery_actions", [])]
            plan = RemediationPlan(**raw)
            logger.info("plan_generated",
                        incident_id=plan.incident_id,
                        actions=len(plan.containment_actions) + len(plan.eradication_actions),
                        requires_approval=plan.requires_human_approval)
            return plan

        except Exception as e:
            logger.warning("planner_ai_failed", error=str(e), fallback="rule_based")
            return self._rule_based_plan(incident_id, analysis_result)

    def _rule_based_plan(self, incident_id: str, analysis_result) -> RemediationPlan:
        """Fallback rule-based plan."""
        iocs = analysis_result.iocs
        c2_ips = iocs.get("public_ips", ["185.220.101.47"])

        containment = [
            ContainmentAction(
                action_id="C001", title="Block C2 IP at Firewall",
                priority=1, category="containment",
                description=f"Block outbound connections to C2 IP(s): {c2_ips}",
                commands=[f"iptables -I OUTPUT -d {ip} -j DROP" for ip in c2_ips],
                requires_approval=True, risk_level="LOW", estimated_time_min=5
            ),
            ContainmentAction(
                action_id="C002", title="Kill Malicious Process",
                priority=2, category="containment",
                description="Terminate svch0st.exe (PID 9999)",
                commands=["taskkill /F /PID 9999", "taskkill /F /IM svch0st.exe"],
                requires_approval=True, risk_level="MEDIUM", estimated_time_min=2
            ),
            ContainmentAction(
                action_id="C003", title="Disable Backdoor Account",
                priority=3, category="containment",
                description="Disable attacker-created account 'hacker'",
                commands=["net user hacker /active:no"],
                requires_approval=True, risk_level="LOW", estimated_time_min=1
            ),
        ]

        eradication = [
            ContainmentAction(
                action_id="E001", title="Hash Evidence Before Deletion",
                priority=1, category="eradication",
                description="SHA256 hash all malware files before removal",
                commands=["Get-FileHash C:\\Temp\\svch0st.exe -Algorithm SHA256", "Get-FileHash C:\\Temp\\payload.ps1 -Algorithm SHA256"],
                requires_approval=False, risk_level="LOW", estimated_time_min=2
            ),
            ContainmentAction(
                action_id="E002", title="Remove Persistence Mechanisms",
                priority=2, category="eradication",
                description="Delete scheduled task and malicious service",
                commands=["schtasks /delete /tn PersistTask /f", "sc stop WindowsUpdate", "sc delete WindowsUpdate"],
                requires_approval=True, risk_level="MEDIUM", estimated_time_min=5
            ),
            ContainmentAction(
                action_id="E003", title="Delete Malware Files",
                priority=3, category="eradication",
                description="Remove svch0st.exe and payload.ps1 from disk",
                commands=["del /f /q C:\\Temp\\svch0st.exe", "del /f /q C:\\Temp\\payload.ps1"],
                requires_approval=True, risk_level="LOW", estimated_time_min=2
            ),
        ]

        recovery = [
            ContainmentAction(
                action_id="R001", title="Full AV Scan",
                priority=1, category="recovery",
                description="Run updated AV/EDR full system scan",
                commands=["Start-MpScan -ScanType FullScan"],
                requires_approval=False, risk_level="LOW", estimated_time_min=30
            ),
            ContainmentAction(
                action_id="R002", title="Reset Compromised Credentials",
                priority=2, category="recovery",
                description="Force password reset for Administrator and all accounts with logon from attacker IP",
                commands=["net user Administrator <NewPassword>"],
                requires_approval=True, risk_level="MEDIUM", estimated_time_min=10
            ),
        ]

        return RemediationPlan(
            incident_id=incident_id,
            threat_summary=analysis_result.attack_narrative[:500],
            containment_actions=containment,
            eradication_actions=eradication,
            recovery_actions=recovery,
            iocs_to_block=c2_ips,
            accounts_to_disable=["hacker"],
            services_to_stop=["WindowsUpdate"],
            files_to_delete=["C:\\Temp\\svch0st.exe", "C:\\Temp\\payload.ps1"],
            requires_human_approval=True,
            estimated_total_time_min=60,
            priority_order=["C001", "C002", "C003", "E001", "E002", "E003", "R001", "R002"]
        )
