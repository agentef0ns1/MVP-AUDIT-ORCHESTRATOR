"""Live screen keeps a stable frame and skips rapid repeats."""
from audit_orchestrator.core.live_screen import LiveScreen


def test_render_contains_fixed_rows():
    screen = LiveScreen()
    screen.update(
        asset="10.19.220.23",
        service="443/tcp https",
        phase="COMMAND",
        mcp="kali POST /api/command",
        llm="idle",
        command="nmap -sV -p 443 10.19.220.23",
        status="running",
        last="SSL detect 443 -> https",
        progress="targets 2/40",
    )
    text = screen.render()
    for label in ("ASSET", "SERVICE", "PHASE", "MCP", "LLM", "COMMAND", "STATUS", "LAST", "PROGRESS"):
        assert label in text
    assert "10.19.220.23" in text
    assert text.startswith("+")
    assert text.endswith("+")
    assert screen.message().startswith("```text\n")
    assert "AUDIT LIVE" in screen.message()


def test_sink_receives_full_frame_on_phase_change():
    seen = []
    screen = LiveScreen(sink=seen.append, min_interval=10)
    screen.update(phase="PROCESS", asset="10.0.0.1", status="auditing")
    screen.update(status="still")  # same phase and asset, inside the interval
    screen.update(phase="COMMAND", command="nmap")
    assert len(seen) == 2
    assert "COMMAND" in seen[1]
    assert "nmap" in seen[1]
