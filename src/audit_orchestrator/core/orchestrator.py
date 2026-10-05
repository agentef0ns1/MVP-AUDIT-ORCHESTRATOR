"""
Audit orchestration logic
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from audit_orchestrator.config import Settings
from audit_orchestrator.core.errors import AuditOrchestratorError, ProjectNotFoundError
from audit_orchestrator.core.filesystem import WorkspaceManager, create_resumen_auditoria
from audit_orchestrator.core.kali_client import KaliClientFactory, KaliMCPClient
from audit_orchestrator.core.parser import (
    format_targets_summary,
    get_target_count,
    get_total_port_count,
    parse_nmap_output,
    validate_targets,
)
from audit_orchestrator.core.live_screen import LiveScreen
from audit_orchestrator.core.store import AuditStore
from audit_orchestrator.core.tool_installer import (
    extract_tool_name,
    get_check_command,
    get_install_command,
)
from audit_orchestrator.core.command_normalizer import normalize_command


class AuditProfile:
    """Audit profile configuration"""
    
    def __init__(self, profile_data: dict[str, Any]):
        self.profile_id = profile_data["profile_id"]
        self.max_time_per_service = profile_data.get("max_time_per_service", 900)
        self.tasks = profile_data.get("tasks", {})
        self.restrictions = profile_data.get("restrictions", {})
    
    def get_tasks_for_service(self, service_name: str) -> list[dict[str, Any]]:
        """Get audit tasks for a service type"""
        # Get service-specific tasks
        tasks = []
        
        # Add all_services tasks
        all_services_count = 0
        if "all_services" in self.tasks:
            all_services_count = len(self.tasks["all_services"])
            tasks.extend(self.tasks["all_services"])
        
        # Add service-specific tasks
        service_lower = service_name.lower()
        service_specific_added = False
        
        # Check for exact match first
        if service_lower in self.tasks:
            tasks.extend(self.tasks[service_lower])
            service_specific_added = True
        # Check for http/https
        elif "http" in service_lower or service_lower in ("www", "web"):
            # Detect SSL/TLS services (ssl/http, https, tls, ssl/radan-http, etc.)
            if ("ssl" in service_lower or "tls" in service_lower or 
                service_lower == "https") and "https" in self.tasks:
                tasks.extend(self.tasks["https"])
                service_specific_added = True
            elif "http" in self.tasks:
                tasks.extend(self.tasks["http"])
                service_specific_added = True
        # Check for other known services
        elif service_lower in ("ssh", "ftp", "smb", "smtp", "mysql", "postgres"):
            if service_lower in self.tasks:
                tasks.extend(self.tasks[service_lower])
                service_specific_added = True
        
        # Add default tasks if no service-specific match (only all_services tasks)
        if not service_specific_added and "default" in self.tasks:
            tasks.extend(self.tasks["default"])
        
        return tasks
    
    @classmethod
    def load_from_file(cls, profile_path: Path) -> AuditProfile:
        """Load profile from JSON file"""
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            return cls(data)
        except Exception as e:
            raise AuditOrchestratorError(
                "profile_load_error",
                f"Failed to load profile from {profile_path}: {e}"
            )


class AuditOrchestrator:
    """Main orchestrator for security audits"""
    
    def __init__(
        self,
        settings: Settings,
        store: AuditStore,
        live: LiveScreen | None = None,
    ):
        self.settings = settings
        self.store = store
        self.live = live
        KaliClientFactory.configure(settings.kali_server_url)

    def _attach_live_file(self, base_path: Path) -> None:
        """Point the screen at the workspace frame file. Never opens a terminal."""
        if self.live is None:
            return
        try:
            self.live.frame_path = base_path / "audit-live.txt"
        except Exception:
            return

    def _live(self, *, force: bool = False, solo: bool = False, **fields: Any) -> None:
        """Refresh one asset box. Failures never stop the audit."""
        if self.live is None:
            return
        try:
            self.live.update(force=force, solo=solo, **fields)
        except Exception:
            return

    def _close_run(
        self,
        project_id: str,
        targets_processed: int,
        targets_completed: int,
        targets_failed: int,
        findings_created: int,
    ) -> tuple[str, dict[str, Any]]:
        """Mark the project finished only when nothing is left pending."""
        stats = self.store.get_project_statistics(project_id)
        by_status = stats["targets_by_status"]
        awaiting_llm = by_status.get("pending_llm_analysis", 0)
        pending = by_status.get("pending", 0)
        pending += by_status.get("auditing", 0)
        pending += awaiting_llm
        if awaiting_llm:
            status = "pending_llm_analysis"
            last = f"{awaiting_llm} targets awaiting LLM analysis"
        elif pending == 0 and targets_failed == 0 and targets_processed > 0:
            self.store.update_project_status(project_id, "completed")
            status = "completed"
            last = "audit finished"
        elif pending:
            status = "partial"
            last = f"{pending} targets still pending"
        elif targets_failed:
            status = "failed"
            last = f"{targets_failed} targets failed"
        else:
            status = "completed"
            last = "audit finished"
        self._live(
            force=True,
            solo=True,
            phase="DONE",
            asset=f"{targets_completed} hosts",
            service="-",
            command="-",
            mcp="audit_run",
            llm="idle",
            status=status,
            last=last,
            progress=(
                f"hosts {targets_completed}   pending {pending}   "
                f"fail {targets_failed}   findings {findings_created}"
            ),
        )
        return status, stats
    
    async def start_audit(
        self,
        base_path: str,
        input_file: str = "open_ports.txt",
        profile: str = "default_blackbox",
        execution_mode: str = "type_1_no_llm",
        reset: bool = False
    ) -> dict[str, Any]:
        """
        Initialize a new audit project.
        
        Args:
            base_path: Base directory for audit workspace
            input_file: Name of input file with targets/ports
            profile: Audit profile to use
            execution_mode: Execution mode (type_1_no_llm, type_2_post_host_llm, type_3_interactive_llm)
            reset: If True, delete existing project and recreate from scratch
        
        Returns:
            Dictionary with project info and initial statistics
        """
        base_path_obj = Path(base_path)
        input_file_path = base_path_obj / input_file
        
        if not input_file_path.exists():
            raise AuditOrchestratorError(
                "input_file_not_found",
                f"Input file not found: {input_file_path}"
            )
        
        # Parse input file
        targets_data = parse_nmap_output(input_file_path)
        validate_targets(targets_data)
        
        # Check if project already exists for this base_path
        existing_projects = self.store.list_projects(limit=100)
        existing_project = None
        for proj in existing_projects:
            if proj["base_path"] == str(base_path_obj) and proj["input_file"] == input_file:
                existing_project = proj
                break
        
        # Handle reset or existing project
        if existing_project:
            if reset:
                # Delete existing project and all related data
                project_id = existing_project["project_id"]
                self.store.delete_project(project_id)
                existing_project = None
            else:
                # Reuse existing project
                return {
                    "project_id": existing_project["project_id"],
                    "base_path": str(base_path_obj),
                    "targets_count": self.store.get_project_statistics(existing_project["project_id"])["total_targets"],
                    "services_count": self.store.get_project_statistics(existing_project["project_id"])["total_services"],
                    "profile": existing_project["profile"],
                    "summary": f"Reusing existing project {existing_project['project_id']}",
                    "note": "Project already exists. Use reset=True to recreate, or use audit_run to continue."
                }
        
        # Create new project
        project = self.store.create_project(
            base_path=str(base_path_obj),
            input_file=input_file,
            profile=profile,
            execution_mode=execution_mode
        )
        project_id = project["project_id"]
        
        # Create workspace manager
        workspace = WorkspaceManager(base_path_obj)
        
        # Create targets and services
        target_count = 0
        service_count = 0
        
        for target_name, ports in targets_data.items():
            # Create workspace for target
            workspace_paths = workspace.create_target_workspace(target_name, ports)
            
            # Create target in database
            target = self.store.create_target(
                project_id=project_id,
                ip_or_hostname=target_name,
                work_dir=workspace_paths["target_dir"],
                ports=ports
            )
            target_id = target["target_id"]
            target_count += 1
            
            # Create services
            for port_info in ports:
                self.store.create_service(
                    target_id=target_id,
                    port=port_info["port"],
                    protocol=port_info.get("protocol", "tcp"),
                    service_name=port_info.get("service"),
                    version=port_info.get("version"),
                    max_time_seconds=self.settings.max_time_per_service
                )
                service_count += 1
            
            # Log to bitacora
            self.store.log_bitacora(
                project_id=project_id,
                target_id=target_id,
                operation=f"Target initialized: {target_name}",
                result="success",
                notes=f"Created workspace with {len(ports)} service(s)"
            )
        
        summary = format_targets_summary(targets_data)
        
        return {
            "project_id": project_id,
            "base_path": str(base_path_obj),
            "targets_count": target_count,
            "services_count": service_count,
            "profile": profile,
            "summary": summary
        }
    
    async def run_audit(
        self,
        project_id: str,
        max_targets: Optional[int] = None
    ) -> dict[str, Any]:
        """
        Run the audit orchestration loop.
        
        This is the main tolerant-to-failures loop that processes all targets
        and services sequentially without stopping on errors.
        
        Args:
            project_id: Project ID to resume/continue
            max_targets: Maximum targets to process (None = all)
        
        Returns:
            Summary of audit execution
        """
        # Get project
        project = self.store.get_project(project_id)
        base_path = Path(project["base_path"])
        profile_name = project["profile"]
        
        # Load audit profile
        profile = self._load_profile(profile_name)
        
        # Create workspace manager
        workspace = WorkspaceManager(base_path)
        self._attach_live_file(base_path)

        self._live(
            phase="PROCESS",
            mcp="audit_run",
            llm="idle",
            asset="-",
            service="-",
            command="-",
            status="starting",
            last=f"profile {profile_name}",
            progress="targets 0",
        )
        
        # Initialize counters
        targets_processed = 0
        targets_completed = 0
        targets_failed = 0
        services_audited = 0
        findings_created = 0
        pending_llm: list[dict[str, Any]] = []
        
        # Process targets sequentially
        async with KaliClientFactory.create() as kali_client:
            while True:
                # Get next pending target
                target = self.store.get_next_pending_target(project_id)
                
                if not target:
                    # No more targets to process
                    break
                
                if max_targets and targets_processed >= max_targets:
                    break
                
                target_id = target["target_id"]
                target_name = target["ip_or_hostname"]

                self._live(
                    phase="PROCESS",
                    asset=target_name,
                    service="-",
                    status="auditing",
                    mcp="audit_run",
                    last=f"target {target_name}",
                    progress=f"targets {targets_processed + 1}",
                )
                
                # Update target status
                self.store.update_target_status(target_id, "auditing")
                targets_processed += 1
                
                try:
                    # Audit this target
                    result = await self._audit_target(
                        project_id=project_id,
                        target=target,
                        profile=profile,
                        workspace=workspace,
                        kali_client=kali_client
                    )
                    
                    services_audited += result["services_audited"]
                    findings_created += result["findings_created"]

                    if result.get("requires_llm_analysis"):
                        self.store.update_target_status(target_id, "pending_llm_analysis")
                        pending_llm.append({
                            "project_id": project_id,
                            "target_id": target_id,
                            "target_name": target_name,
                            "host_context": result.get("host_context"),
                        })
                        self._live(
                            phase="LLM",
                            asset=target_name,
                            status="waiting",
                            llm="pending analysis",
                            last="enumeration done, awaiting LLM",
                        )
                        continue

                    # Mark target as completed
                    self.store.update_target_status(target_id, "completed")
                    targets_completed += 1
                    self._live(
                        phase="PROCESS",
                        asset=target_name,
                        status="completed",
                        last=f"target done findings {result['findings_created']}",
                        progress=(
                            f"targets {targets_completed} ok"
                            f" {targets_failed} fail"
                            f" findings {findings_created}"
                        ),
                    )
                    
                    self.store.log_bitacora(
                        project_id=project_id,
                        target_id=target_id,
                        operation=f"Target audit completed: {target_name}",
                        result="success",
                        notes=f"Audited {result['services_audited']} service(s), "
                              f"found {result['findings_created']} issue(s)"
                    )
                
                except Exception as e:
                    # Log error but continue with next target
                    self.store.update_target_status(
                        target_id,
                        "failed",
                        error=str(e)
                    )
                    targets_failed += 1
                    self._live(
                        phase="PROCESS",
                        asset=target_name,
                        status="failed",
                        last=str(e)[:80],
                        progress=f"targets {targets_completed} ok {targets_failed} fail",
                    )
                    
                    self.store.log_bitacora(
                        project_id=project_id,
                        target_id=target_id,
                        operation=f"Target audit failed: {target_name}",
                        result="error",
                        notes=str(e)
                    )
        
        status, stats = self._close_run(
            project_id,
            targets_processed,
            targets_completed,
            targets_failed,
            findings_created,
        )
        
        return {
            "done": status == "completed",
            "status": status,
            "project_id": project_id,
            "targets_processed": targets_processed,
            "targets_completed": targets_completed,
            "targets_failed": targets_failed,
            "services_audited": services_audited,
            "findings_created": findings_created,
            "pending_llm": pending_llm,
            "statistics": stats
        }
    
    async def run_audit_parallel(
        self,
        project_id: str,
        max_targets: Optional[int] = None,
        max_concurrent: int = 10,
        auto_review: bool = True
    ) -> dict[str, Any]:
        """
        Run audit with concurrent target processing.
        
        Args:
            project_id: Project ID
            max_targets: Max targets to process (None = all)
            max_concurrent: Max concurrent targets (default: 10)
            auto_review: Run auto-review before starting (default: True)
        
        Returns:
            Summary of audit execution with parallel stats
        """
        import time
        start_time = time.time()
        
        # Get project
        project = self.store.get_project(project_id)
        base_path = Path(project["base_path"])
        profile_name = project["profile"]
        
        # Load audit profile
        profile = self._load_profile(profile_name)
        
        # Create workspace manager
        workspace = WorkspaceManager(base_path)
        self._attach_live_file(base_path)

        self._live(
            phase="PROCESS",
            mcp="audit_run",
            llm="idle",
            asset="-",
            service="-",
            command="-",
            status="starting",
            last=f"parallel profile {profile_name}",
            progress=f"concurrency {max_concurrent}",
        )
        
        # Auto-review before starting (if enabled)
        re_enqueued = 0
        if auto_review:
            try:
                from audit_orchestrator.core.audit_reviewer import AuditReviewer
                reviewer = AuditReviewer(base_path, self.store)
                review_result = reviewer.review_project(project_id)
                re_enqueued = review_result.get("re_enqueued", 0)
                
                self.store.log_bitacora(
                    project_id=project_id,
                    operation="Auto-review completed",
                    result="info",
                    notes=f"Re-enqueued {re_enqueued} failed targets"
                )
                
                # Save report to workspace
                if review_result.get("report"):
                    report_path = base_path / "SERVICES_REPORT.md"
                    report_path.write_text(review_result["report"], encoding="utf-8")
            except Exception as e:
                # Log but don't fail if review fails
                self.store.log_bitacora(
                    project_id=project_id,
                    operation="Auto-review failed",
                    result="warning",
                    notes=f"Error: {e}"
                )
        
        # Get all pending targets
        pending_targets = self.store.get_all_pending_targets(project_id)
        
        if not pending_targets:
            stats = self.store.get_project_statistics(project_id)
            return {
                "done": True,
                "project_id": project_id,
                "targets_processed": 0,
                "targets_completed": 0,
                "targets_failed": 0,
                "services_audited": 0,
                "findings_created": 0,
                "re_enqueued": re_enqueued,
                "statistics": stats,
                "duration": time.time() - start_time,
                "parallel": True,
                "max_concurrent": max_concurrent
            }
        
        # Limit targets if specified
        targets_to_process = pending_targets[:max_targets] if max_targets else pending_targets
        
        self.store.log_bitacora(
            project_id=project_id,
            operation=f"Starting parallel audit with {len(targets_to_process)} targets",
            result="info",
            notes=f"Concurrency: {max_concurrent}, Auto-review: {auto_review}, Re-enqueued: {re_enqueued}"
        )
        
        # Create semaphore for concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Process targets in parallel with limit
        async with KaliClientFactory.create() as kali_client:
            tasks = [
                self._audit_target_with_semaphore(
                    semaphore, project_id, target, profile, workspace, kali_client
                )
                for target in targets_to_process
            ]
            
            # Wait for all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        aggregated = self._aggregate_results(results)
        
        status, stats = self._close_run(
            project_id,
            aggregated["targets_processed"],
            aggregated["targets_completed"],
            aggregated["targets_failed"],
            aggregated["findings_created"],
        )
        
        duration = time.time() - start_time
        
        self.store.log_bitacora(
            project_id=project_id,
            operation="Parallel audit completed",
            result="success",
            notes=f"Processed {aggregated['targets_processed']} targets in {duration:.1f}s, "
                  f"Completed: {aggregated['targets_completed']}, Failed: {aggregated['targets_failed']}"
        )
        
        return {
            "done": status == "completed",
            "status": status,
            "project_id": project_id,
            "targets_processed": aggregated["targets_processed"],
            "targets_completed": aggregated["targets_completed"],
            "targets_failed": aggregated["targets_failed"],
            "services_audited": aggregated["services_audited"],
            "findings_created": aggregated["findings_created"],
            "pending_llm": [
                {**item, "project_id": project_id}
                for item in aggregated.get("pending_llm", [])
            ],
            "re_enqueued": re_enqueued,
            "statistics": stats,
            "duration": duration,
            "parallel": True,
            "max_concurrent": max_concurrent
        }
    
    async def _audit_target_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        project_id: str,
        target: dict[str, Any],
        profile: AuditProfile,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> dict[str, Any]:
        """Audit single target with semaphore control"""
        async with semaphore:
            target_id = target["target_id"]
            target_name = target["ip_or_hostname"]

            self._live(
                phase="PROCESS",
                asset=target_name,
                service="-",
                status="auditing",
                mcp="audit_run",
                last=f"target {target_name}",
            )
            
            self.store.update_target_status(target_id, "auditing")
            
            try:
                result = await self._audit_target(
                    project_id, target, profile, workspace, kali_client
                )
                if result.get("requires_llm_analysis"):
                    self.store.update_target_status(target_id, "pending_llm_analysis")
                    self._live(
                        phase="LLM",
                        asset=target_name,
                        status="waiting",
                        llm="pending analysis",
                        last="enumeration done, awaiting LLM",
                    )
                    return {
                        "success": True,
                        "requires_llm_analysis": True,
                        "target": target_name,
                        "target_id": target_id,
                        "host_context": result.get("host_context"),
                        "services_audited": result.get("services_audited", 0),
                        "findings_created": result.get("findings_created", 0),
                    }

                self.store.update_target_status(target_id, "completed")
                self._live(
                    phase="PROCESS",
                    asset=target_name,
                    status="completed",
                    last=f"findings {result.get('findings_created', 0)}",
                )
                
                self.store.log_bitacora(
                    project_id=project_id,
                    target_id=target_id,
                    operation=f"Target audit completed: {target_name}",
                    result="success",
                    notes=f"Services: {result.get('services_audited', 0)}, Findings: {result.get('findings_created', 0)}"
                )
                
                return {
                    "success": True,
                    "target": target_name,
                    "target_id": target_id,
                    "services_audited": result.get("services_audited", 0),
                    "findings_created": result.get("findings_created", 0)
                }
            
            except Exception as e:
                self.store.update_target_status(target_id, "failed", error=str(e))
                self._live(
                    phase="PROCESS",
                    asset=target_name,
                    status="failed",
                    last=str(e)[:80],
                )
                
                self.store.log_bitacora(
                    project_id=project_id,
                    target_id=target_id,
                    operation=f"Target audit failed: {target_name}",
                    result="error",
                    notes=str(e)
                )
                
                return {
                    "success": False,
                    "target": target_name,
                    "target_id": target_id,
                    "error": str(e),
                    "services_audited": 0,
                    "findings_created": 0
                }
    
    def _aggregate_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate results from parallel execution"""
        targets_processed = 0
        targets_completed = 0
        targets_failed = 0
        services_audited = 0
        findings_created = 0
        pending_llm: list[dict[str, Any]] = []
        
        for result in results:
            # Handle exceptions
            if isinstance(result, Exception):
                targets_failed += 1
                continue
            
            targets_processed += 1
            
            if result.get("requires_llm_analysis"):
                pending_llm.append({
                    "target_id": result.get("target_id"),
                    "target_name": result.get("target"),
                    "host_context": result.get("host_context"),
                })
            elif result.get("success"):
                targets_completed += 1
            else:
                targets_failed += 1
            
            services_audited += result.get("services_audited", 0)
            findings_created += result.get("findings_created", 0)
        
        return {
            "targets_processed": targets_processed,
            "targets_completed": targets_completed,
            "targets_failed": targets_failed,
            "services_audited": services_audited,
            "findings_created": findings_created,
            "pending_llm": pending_llm,
        }
    
    async def _audit_target(
        self,
        project_id: str,
        target: dict[str, Any],
        profile: AuditProfile,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> dict[str, Any]:
        """Audit a single target - dispatches to appropriate execution mode"""
        target_id = target["target_id"]
        target_name = target["ip_or_hostname"]
        
        # Get execution_mode from project
        project = self.store.get_project(project_id)
        execution_mode = project.get("execution_mode", "type_1_no_llm")
        
        # Dispatch to appropriate method based on execution mode
        if execution_mode == "type_1_no_llm":
            return await self._audit_target_type1(
                project_id, target, profile, workspace, kali_client
            )
        elif execution_mode == "type_2_post_host_llm":
            return await self._audit_target_type2(
                project_id, target, profile, workspace, kali_client
            )
        elif execution_mode == "type_3_interactive_llm":
            return await self._audit_target_type3(
                project_id, target, profile, workspace, kali_client
            )
        else:
            raise AuditOrchestratorError(
                "invalid_execution_mode",
                f"Unknown execution_mode: {execution_mode}"
            )
    
    async def _audit_target_type1(
        self,
        project_id: str,
        target: dict[str, Any],
        profile: AuditProfile,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> dict[str, Any]:
        """Type 1: Fixed sequence from JSON (original behavior)"""
        target_id = target["target_id"]
        target_name = target["ip_or_hostname"]
        
        services_audited = 0
        findings_created = 0
        
        # Get all services for this target
        services = self.store.get_services_by_target(target_id)
        
        for service in services:
            service_id = service["service_id"]
            port = service["port"]
            protocol = service["protocol"]
            service_name = service.get("service_name", "unknown")
            
            try:
                # Audit this service
                result = await self._audit_service(
                    project_id=project_id,
                    target_id=target_id,
                    target_name=target_name,
                    service=service,
                    profile=profile,
                    workspace=workspace,
                    kali_client=kali_client
                )
                
                services_audited += 1
                findings_created += result.get("findings_created", 0)
                
            except Exception as e:
                # Log error but continue with next service
                self.store.update_service_status(
                    service_id,
                    "failed",
                    error=str(e)
                )
                
                self.store.log_bitacora(
                    project_id=project_id,
                    target_id=target_id,
                    service_id=service_id,
                    operation=f"Service audit failed: {port}/{protocol}",
                    result="error",
                    notes=str(e)
                )
                
                workspace.append_bitacora(
                    target_name,
                    f"SERVICE: {port}/{protocol} ({service_name})",
                    f"Audit failed: {e}",
                    result="error"
                )
        
        return {
            "services_audited": services_audited,
            "findings_created": findings_created
        }
    
    async def _audit_target_type2(
        self,
        project_id: str,
        target: dict[str, Any],
        profile: AuditProfile,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> dict[str, Any]:
        """Type 2: Execute JSON tasks, then await LLM analysis and PoC execution"""
        target_id = target["target_id"]
        target_name = target["ip_or_hostname"]
        
        services_audited = 0
        findings_created = 0
        all_outputs = []
        
        # Phase 1: Execute all predefined tasks from JSON (like Type 1)
        services = self.store.get_services_by_target(target_id)
        
        for service in services:
            service_id = service["service_id"]
            port = service["port"]
            protocol = service["protocol"]
            service_name = service.get("service_name", "unknown")
            
            try:
                result = await self._audit_service(
                    project_id=project_id,
                    target_id=target_id,
                    target_name=target_name,
                    service=service,
                    profile=profile,
                    workspace=workspace,
                    kali_client=kali_client
                )
                
                services_audited += 1
                findings_created += result.get("findings_created", 0)
                all_outputs.append({
                    "service": service,
                    "result": result
                })
                
            except Exception as e:
                self.store.update_service_status(
                    service_id,
                    "failed",
                    error=str(e)
                )
                
                self.store.log_bitacora(
                    project_id=project_id,
                    target_id=target_id,
                    service_id=service_id,
                    operation=f"Service audit failed: {port}/{protocol}",
                    result="error",
                    notes=str(e)
                )
                
                workspace.append_bitacora(
                    target_name,
                    f"SERVICE: {port}/{protocol} ({service_name})",
                    f"Audit failed: {e}",
                    result="error"
                )
        
        # Phase 2: Build context and mark for LLM analysis
        host_context = self._build_host_context(project_id, target_id)
        
        self._live(
            phase="LLM",
            asset=target_name,
            llm="pending analysis",
            mcp="audit_llm_analyze_host",
            status="waiting",
            last=f"{len(services)} services scanned",
        )
        self.store.log_bitacora(
            project_id=project_id,
            target_id=target_id,
            operation=f"Host enumeration completed for {target_name} - awaiting LLM analysis",
            result="pending_llm_analysis",
            notes=f"Services scanned: {len(services)}. LLM will analyze results and propose PoCs."
        )
        
        workspace.append_bitacora(
            target_name,
            "HOST ENUMERATION COMPLETED",
            f"All {len(services)} services scanned. Awaiting LLM analysis for PoC execution.",
            result="pending_llm"
        )
        
        return {
            "services_audited": services_audited,
            "findings_created": findings_created,
            "requires_llm_analysis": True,
            "target_id": target_id,
            "target_name": target_name,
            "host_context": host_context
        }
    
    async def _audit_target_type3(
        self,
        project_id: str,
        target: dict[str, Any],
        profile: AuditProfile,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> dict[str, Any]:
        """Type 3: LLM has full control, with limits (50 commands, 30 minutes)"""
        target_id = target["target_id"]
        target_name = target["ip_or_hostname"]
        
        # Create execution state tracker
        state_id = self.store.create_llm_execution_state(project_id, target_id)
        
        # Limits
        MAX_COMMANDS = 50
        MAX_TIME_SECONDS = 1800  # 30 minutes
        
        # Bootstrap: Execute initial nmap version scan
        services = self.store.get_services_by_target(target_id)
        bootstrap_output = ""
        
        if services:
            # Build port list for nmap
            ports = ",".join(str(s["port"]) for s in services)
            bootstrap_cmd = f"nmap -sV -p {ports} {target_name}"
            
            self._live(
                phase="LLM",
                asset=target_name,
                llm="bootstrap",
                mcp="kali POST /api/command",
                command=bootstrap_cmd,
                status="running",
            )
            try:
                result = await kali_client.execute(bootstrap_cmd, timeout=300)
                bootstrap_output = result.get("stdout", "")
                self._live(
                    phase="LLM",
                    asset=target_name,
                    status="done",
                    last="bootstrap nmap finished",
                    llm="control",
                )
                
                # Update execution state
                self.store.update_llm_execution_state(
                    state_id,
                    commands_executed=1,
                    execution_time_seconds=result.get("execution_time", 0),
                    last_command=bootstrap_cmd,
                    last_output=bootstrap_output
                )
                
                # Log to bitacora
                self.store.log_bitacora(
                    project_id=project_id,
                    target_id=target_id,
                    operation=f"Type 3 Bootstrap: {bootstrap_cmd}",
                    result="completed",
                    notes=f"Initial enumeration. LLM will take full control. Limits: {MAX_COMMANDS} commands, {MAX_TIME_SECONDS}s"
                )
                
                workspace.append_bitacora(
                    target_name,
                    "TYPE 3 BOOTSTRAP",
                    f"Initial scan completed. LLM now has full control (limits: {MAX_COMMANDS} cmds, 30 min)",
                    result="llm_control"
                )
                
            except Exception as e:
                self.store.log_bitacora(
                    project_id=project_id,
                    target_id=target_id,
                    operation=f"Type 3 Bootstrap failed: {bootstrap_cmd}",
                    result="error",
                    notes=str(e)
                )
        
        return {
            "services_audited": 1,
            "findings_created": 0,
            "requires_llm_control": True,
            "state_id": state_id,
            "limits": {
                "max_commands": MAX_COMMANDS,
                "max_time_seconds": MAX_TIME_SECONDS,
                "commands_used": 1,
                "time_used": result.get("execution_time", 0) if services else 0
            },
            "bootstrap_output": bootstrap_output
        }
    
    def _build_host_context(self, project_id: str, target_id: str) -> dict[str, Any]:
        """Build complete host context for LLM analysis"""
        target = self.store.get_target(target_id)
        services = self.store.get_services_by_target(target_id)
        tasks = self._attach_output_excerpts(self.store.get_tasks_by_target(target_id))
        findings = self.store.get_findings_by_target(target_id)
        bitacora = self.store.get_bitacora_by_target(target_id)
        
        return {
            "target": target,
            "services": services,
            "tasks": tasks,
            "findings": findings,
            "bitacora": bitacora,
            "summary": {
                "total_services": len(services),
                "total_tasks": len(tasks),
                "total_findings": len(findings),
                "completed_tasks": sum(1 for t in tasks if t.get("status") == "completed"),
                "failed_tasks": sum(1 for t in tasks if t.get("status") == "failed")
            }
        }

    def _attach_output_excerpts(
        self,
        tasks: list[dict[str, Any]],
        limit: int = 4000,
    ) -> list[dict[str, Any]]:
        """Attach a short copy of each task output so the agent can read it."""
        for task in tasks:
            path = task.get("output_path")
            if not path:
                continue
            output_file = Path(path)
            if not output_file.is_file():
                task["output_excerpt"] = f"(output file missing: {path})"
                continue
            try:
                text = output_file.read_text(encoding="utf-8", errors="ignore")
                task["output_excerpt"] = text[:limit]
            except OSError as exc:
                task["output_excerpt"] = f"(cannot read output: {exc})"
        return tasks
    
    async def _detect_ssl_on_port(
        self,
        target_name: str,
        port: int,
        kali_client: KaliMCPClient,
        workspace: WorkspaceManager
    ) -> bool:
        """
        Detect if a port is serving SSL/TLS.
        
        Uses openssl s_client to test SSL connectivity.
        
        Returns:
            True if SSL is detected, False otherwise
        """
        try:
            # Test SSL connection with openssl
            test_cmd = f"timeout 5 openssl s_client -connect {target_name}:{port} < /dev/null 2>&1 | grep -q 'Cipher'"
            result = await kali_client.execute_command(
                command=test_cmd,
                timeout=10
            )
            
            # If exit code is 0, SSL cipher was found
            if result.get("exit_code") == 0:
                workspace.append_bitacora(
                    target_name,
                    f"SSL Detection on {port}/tcp",
                    "✓ SSL/TLS detected - using HTTPS",
                    result="info"
                )
                return True
            else:
                workspace.append_bitacora(
                    target_name,
                    f"SSL Detection on {port}/tcp",
                    "✗ No SSL/TLS - using HTTP",
                    result="info"
                )
                return False
                
        except Exception as e:
            # On error, assume no SSL
            workspace.append_bitacora(
                target_name,
                f"SSL Detection on {port}/tcp",
                f"Detection failed: {e} - defaulting to HTTP",
                result="info"
            )
            return False
    
    async def _audit_service(
        self,
        project_id: str,
        target_id: str,
        target_name: str,
        service: dict[str, Any],
        profile: AuditProfile,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> dict[str, Any]:
        """Audit a single service with timeout"""
        service_id = service["service_id"]
        port = service["port"]
        protocol = service["protocol"]
        service_name = service.get("service_name", "unknown")
        max_time = service["max_time_seconds"]
        
        self._live(
            phase="PROCESS",
            asset=target_name,
            service=f"{port}/{protocol} {service_name}",
            status="running",
            mcp="audit_run",
            command="-",
            last=f"service {port}/{protocol}",
        )

        # Update service status
        self.store.update_service_status(service_id, "running")
        
        # Log start
        self.store.log_bitacora(
            project_id=project_id,
            target_id=target_id,
            service_id=service_id,
            operation=f"Starting audit: {port}/{protocol} ({service_name})",
            result="info",
            notes=f"Max time: {max_time}s"
        )
        
        workspace.append_bitacora(
            target_name,
            f"SERVICE: {port}/{protocol} ({service_name})",
            f"Starting audit (max {max_time}s)"
        )
        
        findings_created = 0
        
        try:
            # Detect SSL for HTTP services
            effective_service_name = service_name
            service_name_lower = service_name.lower()
            
            # Check if it's an HTTP service without explicit SSL
            is_http_service = ("http" in service_name_lower or 
                               service_name_lower in ("www", "web", "radan-http"))
            has_ssl_prefix = ("ssl" in service_name_lower or 
                              "tls" in service_name_lower or 
                              service_name_lower == "https")
            
            if is_http_service and not has_ssl_prefix:
                # Perform SSL detection
                workspace.append_bitacora(
                    target_name,
                    f"SERVICE: {port}/{protocol} ({service_name})",
                    "Checking for SSL/TLS...",
                    result="info"
                )
                
                has_ssl = await self._detect_ssl_on_port(
                    target_name, port, kali_client, workspace
                )
                
                if has_ssl:
                    # Use HTTPS tasks instead
                    effective_service_name = "https"
                    self._live(
                        phase="ANALYSIS",
                        asset=target_name,
                        service=f"{port}/{protocol} https",
                        mcp="kali POST /api/command",
                        last=f"SSL detect {port} -> https",
                        status="done",
                    )
                    self.store.log_bitacora(
                        project_id=project_id,
                        target_id=target_id,
                        service_id=service_id,
                        operation=f"SSL detected on {port}/tcp - using HTTPS profile",
                        result="info"
                    )
            
            # Get tasks for this service (with SSL detection applied)
            tasks = profile.get_tasks_for_service(effective_service_name)
            
            if not tasks:
                # No tasks defined, just mark as completed
                self.store.update_service_status(service_id, "completed")
                return {"findings_created": 0}
            
            # Execute tasks with overall timeout
            start_time = asyncio.get_event_loop().time()
            
            for task_config in tasks:
                # Check if we've exceeded max time
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= max_time:
                    self.store.update_service_status(service_id, "timeout")
                    workspace.append_bitacora(
                        target_name,
                        f"SERVICE: {port}/{protocol}",
                        f"Timeout after {elapsed:.1f}s",
                        result="timeout"
                    )
                    break
                
                # Execute task
                remaining_time = max_time - elapsed
                task_result = await self._execute_task(
                    project_id=project_id,
                    target_id=target_id,
                    target_name=target_name,
                    service_id=service_id,
                    port=port,
                    protocol=protocol,
                    service_name=service_name,
                    task_config=task_config,
                    workspace=workspace,
                    kali_client=kali_client,
                    timeout=min(remaining_time, 600)  # Max 10 min per task
                )
                
                # Analyze for automatic findings
                if task_result.get("success") and task_result.get("output"):
                    auto_findings = self._analyze_for_findings(
                        task_result["output"],
                        target_name,
                        port,
                        service_name
                    )
                    
                    for finding in auto_findings:
                        finding_result = await self._create_finding(
                            project_id=project_id,
                            target_id=target_id,
                            target_name=target_name,
                            service_id=service_id,
                            port=port,
                            service_name=service_name,
                            finding_data=finding,
                            workspace=workspace
                        )
                        if finding_result:
                            findings_created += 1
            
            # Mark service as completed
            self.store.update_service_status(service_id, "completed")
            
        except asyncio.TimeoutError:
            self.store.update_service_status(service_id, "timeout")
            workspace.append_bitacora(
                target_name,
                f"SERVICE: {port}/{protocol}",
                "Service audit timeout",
                result="timeout"
            )
        
        except Exception as e:
            self.store.update_service_status(service_id, "failed", error=str(e))
            raise
        
        return {"findings_created": findings_created}
    
    async def _ensure_tool_installed(
        self,
        command: str,
        target_name: str,
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient
    ) -> tuple[bool, str]:
        """
        Ensure tool is installed before execution.
        
        Returns:
            (is_installed: bool, message: str)
        """
        # Extract tool name from command
        tool = extract_tool_name(command)
        
        if not tool:
            return (True, "No tool to check")
        
        try:
            # Check if tool is installed
            check_cmd = get_check_command(tool)
            check_result = await kali_client.execute_command(
                command=check_cmd,
                timeout=10  # Quick check
            )
            
            # If check succeeded (exit_code 0), tool is installed
            if check_result.get("exit_code") == 0:
                return (True, f"Tool {tool} is already installed")
            
            # Tool not found, need to install
            workspace.append_bitacora(
                target_name,
                f"INSTALL: {tool}",
                f"Tool not found, installing..."
            )
            
            install_cmd = get_install_command(tool)
            install_result = await kali_client.execute_command(
                command=install_cmd,
                timeout=300  # 5 minutes for installation
            )
            
            if install_result.get("exit_code") == 0:
                workspace.append_bitacora(
                    target_name,
                    f"INSTALL: {tool}",
                    result="success"
                )
                return (True, f"Tool {tool} installed successfully")
            else:
                error_msg = f"Failed to install {tool}: {install_result.get('error', 'Unknown error')}"
                workspace.append_bitacora(
                    target_name,
                    f"INSTALL: {tool}",
                    result="failed",
                    details=error_msg
                )
                return (False, error_msg)
                
        except Exception as e:
            error_msg = f"Error checking/installing {tool}: {e}"
            try:
                workspace.append_bitacora(
                    target_name,
                    f"INSTALL: {tool}",
                    result="error",
                    details=error_msg
                )
            except Exception:
                pass
            return (False, error_msg)
    
    async def _execute_task(
        self,
        project_id: str,
        target_id: str,
        target_name: str,
        service_id: str,
        port: int,
        protocol: str,
        service_name: str,
        task_config: dict[str, Any],
        workspace: WorkspaceManager,
        kali_client: KaliMCPClient,
        timeout: float
    ) -> dict[str, Any]:
        """Execute a single audit task - NEVER raises exceptions"""
        task_type = task_config["type"]
        command_template = task_config["command"]
        
        try:
            # Format command with target and port
            command = command_template.format(
                target=target_name,
                port=port,
                protocol=protocol
            )
            # Normalize command to use absolute paths (prevents aliasing issues)
            command = normalize_command(command)
        except Exception as e:
            # If command formatting fails, return error
            return {
                "success": False,
                "output": "",
                "error": f"Command formatting error: {e}"
            }
        
        # Create task in database
        task = self.store.create_task(
            service_id=service_id,
            task_type=task_type,
            kali_command=command
        )
        task_id = task["task_id"]
        
        # Log task start
        try:
            workspace.append_bitacora(
                target_name,
                f"TASK: {task_type}",
                command=command
            )
        except Exception:
            pass  # Don't fail if logging fails
        
        # Update task status
        try:
            self.store.update_task_status(task_id, "running")
        except Exception:
            pass  # Don't fail if DB update fails

        self._live(
            phase="COMMAND",
            asset=target_name,
            service=f"{port}/{protocol} {service_name}",
            mcp="kali POST /api/command",
            command=command,
            status="running",
            llm="idle",
            last=task_type,
        )
        
        # Ensure tool is installed before execution
        try:
            is_installed, install_msg = await self._ensure_tool_installed(
                command=command,
                target_name=target_name,
                workspace=workspace,
                kali_client=kali_client
            )
            
            if not is_installed:
                # Tool installation failed, return error
                try:
                    self.store.update_task_status(
                        task_id,
                        status="failed",
                        error=install_msg
                    )
                except Exception:
                    pass
                
                return {
                    "success": False,
                    "output": "",
                    "error": install_msg
                }
        except Exception as e:
            # If tool check fails, log but continue anyway
            try:
                workspace.append_bitacora(
                    target_name,
                    f"WARNING: Tool check failed",
                    details=str(e)
                )
            except Exception:
                pass
        
        try:
            # Execute via Kali MCP - this should never raise
            result = await kali_client.execute_command(
                command=command,
                timeout=int(timeout)
            )
            
            # Save output to file (if we got output)
            output_path = None
            if result.get("output"):
                try:
                    output_path = workspace.write_enumeration_output(
                        target=target_name,
                        task_type=task_type,
                        output=result["output"]
                    )
                except Exception as e:
                    # If file write fails, log but continue
                    print(f"Warning: Failed to write output file: {e}")
            
            # Update task status
            status = "completed" if result.get("success") else "failed"
            try:
                self.store.update_task_status(
                    task_id,
                    status=status,
                    output_path=output_path,
                    duration_seconds=result.get("duration"),
                    error=result.get("error")
                )
            except Exception:
                pass  # Don't fail if DB update fails
            
            # Log result
            try:
                result_str = "success" if result.get("success") else "failed"
                if result.get("timed_out"):
                    result_str = "timeout"
                
                workspace.append_bitacora(
                    target_name,
                    f"TASK: {task_type}",
                    details=f"Duration: {result.get('duration', 0):.1f}s",
                    result=result_str
                )
                
                if output_path:
                    workspace.append_bitacora(
                        target_name,
                        f"OUTPUT: {output_path}"
                    )
            except Exception:
                pass  # Don't fail if logging fails
            
            outcome = "done" if result.get("success") else "failed"
            if result.get("timed_out"):
                outcome = "timeout"
            self._live(
                phase="COMMAND",
                asset=target_name,
                service=f"{port}/{protocol} {service_name}",
                mcp="kali POST /api/command",
                command=command,
                status=outcome,
                output=result.get("output") or result.get("error") or "",
                last=f"{task_type} {outcome}",
            )
            return result
        
        except Exception as e:
            self._live(
                phase="COMMAND",
                asset=target_name,
                status="failed",
                command=command,
                last=str(e)[:80],
            )
            # Catch any unexpected exceptions
            try:
                self.store.update_task_status(
                    task_id,
                    status="failed",
                    error=str(e)
                )
            except Exception:
                pass
            
            try:
                workspace.append_bitacora(
                    target_name,
                    f"TASK: {task_type}",
                    details=str(e),
                    result="error"
                )
            except Exception:
                pass
            
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
    def _analyze_for_findings(
        self,
        output: str,
        target: str,
        port: int,
        service_name: str
    ) -> list[dict[str, Any]]:
        """
        Analyze command output for automatic findings.
        
        Detects:
        - Anonymous access
        - Vulnerable versions (CVE mentions)
        - Default credentials
        - SSL/TLS issues
        - Missing WAF
        """
        findings = []
        output_lower = output.lower()
        
        # Check for anonymous access
        if any(kw in output_lower for kw in ["anonymous", "guest", "unauthenticated access"]):
            findings.append({
                "severity": "medium",
                "title": f"Anonymous Access Detected on {service_name}",
                "description": f"Service allows anonymous or unauthenticated access on port {port}",
                "evidence": self._extract_relevant_lines(output, ["anonymous", "guest", "unauth"]),
                "cwe": "CWE-306"
            })
        
        # Check for CVEs
        cve_pattern = r'CVE-\d{4}-\d{4,7}'
        cves = re.findall(cve_pattern, output, re.IGNORECASE)
        if cves:
            findings.append({
                "severity": "high",
                "title": f"Vulnerable Version Detected - {', '.join(set(cves))}",
                "description": f"Service version has known CVEs: {', '.join(set(cves))}",
                "evidence": self._extract_relevant_lines(output, cves),
                "exploit_available": True,
                "cwe": "CWE-1035"
            })
        
        # Check for default credentials
        if any(kw in output_lower for kw in ["default password", "default credential", "admin:admin"]):
            findings.append({
                "severity": "critical",
                "title": "Default Credentials Detected",
                "description": f"Service may be using default or weak credentials on port {port}",
                "evidence": self._extract_relevant_lines(output, ["default", "admin", "password"]),
                "cwe": "CWE-798"
            })
        
        # Check for SSL/TLS issues
        if "ssl" in service_name.lower() or port in (443, 8443):
            if any(kw in output_lower for kw in ["ssl", "tls", "weak cipher", "expired", "self-signed"]):
                if any(issue in output_lower for issue in ["weak", "vulnerable", "insecure", "deprecated"]):
                    findings.append({
                        "severity": "medium",
                        "title": "SSL/TLS Configuration Issues",
                        "description": f"Weak or insecure SSL/TLS configuration detected on port {port}",
                        "evidence": self._extract_relevant_lines(output, ["ssl", "tls", "cipher"]),
                        "cwe": "CWE-327"
                    })
        
        # Check for missing WAF (for web services)
        if service_name.lower() in ("http", "https", "web", "www"):
            if "no waf" in output_lower or "not protected" in output_lower:
                findings.append({
                    "severity": "low",
                    "title": "No WAF Detected",
                    "description": f"Web service on port {port} does not appear to have WAF protection",
                    "evidence": self._extract_relevant_lines(output, ["waf", "firewall"]),
                    "cwe": "CWE-693"
                })
        
        return findings
    
    def _extract_relevant_lines(self, text: str, keywords: list[str], context: int = 2) -> str:
        """Extract relevant lines from text containing keywords"""
        lines = text.split('\n')
        relevant = []
        
        for i, line in enumerate(lines):
            if any(kw.lower() in line.lower() for kw in keywords):
                # Get context lines
                start = max(0, i - context)
                end = min(len(lines), i + context + 1)
                relevant.extend(lines[start:end])
        
        return '\n'.join(relevant[:20])  # Limit output
    
    async def _create_finding(
        self,
        project_id: str,
        target_id: str,
        target_name: str,
        service_id: str,
        port: int,
        service_name: str,
        finding_data: dict[str, Any],
        workspace: WorkspaceManager
    ) -> bool:
        """Create a finding in database and filesystem"""
        try:
            # Create in database
            finding = self.store.create_finding(
                project_id=project_id,
                target_id=target_id,
                service_id=service_id,
                severity=finding_data["severity"],
                title=finding_data["title"],
                description=finding_data.get("description", ""),
                exploit_available=finding_data.get("exploit_available", False),
                cwe=finding_data.get("cwe")
            )
            
            finding_id = finding["finding_id"]
            self._live(
                phase="ANALYSIS",
                asset=target_name,
                service=f"{port}/{service_name}",
                mcp="audit_run",
                status="finding",
                last=f"{finding_data['severity']} {finding_data['title']}"[:80],
            )
            
            # Create finding file
            workspace.create_finding(
                target=target_name,
                finding_id=finding_id,
                severity=finding_data["severity"],
                title=finding_data["title"],
                description=finding_data.get("description", ""),
                service=f"{port}/{service_name}",
                cwe=finding_data.get("cwe"),
                evidence=finding_data.get("evidence", ""),
                exploit_available=finding_data.get("exploit_available", False)
            )
            
            # Log to bitacora
            self.store.log_bitacora(
                project_id=project_id,
                target_id=target_id,
                service_id=service_id,
                operation=f"Finding created: {finding_data['title']}",
                result="info",
                notes=f"Severity: {finding_data['severity']}"
            )
            
            return True
        
        except Exception as e:
            # Log error but don't fail
            print(f"Warning: Failed to create finding: {e}")
            return False
    
    def _load_profile(self, profile_name: str) -> AuditProfile:
        """Load audit profile from file"""
        # Get profile path
        profiles_dir = Path(__file__).parent.parent / "audit_profiles"
        profile_path = profiles_dir / f"{profile_name}.json"
        
        if not profile_path.exists():
            raise AuditOrchestratorError(
                "profile_not_found",
                f"Audit profile not found: {profile_name}"
            )
        
        return AuditProfile.load_from_file(profile_path)
    
    def get_audit_status(self, project_id: str) -> dict[str, Any]:
        """Get current audit status"""
        try:
            project = self.store.get_project(project_id)
        except ProjectNotFoundError:
            raise
        
        stats = self.store.get_project_statistics(project_id)
        last_entry = self.store.get_last_bitacora_entry(project_id)
        
        # Get next pending target
        next_target = self.store.get_next_pending_target(project_id)
        
        return {
            "project_id": project_id,
            "status": project["status"],
            "base_path": project["base_path"],
            "profile": project["profile"],
            "statistics": stats,
            "last_operation": last_entry,
            "next_target": next_target["ip_or_hostname"] if next_target else None,
            "done": next_target is None
        }
    
    def reset_project(self, project_id: str) -> dict[str, Any]:
        """
        Reset a project's targets and services to 'pending' status.
        
        Use this when you want to re-run an audit from scratch without
        deleting the project structure.
        
        Args:
            project_id: Project ID to reset
        
        Returns:
            Dictionary with reset statistics
        """
        # Verify project exists
        project = self.store.get_project(project_id)
        if not project:
            raise AuditOrchestratorError(
                "project_not_found",
                f"Project not found: {project_id}"
            )
        
        # Reset all targets, services, and tasks to pending
        result = self.store.reset_project_status(project_id)
        
        # Log the reset
        self.store.log_bitacora(
            project_id=project_id,
            operation="Project reset",
            result="success",
            notes=f"Reset {result['targets_reset']} targets, {result['services_reset']} services, {result['tasks_reset']} tasks"
        )
        
        return result
    
    def finalize_audit(self, project_id: str) -> dict[str, Any]:
        """Finalize audit and generate executive summary"""
        project = self.store.get_project(project_id)
        base_path = Path(project["base_path"])
        
        stats = self.store.get_project_statistics(project_id)
        
        # Prepare summaries
        targets_summary = {
            "total": stats["total_targets"],
            "completed": stats["targets_by_status"].get("completed", 0),
            "failed": stats["targets_by_status"].get("failed", 0),
            "pending": stats["targets_by_status"].get("pending", 0)
        }
        
        findings_summary = {
            "total": stats["total_findings"],
            "critical": stats["findings_by_severity"].get("critical", 0),
            "high": stats["findings_by_severity"].get("high", 0),
            "medium": stats["findings_by_severity"].get("medium", 0),
            "low": stats["findings_by_severity"].get("low", 0),
            "info": stats["findings_by_severity"].get("info", 0),
            "total_services": stats["total_services"]
        }
        
        # Create executive summary
        resumen_path = create_resumen_auditoria(
            base_path=base_path,
            project_id=project_id,
            targets_summary=targets_summary,
            findings_summary=findings_summary
        )
        
        # Update project as completed
        self.store.update_project_status(project_id, "completed")
        
        return {
            "project_id": project_id,
            "resumen_path": resumen_path,
            "base_path": str(base_path),
            "statistics": stats
        }
