"""
Audit review and reconciliation system
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime

from audit_orchestrator.core.store import AuditStore


class AuditReviewer:
    """Reviews audit workspaces and detects failures"""
    
    def __init__(self, base_path: Path, store: AuditStore):
        self.base_path = Path(base_path)
        self.store = store
    
    def review_project(self, project_id: str) -> dict[str, Any]:
        """
        Review all targets in project and detect failures.
        
        Returns:
            {
                "total_targets": int,
                "failed_targets": list[dict],
                "re_enqueued": int,
                "report": str  # Markdown report
            }
        """
        project = self.store.get_project(project_id)
        targets = self.store.get_targets_by_project(project_id)
        
        failed_targets = []
        re_enqueued = 0
        
        for target in targets:
            failure_reason = self._is_target_failed(target)
            if failure_reason:
                failed_targets.append({
                    "ip": target["ip_or_hostname"],
                    "target_id": target["target_id"],
                    "status": target["status"],
                    "reason": failure_reason
                })
                
                # Re-enqueue: reset to pending
                self.store.update_target_status(
                    target["target_id"], 
                    "pending",
                    error=None
                )
                re_enqueued += 1
        
        # Generate report
        report = self._generate_services_report(project_id, targets)
        
        return {
            "total_targets": len(targets),
            "failed_targets": failed_targets,
            "re_enqueued": re_enqueued,
            "report": report
        }
    
    def _is_target_failed(self, target: dict) -> str | None:
        """
        Detect if target audit failed based on criteria.
        
        Returns:
            Failure reason string if failed, None if successful
        """
        target_name = target["ip_or_hostname"]
        safe_name = self._sanitize_filename(target_name)
        target_dir = self.base_path / safe_name
        
        # Check 1: Bitacora exists and has content
        bitacora_dir = target_dir / "bitacora"
        if not bitacora_dir.exists():
            return "No bitacora directory found"
        
        bitacora_files = list(bitacora_dir.glob("audit_*.log"))
        if not bitacora_files:
            return "No bitacora log files found"
        
        # Check 2: Read bitacora for error indicators
        latest_bitacora = max(bitacora_files, key=lambda f: f.stat().st_mtime)
        
        try:
            content = latest_bitacora.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return f"Cannot read bitacora: {e}"
        
        if not content.strip():
            return "Empty bitacora file"
        
        # Error indicators
        error_keywords = [
            "connection refused",
            "connection timed out",
            "no route to host",
            "host is down",
            "closed",
            "unreachable",
            "network is unreachable",
            "failed",
            "error",
            "timeout"
        ]
        
        # Count error lines vs total lines
        lines = [line for line in content.split("\n") if line.strip()]
        if not lines:
            return "Bitacora has no content lines"
        
        error_lines = sum(
            1 for line in lines 
            if any(kw in line.lower() for kw in error_keywords)
        )
        
        # If >80% error lines, consider failed
        if len(lines) > 5 and (error_lines / len(lines)) > 0.8:
            return f"Too many errors in bitacora ({error_lines}/{len(lines)} lines)"
        
        # Check 3: Enumeration outputs exist and have content
        enum_dir = target_dir / "enumeration"
        if enum_dir.exists():
            output_files = [
                f for f in enum_dir.glob("*.txt") 
                if f.name != "ports.json" and not f.name.startswith(".")
            ]
            
            if output_files:
                # Check if outputs have content (>100 bytes)
                files_with_content = [f for f in output_files if f.stat().st_size > 100]
                
                if not files_with_content:
                    return "All enumeration outputs are empty or minimal"
        
        # If we reach here, audit appears successful
        return None
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize target name for filesystem use"""
        return name.replace("/", "_").replace(":", "_").replace(" ", "_")
    
    def _generate_services_report(
        self, 
        project_id: str, 
        targets: list[dict]
    ) -> str:
        """
        Generate markdown report grouping machines by services.
        
        Returns markdown with format:
        # Services Report
        
        ## HTTP/HTTPS (80, 443, 8080, 8443)
        - 10.1.1.1 - ports: 80, 443
        - 10.1.1.5 - ports: 8080
        
        ## SSH (22)
        - 10.1.1.1 - ports: 22
        ...
        """
        # Get all services from DB
        services_by_target = {}
        for target in targets:
            target_id = target["target_id"]
            try:
                services = self.store.get_services_by_target(target_id)
                services_by_target[target["ip_or_hostname"]] = services
            except Exception:
                services_by_target[target["ip_or_hostname"]] = []
        
        # Group by service name
        service_groups = {}
        for target_name, services in services_by_target.items():
            for svc in services:
                svc_name = svc.get("service_name", "unknown")
                port = svc["port"]
                
                if svc_name not in service_groups:
                    service_groups[svc_name] = {"ports": set(), "targets": []}
                
                service_groups[svc_name]["ports"].add(port)
                service_groups[svc_name]["targets"].append({
                    "ip": target_name,
                    "port": port,
                    "status": svc.get("status", "unknown")
                })
        
        # Generate markdown
        report_lines = [
            "# Services Report",
            "",
            f"**Project**: {project_id}",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Targets**: {len(targets)}",
            "",
            "---",
            ""
        ]
        
        # Sort services by frequency (most common first)
        sorted_services = sorted(
            service_groups.items(),
            key=lambda x: len(x[1]["targets"]),
            reverse=True
        )
        
        for svc_name, data in sorted_services:
            ports_str = ", ".join(map(str, sorted(data["ports"])))
            report_lines.append(f"## {svc_name.upper()} (ports: {ports_str})")
            report_lines.append("")
            report_lines.append(f"**Total machines**: {len(data['targets'])}")
            report_lines.append("")
            
            # Group targets by status
            completed = [t for t in data["targets"] if t["status"] == "completed"]
            failed = [t for t in data["targets"] if t["status"] in ["failed", "timeout", "error"]]
            running = [t for t in data["targets"] if t["status"] in ["running", "auditing"]]
            
            if completed:
                report_lines.append(f"### Completed ({len(completed)})")
                report_lines.append("")
                for t in sorted(completed, key=lambda x: x["ip"]):
                    report_lines.append(f"- `{t['ip']}:{t['port']}`")
                report_lines.append("")
            
            if running:
                report_lines.append(f"### Running ({len(running)})")
                report_lines.append("")
                for t in sorted(running, key=lambda x: x["ip"]):
                    report_lines.append(f"- `{t['ip']}:{t['port']}` - {t['status']}")
                report_lines.append("")
            
            if failed:
                report_lines.append(f"### Failed/Timeout ({len(failed)})")
                report_lines.append("")
                for t in sorted(failed, key=lambda x: x["ip"]):
                    report_lines.append(f"- `{t['ip']}:{t['port']}` - {t['status']}")
                report_lines.append("")
            
            report_lines.append("---")
            report_lines.append("")
        
        return "\n".join(report_lines)
