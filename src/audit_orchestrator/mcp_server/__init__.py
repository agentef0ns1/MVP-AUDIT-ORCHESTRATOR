"""
MCP Server for Audit Orchestrator
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from audit_orchestrator.mcp_compat import FastMCP
from audit_orchestrator.config import Settings
from audit_orchestrator.core.errors import AuditOrchestratorError
from audit_orchestrator.core.live_screen import LiveScreen
from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.core.store import AuditStore

try:
    from mcp.server.mcpserver import Context
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import Context  # type: ignore[no-redef]

# Initialize MCP server
mcp = FastMCP("audit-orchestrator")

# Global instances
_store: AuditStore | None = None
_orchestrator: AuditOrchestrator | None = None
_settings: Settings | None = None


def get_store() -> AuditStore:
    """Get or create store instance"""
    global _store, _settings
    if _store is None:
        _settings = Settings.from_args()
        _store = AuditStore(_settings)
    return _store


def get_orchestrator() -> AuditOrchestrator:
    """Get or create orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        store = get_store()
        settings = _settings or Settings.from_args()
        _orchestrator = AuditOrchestrator(settings, store)
    return _orchestrator


def _ok(data: dict[str, Any]) -> str:
    """Format success response"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def _normalize_command(command: str) -> str:
    return " ".join((command or "").split())


def _duplicate_command_message(project_id: str, target_id: str, command: str) -> str:
    return (
        f"Command already ran and was not executed again: {command}. "
        "The MCP kept control and continued the profile. "
        f'When the next port is ready, call audit_llm_continue(project_id="{project_id}", target_id="{target_id}") '
        "only after analyzing that port."
    )


def _continue_after_repeat(orch, project, project_id: str, target_id: str, target_name: str, command: str) -> dict:
    """A repeated LLM command does not stop the audit. The MCP enumerates the next port."""
    _show_llm(
        project["base_path"],
        asset=target_name,
        phase="LLM",
        llm="continue profile",
        mcp="audit_llm_continue",
        command=command,
        ask="repeated command ignored",
        answer="MCP continues with the next port",
        status="running",
        output="-",
    )
    try:
        from audit_orchestrator.core.filesystem import WorkspaceManager
        WorkspaceManager(project["base_path"]).append_bitacora(
            target_name,
            "LLM REPEAT",
            f"Ignored repeated command and continued the profile: {command}",
            result="pending_llm",
        )
    except Exception:
        pass
    result = asyncio.run(orch.continue_type3(project_id, target_id))
    note = _duplicate_command_message(project_id, target_id, command)
    if result.get("done"):
        return {
            "success": True,
            "done": True,
            "skipped_duplicate": True,
            "project_id": project_id,
            "target_id": target_id,
            "target_name": result.get("target_name") or target_name,
            "command": command,
            "note": note + " Profile finished for this target.",
            "next_action": None,
        }
    handoff = orch.type3_handoff(project_id, target_id)
    return {
        "success": True,
        "done": False,
        "skipped_duplicate": True,
        "project_id": project_id,
        "target_id": target_id,
        "target_name": result.get("target_name") or target_name,
        "command": command,
        "step": handoff["step"],
        "prompt": handoff["prompt"],
        "continue_with": handoff["continue_with"],
        "next_action": handoff["prompt"],
        "note": note,
    }


def _err(code: str, message: str) -> str:
    """Format error response"""
    return json.dumps({
        "error": True,
        "code": code,
        "message": message
    }, ensure_ascii=False)


def _consume_task(task: asyncio.Task) -> None:
    try:
        task.exception()
    except Exception:
        return


def _make_live_sink(ctx: Context, pending: list[asyncio.Task]):
    """Push a full screen frame as notifications/message on the server loop.

    ctx.info() is dropped on protocol 2026-07-28 unless the client opts in
    via _meta. send_notification does not apply that filter, so Cline receives
    the frame while the tool is still running.
    """

    def sink(frame: str) -> None:
        text = "```text\n" + frame + "\n```"

        async def _send() -> None:
            try:
                import mcp.types as types
                note = types.LoggingMessageNotification(
                    params=types.LoggingMessageNotificationParams(
                        level="info",
                        data=text,
                        logger="audit-live",
                    )
                )
                await ctx.session.send_notification(
                    note,
                    related_request_id=ctx.request_id,
                )
            except Exception:
                return

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_send())
            pending.append(task)
            task.add_done_callback(_consume_task)
        except RuntimeError:
            return

    return sink


def _show_llm(base_path: str, **fields: Any) -> None:
    """Paint one asset box, including the LLM question and answer."""
    from pathlib import Path

    orch = get_orchestrator()
    if orch.live is None:
        orch.live = LiveScreen()
    orch.live.frame_path = Path(base_path) / "audit-live.txt"
    _arm_live_console(base_path)
    orch._live(force=True, **fields)


def _arm_live_console(base_path: str) -> None:
    """Open the redraw terminal. The audit continues if the window cannot open."""
    from audit_orchestrator.core.live_terminal import open_live_terminal

    open_live_terminal(base_path)


def _bind_live(ctx: Context) -> LiveScreen:
    pending: list[asyncio.Task] = []
    screen = LiveScreen(sink=_make_live_sink(ctx, pending))
    screen.notify_tasks = pending  # type: ignore[attr-defined]
    get_orchestrator().live = screen
    return screen


async def _ok_live(data: dict[str, Any], screen: LiveScreen) -> str:
    """Final tool text: last frame, then the same JSON as before."""
    screen.publish(force=True)
    pending = getattr(screen, "notify_tasks", [])
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return screen.message() + "\n\n" + _ok(data)


def _record_llm_prompt(
    base_path: str,
    target_name: str,
    prompt: str,
    answer: str = "-",
    **live: Any,
) -> None:
    """Paint the prompt the model receives and append that same text to audit.log."""
    _show_llm(
        base_path,
        asset=target_name,
        phase="LLM",
        llm="prompt",
        status="waiting",
        ask=prompt,
        answer=answer,
        **live,
    )
    logged = prompt if not answer or answer == "-" else f"{prompt}\n\nstdout:\n{answer}"
    try:
        from audit_orchestrator.core.filesystem import WorkspaceManager
        WorkspaceManager(base_path).append_bitacora(
            target_name, "LLM PROMPT", logged, result="pending_llm"
        )
    except Exception:
        return


def _type2_prompt(pending_llm: list[dict[str, Any]]) -> str:
    """Type 2 handoff: the instruction plus the service index sent with it."""
    lines = [_next_action_for("type_2_post_host_llm"), ""]
    for item in pending_llm:
        lines.append(f"Target: {item.get('target_name') or item.get('target_id')}")
        for service in item.get("services") or []:
            version = service.get("version") or ""
            lines.append(
                " ".join(
                    part for part in (
                        f"{service.get('port')}/{service.get('protocol')} {service.get('service_name') or ''}".strip(),
                        version,
                    ) if part
                )
            )
    return "\n".join(lines).strip()


def _next_action_for(execution_mode: str) -> str:
    if execution_mode == "type_3_interactive_llm":
        return (
            "Enumeration of one port just finished. Read the prompt. "
            "It lists that port's commands and output excerpts. "
            "Record a real issue with audit_record_finding, or repeat and deepen "
            "checks on that same port with audit_llm_next_command. "
            "When that port needs nothing more, call audit_llm_continue(project_id, target_id). "
            "That runs the next port and stops again. "
            "Keep going until audit_llm_continue returns done=true. "
            "No DoS, no brute-force, no exploitation."
        )
    return (
        "Call audit_llm_analyze_host(project_id, target_id) once to get the service index. "
        "Then call it again with port= for one service at a time and read only those files. "
        "Do not write an analysis, do not list negative results, and do not invent CVE identifiers. "
        "After each service, run at most one safe command with "
        "audit_llm_execute_poc(project_id, target_id, command, reason), or skip it. "
        "No DoS, no brute-force, no exploitation."
    )


def _compact_pending_llm(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identifiers and service list only. Full outputs stay in audit_llm_analyze_host."""
    compact: list[dict[str, Any]] = []
    for item in items:
        context = item.get("host_context") or {}
        services = [
            {
                "port": service.get("port"),
                "protocol": service.get("protocol"),
                "service_name": service.get("service_name"),
                "version": service.get("version"),
                "status": service.get("status"),
            }
            for service in (context.get("services") or [])
        ]
        compact.append({
            "project_id": item.get("project_id"),
            "target_id": item.get("target_id"),
            "target_name": item.get("target_name"),
            "summary": context.get("summary") or {},
            "services": services,
            "step": item.get("step"),
        })
    return compact


def _handle(fn, *args, **kwargs) -> str:
    """Handle function call with error wrapping"""
    try:
        result = fn(*args, **kwargs)
        # Handle async functions
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        return _ok(result)
    except AuditOrchestratorError as e:
        return _err(e.code, e.message)
    except Exception as e:
        return _err("internal_error", str(e))


# ===== MCP Tools =====

@mcp.tool(structured_output=False)
def audit_start(
    base_path: str,
    input_file: str = "open_ports.txt",
    profile: str = "default_blackbox",
    execution_mode: str = "type_1_no_llm",
    reset: bool = False
) -> str:
    """
    Initialize a new audit project.
    
    Parse input file with targets and ports, create directory structure,
    and initialize the audit database.
    
    Args:
        base_path: Base directory containing the input file and for workspace
        input_file: Name of input file with nmap output (default: open_ports.txt)
        profile: Audit profile to use (default: default_blackbox)
        execution_mode: Execution mode:
            - "type_1_no_llm": Fixed sequence from JSON (no LLM)
            - "type_2_post_host_llm": LLM analyzes after host enumeration, executes PoCs
            - "type_3_interactive_llm": LLM reviews each finished port (limits: 50 commands, 30 min)
        reset: Reset existing workspace if True
    
    Returns:
        JSON with project_id, targets_count, services_count, and summary
    """
    orchestrator = get_orchestrator()
    return _handle(
        orchestrator.start_audit,
        base_path=base_path,
        input_file=input_file,
        profile=profile,
        execution_mode=execution_mode,
        reset=reset
    )


@mcp.tool(structured_output=False)
async def audit_run(
    project_id: str,
    max_targets: int | None = None,
    parallel: bool = True,
    max_concurrent: int = 10,
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """
    Run the audit orchestration loop.
    
    This is the main audit execution that processes all pending targets
    and services. It is fault-tolerant and will continue even if individual
    tasks fail.
    
    The loop will:
    - Process targets (sequentially or in parallel based on 'parallel' parameter)
    - Execute service-specific audit tasks
    - Respect 15-minute timeout per service
    - Automatically detect common vulnerabilities
    - Log all operations to bitacora
    - Continue on errors without stopping
    - Auto-review before starting (if parallel mode enabled)
    
    Args:
        project_id: Project ID from audit_start
        max_targets: Optional limit on targets to process (for testing)
        parallel: Enable parallel execution (default: True). Set False for legacy sequential mode
        max_concurrent: Max concurrent targets when parallel=True (default: 10)
    
    Returns:
        JSON with execution summary, statistics, and done status
    
    Examples:
        # Parallel execution (recommended)
        audit_run(project_id="abc-123", parallel=True, max_concurrent=10)
        
        # Sequential execution (legacy)
        audit_run(project_id="abc-123", parallel=False)
        
        # High concurrency
        audit_run(project_id="abc-123", parallel=True, max_concurrent=20)
    """
    orchestrator = get_orchestrator()
    screen = _bind_live(ctx) if ctx is not None else LiveScreen()
    try:
        project = orchestrator.store.get_project(project_id)
        _arm_live_console(project["base_path"])
        if parallel:
            result = await orchestrator.run_audit_parallel(
                project_id=project_id,
                max_targets=max_targets,
                max_concurrent=max_concurrent,
            )
        else:
            result = await orchestrator.run_audit(
                project_id=project_id,
                max_targets=max_targets,
            )
        return await _ok_live(result, screen)
    except AuditOrchestratorError as e:
        return _err(e.code, e.message)
    except Exception as e:
        return _err("internal_error", str(e))
    finally:
        orchestrator.live = None


@mcp.tool(structured_output=False)
def audit_review(
    project_id: str,
    re_enqueue_failed: bool = True
) -> str:
    """
    Review project audits, detect failures, and generate services report.
    
    This tool analyzes completed audits to detect targets that failed due to
    connectivity issues, empty outputs, or excessive errors. Failed targets
    can be automatically re-enqueued for retry.
    
    Detection criteria for failed audits:
    - No bitacora directory or files
    - Empty bitacora logs
    - More than 80% of log lines contain errors
    - No enumeration outputs or all outputs are empty
    
    The tool also generates a comprehensive SERVICES_REPORT.md that groups
    targets by detected services, showing completion status for each.
    
    Args:
        project_id: Project ID to review
        re_enqueue_failed: Reset failed targets to pending status (default: True)
    
    Returns:
        JSON with:
        - total_targets: Total number of targets
        - failed_targets: List of detected failed targets with reasons
        - re_enqueued: Number of targets reset to pending
        - report_path: Path to generated SERVICES_REPORT.md
        - report: Full markdown report content
    
    Examples:
        # Review and re-enqueue failures
        audit_review(project_id="abc-123", re_enqueue_failed=True)
        
        # Review only (no re-enqueue)
        audit_review(project_id="abc-123", re_enqueue_failed=False)
    """
    from pathlib import Path
    from audit_orchestrator.core.audit_reviewer import AuditReviewer
    
    orchestrator = get_orchestrator()
    project = orchestrator.store.get_project(project_id)
    base_path = Path(project["base_path"])
    
    reviewer = AuditReviewer(base_path, orchestrator.store)
    
    # Perform review
    if re_enqueue_failed:
        result = reviewer.review_project(project_id)
    else:
        # Review without re-enqueuing
        targets = orchestrator.store.get_targets_by_project(project_id)
        failed_targets = []
        
        for target in targets:
            failure_reason = reviewer._is_target_failed(target)
            if failure_reason:
                failed_targets.append({
                    "ip": target["ip_or_hostname"],
                    "target_id": target["target_id"],
                    "status": target["status"],
                    "reason": failure_reason
                })
        
        result = {
            "total_targets": len(targets),
            "failed_targets": failed_targets,
            "re_enqueued": 0,
            "report": reviewer._generate_services_report(project_id, targets)
        }
    
    # Save report to workspace
    report_path = base_path / "SERVICES_REPORT.md"
    report_path.write_text(result["report"], encoding="utf-8")
    result["report_path"] = str(report_path)
    
    return _ok(result)


@mcp.tool(structured_output=False)
async def audit_start_and_run(
    base_path: str,
    input_file: str = "open_ports.txt",
    profile: str = "default_blackbox",
    execution_mode: str = "type_1_no_llm",
    reset: bool = False,
    max_targets: int | None = None,
    parallel: bool = True,
    max_concurrent: int = 10,
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """
    Convenience tool: Start + Run audit in one call.
    
    Combines audit_start() and audit_run() to simplify workflow.
    The model doesn't need to manage project_id between calls.
    
    Args:
        base_path: Base directory for audit workspace
        input_file: Name of input file (default: open_ports.txt)
        profile: Audit profile (default: default_blackbox)
        execution_mode: Execution mode (type_1_no_llm, type_2_post_host_llm, type_3_interactive_llm)
        reset: Reset existing workspace if True
        max_targets: Optional limit on targets to process
        parallel: Enable parallel execution (default: True)
        max_concurrent: Max concurrent targets when parallel=True (default: 10)
    
    Returns:
        JSON with:
        - project_id: For future reference if needed
        - Initial setup info (targets_count, services_count)
        - Execution results (targets_processed, findings_created)
        - Final status
    """
    orch = get_orchestrator()
    screen = _bind_live(ctx) if ctx is not None else LiveScreen()
    try:
        start_result = await orch.start_audit(
            base_path, input_file, profile, execution_mode, reset
        )
        project_id = start_result["project_id"]
        _arm_live_console(base_path)
        if parallel:
            run_result = await orch.run_audit_parallel(
                project_id, max_targets, max_concurrent
            )
        else:
            run_result = await orch.run_audit(project_id, max_targets)
        pending_llm = _compact_pending_llm(run_result.get("pending_llm") or [])
        status = run_result.get("status", "completed")
        if pending_llm:
            status = "pending_llm_analysis"
        handoff = None
        if execution_mode == "type_3_interactive_llm" and pending_llm:
            handoff = orch.type3_handoff(project_id, pending_llm[0]["target_id"])
        note = "Audit started and executed successfully. Results in: " + base_path
        if handoff:
            note = "One port finished. The prompt is in next_action. Follow it, then call continue_with."
        elif pending_llm:
            note = (
                "Enumeration finished. Do not analyze this response in prose. "
                "Follow next_action and stop after the tool calls."
            )
        payload = {
            "success": True,
            "project_id": project_id,
            "base_path": base_path,
            "execution_mode": execution_mode,
            "setup": {
                "targets_count": start_result["targets_count"],
                "services_count": start_result["services_count"]
            },
            "execution": {
                "targets_processed": run_result.get("targets_processed", 0),
                "targets_completed": run_result.get("targets_completed", 0),
                "services_audited": run_result.get("services_audited", 0),
                "findings_created": run_result.get("findings_created", 0)
            },
            "status": status,
            "pending_llm": pending_llm,
            "step": (handoff or {}).get("step"),
            "prompt": (handoff or {}).get("prompt"),
            "continue_with": (handoff or {}).get("continue_with"),
            "next_action": (handoff or {}).get("prompt") if handoff else (
                _type2_prompt(pending_llm) if pending_llm else None
            ),
            "note": note
        }
        if pending_llm and not handoff:
            payload["prompt"] = payload["next_action"]
            _record_llm_prompt(
                base_path,
                pending_llm[0].get("target_name") or "target",
                payload["prompt"],
                mcp="audit_llm_analyze_host",
            )
        return await _ok_live(payload, screen)
    except AuditOrchestratorError as e:
        return _err(e.code, e.message)
    except Exception as e:
        return _err("internal_error", str(e))
    finally:
        orch.live = None


@mcp.tool(structured_output=False)
async def audit_resume(
    base_path: str,
    input_file: str = "open_ports.txt",
    max_targets: int | None = None,
    ctx: Context = None,  # type: ignore[assignment]
) -> str:
    """
    Resume/continue audit from a directory without knowing project_id.
    
    Finds the project by base_path and continues execution.
    Useful for resuming interrupted audits or continuing partial runs.
    
    Args:
        base_path: Base directory of the audit project
        input_file: Name of input file (default: open_ports.txt)
        max_targets: Optional limit on targets to process
    
    Returns:
        JSON with execution results and status
    """
    orch = get_orchestrator()
    screen = _bind_live(ctx) if ctx is not None else LiveScreen()
    try:
        try:
            project = orch.store.get_project_by_path(base_path, input_file)
            project_id = project["project_id"]
        except Exception:
            raise AuditOrchestratorError(
                "project_not_found",
                f"No audit project found at {base_path}. Use audit_start_and_run() to create one."
            )
        _arm_live_console(base_path)
        run_result = await orch.run_audit(project_id, max_targets)
        payload = {
            "success": True,
            "project_id": project_id,
            "base_path": base_path,
            "execution_mode": project.get("execution_mode", "type_1_no_llm"),
            "execution": {
                "targets_processed": run_result.get("targets_processed", 0),
                "targets_completed": run_result.get("targets_completed", 0),
                "services_audited": run_result.get("services_audited", 0),
                "findings_created": run_result.get("findings_created", 0)
            },
            "status": run_result.get("status", "completed"),
            "note": "Audit resumed and executed. Results in: " + base_path
        }
        return await _ok_live(payload, screen)
    except AuditOrchestratorError as e:
        return _err(e.code, e.message)
    except Exception as e:
        return _err("internal_error", str(e))
    finally:
        orch.live = None


@mcp.tool(structured_output=False)
def audit_status(project_id: str) -> str:
    """
    Get current audit status and progress.
    
    Args:
        project_id: Project ID
    
    Returns:
        JSON with:
        - Current project status
        - Statistics (targets, services, findings)
        - Last operation from bitacora
        - Next pending target
        - Whether audit is complete
    """
    orchestrator = get_orchestrator()
    return _handle(
        orchestrator.get_audit_status,
        project_id=project_id
    )


@mcp.tool(structured_output=False)
def audit_status_by_path(
    base_path: str,
    input_file: str = "open_ports.txt"
) -> str:
    """
    Get audit status by directory path (no project_id needed).
    
    Finds the project by base_path and returns its status.
    Useful when you don't have the project_id handy.
    
    Args:
        base_path: Base directory of the audit project
        input_file: Name of input file (default: open_ports.txt)
    
    Returns:
        JSON with status and statistics (same as audit_status)
    """
    def _impl():
        orch = get_orchestrator()
        store = orch.store
        
        # Find project by path
        try:
            project = store.get_project_by_path(base_path, input_file)
            project_id = project["project_id"]
        except Exception:
            raise AuditOrchestratorError(
                "project_not_found",
                f"No audit project found at {base_path}"
            )
        
        # Get status
        status = orch.get_audit_status(project_id)
        
        # Add base_path for reference
        status["base_path"] = base_path
        
        return status
    
    return _handle(_impl)


@mcp.tool(structured_output=False)
def audit_record_finding(
    project_id: str,
    target: str,
    severity: str,
    title: str,
    description: str = "",
    port: int | None = None,
    service: str | None = None,
    cwe: str | None = None,
    cvss_score: float | None = None,
    evidence: str = "",
    exploit_available: bool = False
) -> str:
    """
    Manually record a security finding.
    
    Creates a finding in the database and generates a markdown report
    in the target's findings/ directory.
    
    Args:
        project_id: Project ID
        target: Target IP or hostname
        severity: critical | high | medium | low | info
        title: Finding title
        description: Detailed description
        port: Service port (optional)
        service: Service name (optional)
        cwe: CWE identifier (optional)
        cvss_score: CVSS score (optional)
        evidence: Evidence text or command output
        exploit_available: Whether public exploit exists
    
    Returns:
        JSON with finding_id and file path
    """
    store = get_store()
    
    # Get target_id
    targets = store.get_targets_by_project(project_id)
    target_obj = next((t for t in targets if t["ip_or_hostname"] == target), None)
    
    if not target_obj:
        return _err("target_not_found", f"Target not found: {target}")
    
    target_id = target_obj["target_id"]
    
    # Get service_id if port provided
    service_id = None
    if port:
        services = store.get_services_by_target(target_id)
        service_obj = next((s for s in services if s["port"] == port), None)
        if service_obj:
            service_id = service_obj["service_id"]
    
    # Create finding
    finding = store.create_finding(
        project_id=project_id,
        target_id=target_id,
        service_id=service_id,
        severity=severity,
        title=title,
        description=description,
        exploit_available=exploit_available,
        cwe=cwe,
        cvss_score=cvss_score
    )
    
    # Create finding file
    project = store.get_project(project_id)
    from pathlib import Path
    from audit_orchestrator.core.filesystem import WorkspaceManager
    
    workspace = WorkspaceManager(Path(project["base_path"]))
    
    service_str = f"{port}/{service}" if port and service else None
    
    finding_path = workspace.create_finding(
        target=target,
        finding_id=finding["finding_id"],
        severity=severity,
        title=title,
        description=description,
        service=service_str,
        cwe=cwe,
        cvss_score=cvss_score,
        evidence=evidence,
        exploit_available=exploit_available
    )
    
    return _ok({
        "finding_id": finding["finding_id"],
        "finding_path": finding_path,
        "target": target,
        "severity": severity
    })


@mcp.tool(structured_output=False)
def audit_reset_project(project_id: str) -> str:
    """
    Reset a project's targets and services to 'pending' status.
    
    Use this when you want to re-run an audit from scratch without
    deleting the project structure. This will:
    - Reset all targets to 'pending'
    - Reset all services to 'pending'
    - Reset all audit tasks to 'pending'
    - Clear timestamps and errors
    - Keep existing findings and bitacora logs
    
    Args:
        project_id: Project ID to reset
    
    Returns:
        JSON with reset statistics (targets_reset, services_reset, tasks_reset)
    """
    orchestrator = get_orchestrator()
    return _handle(
        orchestrator.reset_project,
        project_id=project_id
    )


@mcp.tool(structured_output=False)
def audit_finalize(project_id: str) -> str:
    """
    Finalize audit and generate executive summary.
    
    Creates RESUMEN-AUDITORIA.md with:
    - Project overview
    - Target statistics
    - Findings by severity
    - Directory structure
    - Next steps
    
    Args:
        project_id: Project ID
    
    Returns:
        JSON with resumen_path and final statistics
    """
    orchestrator = get_orchestrator()
    return _handle(
        orchestrator.finalize_audit,
        project_id=project_id
    )


@mcp.tool(structured_output=False)
def audit_list_projects(
    status: str | None = None,
    limit: int = 50
) -> str:
    """
    List audit projects.
    
    Args:
        status: Filter by status (running | completed | paused)
        limit: Maximum number of projects to return
    
    Returns:
        JSON with list of projects
    """
    store = get_store()
    return _handle(
        store.list_projects,
        status=status,
        limit=limit
    )


@mcp.tool(structured_output=False)
def audit_get_findings(
    project_id: str,
    severity: str | None = None
) -> str:
    """
    Get findings for a project.
    
    Args:
        project_id: Project ID
        severity: Filter by severity (optional)
    
    Returns:
        JSON with list of findings
    """
    store = get_store()
    return _handle(
        store.get_findings_by_project,
        project_id=project_id,
        severity=severity
    )


@mcp.tool(structured_output=False)
def audit_get_targets(
    project_id: str,
    status: str | None = None
) -> str:
    """
    Get targets for a project.
    
    Args:
        project_id: Project ID
        status: Filter by status (optional)
    
    Returns:
        JSON with list of targets
    """
    store = get_store()
    return _handle(
        store.get_targets_by_project,
        project_id=project_id,
        status=status
    )


@mcp.tool(structured_output=False)
def audit_get_bitacora(
    project_id: str,
    target: str | None = None,
    limit: int = 100
) -> str:
    """
    Get audit log (bitacora) entries.
    
    Args:
        project_id: Project ID
        target: Filter by target IP/hostname (optional)
        limit: Maximum entries to return
    
    Returns:
        JSON with bitacora entries
    """
    store = get_store()
    
    # Get target_id if target provided
    target_id = None
    if target:
        targets = store.get_targets_by_project(project_id)
        target_obj = next((t for t in targets if t["ip_or_hostname"] == target), None)
        if target_obj:
            target_id = target_obj["target_id"]
    
    return _handle(
        store.get_bitacora_entries,
        project_id=project_id,
        target_id=target_id,
        limit=limit
    )


@mcp.tool(structured_output=False)
def kali_test_connection() -> str:
    """
    Test connection to MCP Kali server.
    
    Checks if the Kali MCP server is accessible and returns
    diagnostic information.
    
    Returns:
        JSON with connection status and server info
    """
    from audit_orchestrator.core.kali_client import test_kali_connection
    
    settings = _settings or Settings.from_args()
    
    return _handle(
        test_kali_connection,
        server_url=settings.kali_server_url
    )


# ===== LLM Interaction Tools =====

@mcp.tool(structured_output=False)
def audit_llm_analyze_host(
    project_id: str,
    target_id: str,
    port: int | None = None,
) -> str:
    """
    [Type 2 Mode] Read enumeration results one service at a time.

    Without port, returns the service index (ports and file names, no output).
    With port, returns only that service's task outputs.

    Args:
        project_id: Project ID
        target_id: Target ID to analyze
        port: Service port. Omit it for the index; set it to read that service.
    """
    def _impl():
        orch = get_orchestrator()

        project = orch.store.get_project(project_id)
        target = orch.store.get_target(target_id)

        if project.get("execution_mode") != "type_2_post_host_llm":
            return {
                "error": True,
                "message": f"This tool is only for Type 2 mode. Project is in {project.get('execution_mode')} mode."
            }

        services = orch.store.get_services_by_target(target_id)
        target_name = target.get("ip_or_hostname") or target_id
        if port is None:
            index = []
            for service in services:
                tasks = orch.store.get_tasks_by_service(service["service_id"])
                index.append({
                    "port": service.get("port"),
                    "protocol": service.get("protocol"),
                    "service_name": service.get("service_name"),
                    "version": service.get("version"),
                    "tasks": [
                        {
                            "task_type": task.get("task_type"),
                            "status": task.get("status"),
                            "output_path": task.get("output_path"),
                        }
                        for task in tasks
                    ],
                })
            lines = [
                f"{item.get('port')}/{item.get('protocol')} {item.get('service_name') or ''}".strip()
                for item in index
            ]
            instructions = (
                "This is only the index. Do not analyze it and do not list CVEs. "
                "Call audit_llm_analyze_host again with port= for one service. "
                "Read those files, run at most one safe PoC with audit_llm_execute_poc "
                "or skip the service, then request the next port."
            )
            _record_llm_prompt(
                project["base_path"],
                target_name,
                instructions + "\n\n" + ("\n".join(lines) or "no services"),
                mcp="audit_llm_analyze_host",
                status="index",
            )
            return {
                "success": True,
                "mode": "service_index",
                "project_id": project_id,
                "target_id": target_id,
                "target_name": target_name,
                "services": index,
                "instructions": instructions,
            }

        selected = [service for service in services if service.get("port") == port]
        if not selected:
            return {
                "error": True,
                "message": f"No service on port {port} for this target.",
            }
        service = selected[0]
        tasks = orch._attach_output_excerpts(
            orch.store.get_tasks_by_service(service["service_id"])
        )
        bits = []
        for task in tasks:
            path = task.get("output_path")
            full = ""
            if path:
                try:
                    full = Path(path).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    full = ""
            excerpt_text = full or task.get("output_excerpt") or task.get("output") or ""
            bits.append(f"{task.get('task_type')}: {excerpt_text}".strip())
        instructions = (
            "These files belong only to this port. "
            "Do not invent CVE identifiers and do not list checks that found nothing. "
            "If a safe check is useful, call audit_llm_execute_poc once for this port. "
            "Then call audit_llm_analyze_host with the next port."
        )
        _record_llm_prompt(
            project["base_path"],
            target_name,
            instructions + "\n\n" + ("\n\n".join(bits) or "no output"),
            service=f"{port}/{service.get('protocol')} {service.get('service_name') or ''}".strip(),
            mcp="audit_llm_analyze_host",
            status="files",
        )
        return {
            "success": True,
            "mode": "service_files",
            "project_id": project_id,
            "target_id": target_id,
            "target_name": target.get("ip_or_hostname"),
            "service": {
                "port": service.get("port"),
                "protocol": service.get("protocol"),
                "service_name": service.get("service_name"),
                "version": service.get("version"),
            },
            "tasks": tasks,
            "instructions": instructions,
        }

    return _handle(_impl)


@mcp.tool(structured_output=False)
def audit_llm_execute_poc(
    project_id: str,
    target_id: str,
    command: str,
    reason: str,
    timeout: int = 600
) -> str:
    """
    [Type 2 Mode] Execute a PoC test proposed by the LLM.
    
    After analyzing host enumeration results with audit_llm_analyze_host,
    use this tool to execute safe proof-of-concept tests.
    
    All commands are validated against security constraints:
    - No DoS attacks
    - No brute-force attacks
    - No destructive operations
    - No system manipulation
    
    Args:
        project_id: Project ID
        target_id: Target ID
        command: Command to execute (e.g., "curl -k https://10.19.220.25/admin")
        reason: Explanation of why you're running this PoC
        timeout: Timeout in seconds (default: 600)
    
    Returns:
        JSON with command output (stdout, stderr, exit_code)
    """
    def _impl():
        from audit_orchestrator.core.command_validator import validate_safe_command
        from audit_orchestrator.core.kali_client import KaliMCPClient
        
        orch = get_orchestrator()
        
        # Validate project and target
        project = orch.store.get_project(project_id)
        target = orch.store.get_target(target_id)
        target_name = target.get("ip_or_hostname")
        
        # Check execution mode
        if project.get("execution_mode") != "type_2_post_host_llm":
            raise AuditOrchestratorError(
                "invalid_mode",
                f"This tool is only for Type 2 mode. Project is in {project.get('execution_mode')} mode."
            )
        
        # Validate command safety
        is_safe, reason_blocked = validate_safe_command(command)
        if not is_safe:
            raise AuditOrchestratorError(
                "unsafe_command",
                f"Command blocked: {reason_blocked}"
            )
        
        _show_llm(
            project["base_path"],
            asset=target_name,
            phase="LLM",
            llm="asking",
            mcp="audit_llm_execute_poc",
            command=command,
            ask=reason,
            status="running",
        )
        kali_client = KaliMCPClient(orch.settings.kali_server_url)
        result = asyncio.run(kali_client.execute(command, timeout))
        reply = result.get("stdout") or result.get("stderr") or ""
        _record_llm_prompt(
            project["base_path"],
            target_name,
            f"Command finished: {command}\nReason: {reason}",
            answer=reply,
            mcp="audit_llm_execute_poc",
            command=command,
            output=reply,
            status=f"exit {result.get('exit_code')}",
        )

        orch.store.log_bitacora(
            project_id=project_id,
            target_id=target_id,
            operation=f"LLM PoC (Type 2): {command}",
            result="completed" if result["success"] else "error",
            notes=f"Reason: {reason}\nExit: {result['exit_code']}"
        )
        
        return {
            "success": True,
            "target": target_name,
            "command": command,
            "reason": reason,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "execution_time": result.get("execution_time", 0)
        }
    
    return _handle(_impl)


@mcp.tool(structured_output=False)
def audit_llm_get_context(
    project_id: str,
    target_id: str
) -> str:
    """
    [Type 3] Show the prompt for the port whose enumeration just finished.

    Read prompt. It contains that port's commands and excerpts.
    Optional: audit_record_finding, or audit_llm_next_command to repeat or deepen that port.
    The next port runs only when you call continue_with, which is audit_llm_continue.
    """
    def _impl():
        orch = get_orchestrator()
        
        # Validate project and target
        project = orch.store.get_project(project_id)
        target = orch.store.get_target(target_id)
        
        # Check execution mode
        if project.get("execution_mode") != "type_3_interactive_llm":
            return {
                "error": True,
                "message": f"This tool is only for Type 3 mode. Project is in {project.get('execution_mode')} mode."
            }
        
        handoff = orch.type3_handoff(project_id, target_id)
        step = handoff.get("step") or {}
        target_name = target.get("ip_or_hostname") or target_id
        prompt = handoff.get("prompt") or ""
        _record_llm_prompt(
            project["base_path"],
            target_name,
            prompt,
            service=f"{step.get('port') or '-'}/{step.get('protocol') or 'tcp'} {step.get('service_name') or ''}".strip(),
            mcp="audit_llm_get_context",
        )
        try:
            state = orch.store.get_llm_execution_state(project_id, target_id)
        except ValueError:
            state = {
                "commands_executed": 0,
                "execution_time_seconds": 0.0,
                "last_command": None,
                "last_output": None
            }
        max_commands = 50
        max_time = 1800
        return {
            "success": True,
            "project_id": project_id,
            "target_id": target_id,
            "target_name": target.get("ip_or_hostname"),
            "step": handoff["step"],
            "prompt": handoff["prompt"],
            "continue_with": handoff["continue_with"],
            "instructions": handoff["prompt"],
            "limits": {
                "max_commands": max_commands,
                "max_time_seconds": max_time,
                "commands_remaining": max_commands - state.get("commands_executed", 0),
                "time_remaining": max_time - state.get("execution_time_seconds", 0),
            },
        }
    
    return _handle(_impl)


@mcp.tool(structured_output=False)
async def audit_llm_continue(
    project_id: str,
    target_id: str,
) -> str:
    """
    [Type 3] LLM finished the current profile step. Run the next profile script.

    Call this after analyzing the port that just finished. Optional extra commands
    and findings belong in audit_llm_next_command and audit_record_finding before this call.
    Returns the next port's prompt, or done=true when the profile for this target is finished.
    """
    orch = get_orchestrator()
    project = orch.store.get_project(project_id)
    _show_llm(
        project["base_path"],
        asset=orch.store.get_target(target_id).get("ip_or_hostname") or target_id,
        phase="LLM",
        status="running",
        llm="continue profile",
        mcp="audit_llm_continue",
        command="-",
        output="-",
        ask="-",
        answer="-",
        last="next port",
    )
    try:
        result = await orch.continue_type3(project_id, target_id)
        if result.get("done"):
            step = None
            prompt = None
            note = "Profile finished for this target."
            action = None
            continue_with = None
        else:
            handoff = orch.type3_handoff(project_id, target_id)
            step = handoff["step"]
            note = handoff["prompt"]
            action = handoff["prompt"]
            continue_with = handoff["continue_with"]
            prompt = handoff["prompt"]
        return _ok({
            "success": True,
            "done": bool(result.get("done")),
            "project_id": project_id,
            "target_id": target_id,
            "target_name": result.get("target_name"),
            "findings_created": result.get("findings_created", 0),
            "step": step,
            "prompt": prompt,
            "continue_with": continue_with,
            "next_action": action,
            "note": note,
        })
    except AuditOrchestratorError as e:
        return _err(e.code, e.message)
    except Exception as e:
        return _err("internal_error", str(e))


@mcp.tool(structured_output=False)
def audit_llm_next_command(
    project_id: str,
    target_id: str,
    command: str,
    reason: str,
    timeout: int = 600
) -> str:
    """
    [Type 3] Run one extra command for the port that is waiting.

    Use it only to repeat or deepen that same port. Do not send a command
    that already returned output. When the port needs nothing more, call
    audit_llm_continue instead. Limits: 50 commands and 30 minutes per target.
    
    Args:
        project_id: Project ID
        target_id: Target ID
        command: Command to execute
        reason: Your reasoning for executing this command
        timeout: Timeout in seconds (default: 600)
    
    Returns:
        JSON with command output and remaining limits
    """
    def _impl():
        from audit_orchestrator.core.command_validator import validate_safe_command
        from audit_orchestrator.core.kali_client import KaliMCPClient
        
        orch = get_orchestrator()
        
        # Validate project and target
        project = orch.store.get_project(project_id)
        target = orch.store.get_target(target_id)
        target_name = target.get("ip_or_hostname")
        
        # Check execution mode
        if project.get("execution_mode") != "type_3_interactive_llm":
            raise AuditOrchestratorError(
                "invalid_mode",
                f"This tool is only for Type 3 mode. Project is in {project.get('execution_mode')} mode."
            )
        
        # Get current execution state
        try:
            state = orch.store.get_llm_execution_state(project_id, target_id)
        except ValueError:
            # Create state if doesn't exist
            state_id = orch.store.create_llm_execution_state(project_id, target_id)
            state = orch.store.get_llm_execution_state_by_id(state_id)
        
        # Check limits
        MAX_COMMANDS = 50
        MAX_TIME = 1800  # 30 minutes
        
        commands_executed = state.get("commands_executed", 0)
        time_used = state.get("execution_time_seconds", 0.0)
        
        if commands_executed >= MAX_COMMANDS:
            raise AuditOrchestratorError(
                "limit_reached",
                f"Command limit reached: {MAX_COMMANDS} commands executed"
            )
        
        if time_used >= MAX_TIME:
            raise AuditOrchestratorError(
                "limit_reached",
                f"Time limit reached: {MAX_TIME}s ({time_used:.1f}s used)"
            )

        previous = state.get("last_command") or ""
        if previous and _normalize_command(previous) == _normalize_command(command):
            return _continue_after_repeat(orch, project, project_id, target_id, target_name, command)
        
        # Validate command safety
        is_safe, reason_blocked = validate_safe_command(command)
        if not is_safe:
            raise AuditOrchestratorError(
                "unsafe_command",
                f"Command blocked: {reason_blocked}"
            )
        
        _show_llm(
            project["base_path"],
            asset=target_name,
            phase="LLM",
            llm="asking",
            mcp="audit_llm_next_command",
            command=command,
            ask=reason,
            status="running",
        )
        kali_client = KaliMCPClient(orch.settings.kali_server_url)
        result = asyncio.run(kali_client.execute(command, timeout))
        reply = result.get("stdout") or result.get("stderr") or ""
        next_action = (
            "Do not send this command again. Read stdout. "
            "If this port needs nothing more, call "
            f'audit_llm_continue(project_id="{project_id}", target_id="{target_id}"). '
            "Send another audit_llm_next_command only when the command is different "
            "and it deepens this same port."
        )
        _record_llm_prompt(
            project["base_path"],
            target_name,
            next_action,
            answer=reply,
            mcp="audit_llm_next_command",
            command=command,
            output=reply,
            status=f"exit {result.get('exit_code')}",
        )

        # Update execution state
        new_commands = commands_executed + 1
        new_time = time_used + result.get("execution_time", 0)
        
        orch.store.update_llm_execution_state(
            state["state_id"],
            commands_executed=new_commands,
            execution_time_seconds=new_time,
            last_command=command,
            last_output=result.get("stdout", "")
        )
        
        # Log to bitacora
        orch.store.log_bitacora(
            project_id=project_id,
            target_id=target_id,
            operation=f"LLM Command #{new_commands} (Type 3): {command}",
            result="completed" if result["success"] else "error",
            notes=f"Reason: {reason}\nTime: {new_time:.1f}s / {MAX_TIME}s\nCommands: {new_commands}/{MAX_COMMANDS}"
        )
        
        return {
            "success": True,
            "target": target_name,
            "command": command,
            "reason": reason,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "execution_time": result.get("execution_time", 0),
            "limits_status": {
                "commands_executed": new_commands,
                "commands_remaining": MAX_COMMANDS - new_commands,
                "time_elapsed": new_time,
                "time_remaining": MAX_TIME - new_time,
                "limit_reached": new_commands >= MAX_COMMANDS or new_time >= MAX_TIME
            },
            "continue_with": {
                "tool": "audit_llm_continue",
                "project_id": project_id,
                "target_id": target_id,
            },
            "next_action": next_action,
        }
    
    return _handle(_impl)


# ===== Main Entry Point =====

def main() -> None:
    """Main entry point for MCP server"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Audit Orchestrator MCP Server"
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Data directory for SQLite database"
    )
    parser.add_argument(
        "--kali-server-url",
        default=None,
        help="MCP Kali server URL (default: http://127.0.0.1:5001)"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for SSE transport"
    )
    
    args = parser.parse_args()
    
    # Initialize global settings
    global _settings, _store, _orchestrator
    _settings = Settings.from_args(
        data_dir=args.data_dir,
        kali_server_url=args.kali_server_url
    )
    _store = AuditStore(_settings)
    _orchestrator = AuditOrchestrator(_settings, _store)
    
    # Run MCP server
    if args.transport == "sse":
        # SSE transport
        if hasattr(mcp, "settings") and hasattr(mcp.settings, "host"):
            mcp.settings.host = args.host
            mcp.settings.port = args.port
            mcp.run(transport="sse")
        else:
            mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        # stdio transport (default)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
