"""Type 3 runs every profile task for one port, then waits for the LLM."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from audit_orchestrator.config import Settings
from audit_orchestrator.core.filesystem import WorkspaceManager
from audit_orchestrator.core.kali_client import KaliMCPClient
from audit_orchestrator.core.orchestrator import AuditOrchestrator, AuditProfile
from audit_orchestrator.core.store import AuditStore


@pytest.mark.anyio
async def test_execute_maps_command_result():
    client = KaliMCPClient("http://127.0.0.1:5001")

    async def fake_execute(payload, timeout):
        assert payload["command"] == "nmap -sV -p 80 10.19.220.6"
        assert timeout == 300
        return {
            "success": True,
            "output": "80/tcp open http",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
            "error": None,
            "duration": 1.5,
        }

    client._execute_via_mcp = fake_execute
    result = await client.execute("nmap -sV -p 80 10.19.220.6", timeout=300)
    assert result["stdout"] == "80/tcp open http"
    assert result["exit_code"] == 0
    assert result["execution_time"] >= 0
    assert result["success"] is True


def _profile() -> AuditProfile:
    return AuditProfile({
        "profile_id": "default_blackbox",
        "tasks": {
            "all_services": [
                {"type": "nmap_version", "command": "nmap -sV -p {port} {target}"},
                {"type": "nmap_scripts", "command": "nmap -sC -p {port} {target}"},
            ],
            "http": [
                {"type": "whatweb", "command": "whatweb http://{target}:{port}"},
            ],
        },
    })


@pytest.mark.anyio
async def test_type3_pauses_after_each_port(tmp_path: Path):
    store = MagicMock(spec=AuditStore)
    store.get_llm_execution_state.side_effect = ValueError("missing")
    store.create_llm_execution_state.return_value = "state-1"
    store.get_services_by_target.return_value = [
        {
            "service_id": "svc-22",
            "port": 22,
            "protocol": "tcp",
            "service_name": "ssh",
            "status": "pending",
        },
        {
            "service_id": "svc-80",
            "port": 80,
            "protocol": "tcp",
            "service_name": "http",
            "status": "pending",
        },
    ]
    from audit_orchestrator.core.live_screen import LiveScreen

    screen = LiveScreen(min_interval=0)
    orchestrator = AuditOrchestrator(Settings(kali_server_url="http://127.0.0.1:5001"), store, live=screen)
    orchestrator._detect_ssl_on_port = AsyncMock(return_value=False)
    calls = []

    async def execute_task(**kwargs):
        calls.append(kwargs["task_config"]["type"])
        return {
            "success": True,
            "output": f"output for {kwargs['task_config']['type']}",
            "command": kwargs["task_config"]["command"],
            "output_path": f"/tmp/{kwargs['task_config']['type']}.txt",
        }

    orchestrator._execute_task = execute_task
    target_dir = tmp_path / "10.19.220.6"
    (target_dir / "bitacora").mkdir(parents=True)
    (target_dir / "enumeration").mkdir()
    workspace = WorkspaceManager(tmp_path)
    target = {"target_id": "target-1", "ip_or_hostname": "10.19.220.6"}

    first = await orchestrator._audit_target_type3(
        "project-1", target, _profile(), workspace, MagicMock()
    )
    assert first["requires_llm_analysis"] is True
    assert first["step"]["port"] == 22
    assert first["step"]["service_name"] == "ssh"
    assert first["step"]["tasks"] == ["nmap_version", "nmap_scripts"]
    assert "output for nmap_version" in first["step"]["output_excerpt"]
    assert "output for nmap_scripts" in first["prompt"]
    assert 'audit_llm_continue(project_id="project-1", target_id="target-1")' in first["prompt"]
    assert "Stay on this port" in first["prompt"]
    painted = screen.render()
    assert "LLM ASK" in painted
    assert "Enumeration of one service is finished on 10.19.220.6" in painted
    assert "Service: 22/tcp ssh" in painted
    assert "output for nmap_version" in painted
    assert "LLM ANSWER" not in painted
    logged = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "LLM PROMPT" in logged
    assert "output for nmap_scripts" in logged
    assert calls == ["nmap_version", "nmap_scripts"]

    again = await orchestrator._audit_target_type3(
        "project-1", target, _profile(), workspace, MagicMock()
    )
    assert again["step"]["port"] == 22
    assert calls == ["nmap_version", "nmap_scripts"]

    store.get_project.return_value = {
        "execution_mode": "type_3_interactive_llm",
        "base_path": str(tmp_path),
        "profile": "default_blackbox",
    }
    store.get_target.return_value = target
    store.get_project_statistics.return_value = {"targets_by_status": {}}
    orchestrator._load_profile = lambda name: _profile()

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    orchestrator_factory = MagicMock()
    orchestrator_factory.create.return_value = _Client()
    import audit_orchestrator.core.orchestrator as orchestrator_module
    original = orchestrator_module.KaliClientFactory
    orchestrator_module.KaliClientFactory = orchestrator_factory
    try:
        second = await orchestrator.continue_type3("project-1", "target-1")
    finally:
        orchestrator_module.KaliClientFactory = original

    assert second["done"] is False
    assert second["step"]["port"] == 80
    assert second["step"]["tasks"] == ["nmap_version", "nmap_scripts", "whatweb"]
    assert calls == [
        "nmap_version",
        "nmap_scripts",
        "nmap_version",
        "nmap_scripts",
        "whatweb",
    ]

    handoff = orchestrator.type3_handoff("project-1", "target-1")
    assert handoff["step"]["port"] == 80
    assert handoff["prompt"] == handoff["instructions"]
    assert "80/tcp http" in handoff["prompt"]
    assert "whatweb http://{target}:{port}" in handoff["prompt"]
    assert handoff["continue_with"] == {
        "tool": "audit_llm_continue",
        "project_id": "project-1",
        "target_id": "target-1",
    }
    assert 'audit_llm_continue(project_id="project-1", target_id="target-1")' in handoff["prompt"]
    assert "full control" not in handoff["prompt"].lower()


def test_duplicate_command_tells_the_model_to_continue():
    from audit_orchestrator.mcp_server import _duplicate_command_message, _normalize_command

    assert _normalize_command("curl  -k   https://10.19.220.6/login") == (
        "curl -k https://10.19.220.6/login"
    )
    message = _duplicate_command_message("project-1", "target-1", "curl -k https://10.19.220.6/login")
    assert "was not executed again" in message
    assert "The MCP kept control" in message
    assert 'audit_llm_continue(project_id="project-1", target_id="target-1")' in message


def test_waiting_for_llm_keeps_the_target_on_screen():
    from audit_orchestrator.core.live_screen import LiveScreen

    store = MagicMock(spec=AuditStore)
    store.get_project_statistics.return_value = {
        "targets_by_status": {"pending_llm_analysis": 1}
    }
    screen = LiveScreen(min_interval=0)
    screen.update(
        asset="10.19.220.6",
        service="22/tcp ssh",
        command="nmap -sV -p 22 10.19.220.6",
        status="done",
        force=True,
    )
    orchestrator = AuditOrchestrator(
        Settings(kali_server_url="http://127.0.0.1:5001"),
        store,
        live=screen,
    )
    status, _stats = orchestrator._close_run("project-1", 1, 0, 0, 0)
    text = screen.render()
    assert status == "pending_llm_analysis"
    assert "10.19.220.6" in text
    assert "0 hosts" not in text
    assert "nmap -sV -p 22 10.19.220.6" in text
