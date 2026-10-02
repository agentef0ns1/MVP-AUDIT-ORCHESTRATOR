"""
MCP Server for Audit Orchestrator
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from audit_orchestrator.mcp_compat import FastMCP
from audit_orchestrator.config import Settings
from audit_orchestrator.core.errors import AuditOrchestratorError
from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.core.store import AuditStore

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


def _err(code: str, message: str) -> str:
    """Format error response"""
    return json.dumps({
        "error": True,
        "code": code,
        "message": message
    }, ensure_ascii=False)


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
            - "type_3_interactive_llm": LLM has full control (limits: 50 commands, 30 min)
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
def audit_run(
    project_id: str,
    max_targets: int | None = None
) -> str:
    """
    Run the audit orchestration loop.
    
    This is the main audit execution that processes all pending targets
    and services. It is fault-tolerant and will continue even if individual
    tasks fail.
    
    The loop will:
    - Process targets sequentially
    - Execute service-specific audit tasks
    - Respect 15-minute timeout per service
    - Automatically detect common vulnerabilities
    - Log all operations to bitacora
    - Continue on errors without stopping
    
    Args:
        project_id: Project ID from audit_start
        max_targets: Optional limit on targets to process (for testing)
    
    Returns:
        JSON with execution summary, statistics, and done status
    """
    orchestrator = get_orchestrator()
    return _handle(
        orchestrator.run_audit,
        project_id=project_id,
        max_targets=max_targets
    )


@mcp.tool(structured_output=False)
def audit_start_and_run(
    base_path: str,
    input_file: str = "open_ports.txt",
    profile: str = "default_blackbox",
    execution_mode: str = "type_1_no_llm",
    reset: bool = False,
    max_targets: int | None = None
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
    
    Returns:
        JSON with:
        - project_id: For future reference if needed
        - Initial setup info (targets_count, services_count)
        - Execution results (targets_processed, findings_created)
        - Final status
    """
    def _impl():
        orch = get_orchestrator()
        
        # Step 1: Start audit
        start_result = asyncio.run(orch.start_audit(
            base_path, input_file, profile, execution_mode, reset
        ))
        
        project_id = start_result["project_id"]
        
        # Step 2: Run audit
        run_result = asyncio.run(orch.run_audit(project_id, max_targets))
        
        # Combine results
        return {
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
            "status": run_result.get("status", "completed"),
            "note": "Audit started and executed successfully. Results in: " + base_path
        }
    
    return _handle(_impl)


@mcp.tool(structured_output=False)
def audit_resume(
    base_path: str,
    input_file: str = "open_ports.txt",
    max_targets: int | None = None
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
    def _impl():
        orch = get_orchestrator()
        store = orch.store
        
        # Find project by path
        try:
            project = store.get_project_by_path(base_path, input_file)
            project_id = project["project_id"]
        except Exception as e:
            raise AuditOrchestratorError(
                "project_not_found",
                f"No audit project found at {base_path}. Use audit_start_and_run() to create one."
            )
        
        # Run audit
        run_result = asyncio.run(orch.run_audit(project_id, max_targets))
        
        return {
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
    
    return _handle(_impl)


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
    target_id: str
) -> str:
    """
    [Type 2 Mode] Get complete host context for LLM analysis.
    
    Returns all enumeration results for a host after JSON tasks complete.
    The LLM should analyze the outputs and propose safe PoC tests.
    
    Use this after audit_run completes for a target in Type 2 mode to get
    all the data needed for analysis.
    
    Args:
        project_id: Project ID
        target_id: Target ID to analyze
    
    Returns:
        JSON with host_context (target, services, tasks, findings, bitacora)
    """
    def _impl():
        orch = get_orchestrator()
        
        # Validate project and target exist
        project = orch.store.get_project(project_id)
        target = orch.store.get_target(target_id)
        
        # Check execution mode
        if project.get("execution_mode") != "type_2_post_host_llm":
            return {
                "error": True,
                "message": f"This tool is only for Type 2 mode. Project is in {project.get('execution_mode')} mode."
            }
        
        # Build context
        context = orch._build_host_context(project_id, target_id)
        
        return {
            "success": True,
            "project_id": project_id,
            "target_id": target_id,
            "target_name": target.get("ip_or_hostname"),
            "host_context": context,
            "instructions": (
                "Analyze the enumeration outputs. "
                "Look for potential vulnerabilities, misconfigurations, and attack vectors. "
                "Propose safe PoC tests (no DoS, no brute-force, no exploitation). "
                "Use audit_llm_execute_poc to execute your proposed tests."
            )
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
        
        # Execute command
        kali_client = KaliMCPClient(orch.settings.kali_server_url)
        result = asyncio.run(kali_client.execute(command, timeout))
        
        # Log to bitacora
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
    [Type 3 Mode] Get current context for LLM-driven audit.
    
    Returns current state including previous command outputs and execution limits.
    Use this to decide what command to run next.
    
    Args:
        project_id: Project ID
        target_id: Target ID
    
    Returns:
        JSON with host_context, execution_state, and limits
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
        
        # Get context and execution state
        context = orch._build_host_context(project_id, target_id)
        
        try:
            state = orch.store.get_llm_execution_state(project_id, target_id)
        except ValueError:
            # State doesn't exist yet
            state = {
                "commands_executed": 0,
                "execution_time_seconds": 0.0,
                "last_command": None,
                "last_output": None
            }
        
        MAX_COMMANDS = 50
        MAX_TIME = 1800  # 30 minutes
        
        return {
            "success": True,
            "project_id": project_id,
            "target_id": target_id,
            "target_name": target.get("ip_or_hostname"),
            "host_context": context,
            "execution_state": state,
            "limits": {
                "max_commands": MAX_COMMANDS,
                "max_time_seconds": MAX_TIME,
                "commands_remaining": MAX_COMMANDS - state.get("commands_executed", 0),
                "time_remaining": MAX_TIME - state.get("execution_time_seconds", 0)
            },
            "instructions": (
                "Based on the previous outputs, decide the next command to execute. "
                "Use audit_llm_next_command to execute it. "
                "You have full control within the limits. "
                "Focus on reconnaissance, enumeration, and safe vulnerability verification."
            )
        }
    
    return _handle(_impl)


@mcp.tool(structured_output=False)
def audit_llm_next_command(
    project_id: str,
    target_id: str,
    command: str,
    reason: str,
    timeout: int = 600
) -> str:
    """
    [Type 3 Mode] Execute next command in LLM-controlled audit.
    
    The LLM has full control to decide what command to run next based on
    previous results. Commands are validated against security constraints
    and execution limits are enforced (50 commands, 30 minutes per target).
    
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
        
        # Validate command safety
        is_safe, reason_blocked = validate_safe_command(command)
        if not is_safe:
            raise AuditOrchestratorError(
                "unsafe_command",
                f"Command blocked: {reason_blocked}"
            )
        
        # Execute command
        kali_client = KaliMCPClient(orch.settings.kali_server_url)
        result = asyncio.run(kali_client.execute(command, timeout))
        
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
            }
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
