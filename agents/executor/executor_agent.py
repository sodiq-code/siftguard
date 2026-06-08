"""
SIFTGuard — Executor Agent
============================
Stage 4: Human-in-the-loop approval gate + safe execution of containment actions.
In demo mode: simulates human approval and logs it.
In production: presents approval form and waits for human response.
"""

import os
import json
import structlog
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

logger = structlog.get_logger(__name__)

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"


class ApprovalRecord(BaseModel):
    action_id: str
    action_title: str
    approved: bool
    approved_by: str
    approval_timestamp: str
    reason: Optional[str] = None


class ExecutionResult(BaseModel):
    incident_id: str
    actions_executed: list[str]
    actions_skipped: list[str]
    approvals: list[ApprovalRecord]
    success: bool
    error: Optional[str] = None
    execution_log: list[dict]
    duration_seconds: float


class ExecutorAgent:
    """
    Executes remediation plan actions with human-in-the-loop approval.
    """

    def __init__(self):
        self.execution_log: list[dict] = []

    def execute(self, remediation_plan, auto_approve: bool = None) -> ExecutionResult:
        """
        Execute remediation plan with approval gate.

        In DEMO_MODE: auto-approves all actions (simulates SRE approval).
        In PRODUCTION: waits for CLI input from analyst.
        """
        import time
        start = time.time()
        auto = auto_approve if auto_approve is not None else DEMO_MODE

        logger.info("execution_start",
                    incident_id=remediation_plan.incident_id,
                    total_actions=len(remediation_plan.containment_actions) +
                                  len(remediation_plan.eradication_actions),
                    demo_mode=auto)

        executed = []
        skipped = []
        approvals = []

        all_actions = (
            remediation_plan.containment_actions +
            remediation_plan.eradication_actions +
            remediation_plan.recovery_actions
        )
        # Sort by priority
        all_actions.sort(key=lambda a: a.priority)

        print(f"\n{'='*70}")
        print(f"  SIFTGUARD EXECUTOR — Incident: {remediation_plan.incident_id}")
        print(f"  {len(all_actions)} actions to execute")
        print(f"{'='*70}")

        for action in all_actions:
            print(f"\n  [{action.priority}] {action.action_id}: {action.title}")
            print(f"      Category: {action.category.upper()} | Risk: {action.risk_level}")
            print(f"      {action.description}")

            # Approval gate
            approved = False
            if action.requires_approval:
                if auto:
                    print(f"      [DEMO] Auto-approved (in production: human SRE approval required)")
                    approved = True
                    approver = "demo_auto_approve"
                else:
                    resp = input(f"\n      Approve this action? [y/N]: ").strip().lower()
                    approved = resp == "y"
                    approver = os.getenv("ANALYST_NAME", "analyst")
                    if not approved:
                        print(f"      REJECTED by analyst")
            else:
                approved = True
                approver = "auto_no_approval_needed"

            approval = ApprovalRecord(
                action_id=action.action_id,
                action_title=action.title,
                approved=approved,
                approved_by=approver,
                approval_timestamp=datetime.now(timezone.utc).isoformat(),
                reason="Auto-approved in demo mode" if auto else ("Human approved" if approved else "Human rejected")
            )
            approvals.append(approval)

            if not approved:
                skipped.append(action.action_id)
                self._log_execution(action.action_id, "SKIPPED", "Rejected by analyst")
                continue

            # Execute commands (simulated in demo — no actual system changes)
            exec_result = self._simulate_execution(action)
            if exec_result["success"]:
                executed.append(action.action_id)
                print(f"      ✓ Executed successfully")
                for cmd in action.commands[:2]:
                    print(f"        $ {cmd}")
            else:
                print(f"      ✗ Execution failed: {exec_result.get('error', 'unknown')}")
                skipped.append(action.action_id)

            self._log_execution(action.action_id, "EXECUTED" if exec_result["success"] else "FAILED",
                                exec_result.get("output", ""))

        duration = time.time() - start

        print(f"\n{'='*70}")
        print(f"  EXECUTION COMPLETE")
        print(f"  Executed: {len(executed)} | Skipped: {len(skipped)}")
        print(f"  Duration: {duration:.1f}s")
        print(f"{'='*70}\n")

        return ExecutionResult(
            incident_id=remediation_plan.incident_id,
            actions_executed=executed,
            actions_skipped=skipped,
            approvals=approvals,
            success=len(executed) > 0,
            execution_log=self.execution_log,
            duration_seconds=round(duration, 2)
        )

    def _simulate_execution(self, action) -> dict:
        """Simulate command execution — no real system changes in demo."""
        output_map = {
            "containment": f"[SIMULATED] {action.title} — containment applied",
            "eradication": f"[SIMULATED] {action.title} — artifact removed",
            "recovery": f"[SIMULATED] {action.title} — system restored",
            "documentation": f"[SIMULATED] {action.title} — documented",
        }
        return {
            "success": True,
            "output": output_map.get(action.category, f"[SIMULATED] {action.title}"),
            "simulated": True
        }

    def _log_execution(self, action_id: str, status: str, output: str):
        self.execution_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_id": action_id,
            "status": status,
            "output": output[:500],
        })
