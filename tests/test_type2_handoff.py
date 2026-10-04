"""Type 2 handoff: host context includes output text and stays pending."""
import tempfile
from pathlib import Path

from audit_orchestrator.config import Settings
from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.core.store import AuditStore


def test_host_context_includes_output_excerpt_and_stays_pending():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "nmap.txt"
        output.write_text("22/tcp open ssh OpenSSH 8.9\n", encoding="utf-8")

        settings = Settings(data_dir=str(root))
        settings.db_path = root / "audit.db"
        store = AuditStore(settings)
        project = store.create_project(
            base_path=str(root),
            input_file="open_ports.txt",
            execution_mode="type_2_post_host_llm",
        )
        target = store.create_target(
            project_id=project["project_id"],
            ip_or_hostname="192.168.1.39",
            work_dir=str(root),
            ports=[{"port": 22, "protocol": "tcp", "service": "ssh"}],
        )
        service = store.create_service(
            target_id=target["target_id"],
            port=22,
            protocol="tcp",
            service_name="ssh",
        )
        task = store.create_task(
            service_id=service["service_id"],
            task_type="nmap_version",
            kali_command="nmap -sV -p 22 192.168.1.39",
        )
        store.update_task_status(task["task_id"], "completed", output_path=str(output))
        store.log_bitacora(
            project_id=project["project_id"],
            target_id=target["target_id"],
            operation="enumeration done",
            result="success",
        )

        orch = AuditOrchestrator(settings, store)
        context = orch._build_host_context(project["project_id"], target["target_id"])

        assert context["tasks"][0]["output_excerpt"].startswith("22/tcp open ssh")
        assert context["summary"]["total_services"] == 1
        assert len(context["bitacora"]) == 1

        store.update_target_status(target["target_id"], "pending_llm_analysis")
        status, _stats = orch._close_run(
            project["project_id"],
            targets_processed=1,
            targets_completed=0,
            targets_failed=0,
            findings_created=0,
        )
        assert status == "pending_llm_analysis"
        assert store.get_target(target["target_id"])["status"] == "pending_llm_analysis"
        assert store.get_project(project["project_id"])["status"] != "completed"
