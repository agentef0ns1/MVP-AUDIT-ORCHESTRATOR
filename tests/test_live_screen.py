"""Live screen keeps a stable frame and skips rapid repeats."""
import json
from pathlib import Path

from audit_orchestrator.core.live_screen import LiveScreen


def test_command_update_drops_stale_llm_prompt():
    screen = LiveScreen(min_interval=0)
    screen.update(
        asset="10.19.220.6",
        phase="LLM",
        llm="asking",
        ask="Which profile step is waiting?",
        answer="ssh 22",
        status="context",
        force=True,
    )
    screen.update(
        asset="10.19.220.6",
        phase="COMMAND",
        llm="idle",
        command="ffuf -u https://10.19.220.6:443/FUZZ",
        status="running",
        force=True,
    )
    text = screen.render()
    assert "Which profile step is waiting?" not in text
    assert "ssh 22" not in text
    assert "ffuf -u https://10.19.220.6:443/FUZZ" in text


def test_viewer_hides_stale_llm_placeholder():
    from rich.console import Console

    from audit_orchestrator.live_console import build_view

    console = Console(width=100, force_terminal=False)
    with console.capture() as captured:
        console.print(build_view({
            "clock": "00:01:00",
            "lanes": [{
                "asset": "10.19.220.6",
                "service": "443/tcp https",
                "status": "running",
                "command": "ffuf",
                "output": "-",
                "ask": "Which profile step is waiting?",
                "answer": "ssh 22",
            }],
        }))
    text = captured.get()
    assert "Which profile step is waiting?" not in text
    assert "ssh 22" not in text
    assert "ffuf" in text


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
    for label in ("TARGET", "PORT", "PHASE", "STATE", "MCP", "LLM", "COMMAND", "LAST", "PROGRESS"):
        assert label in text
    assert "10.19.220.23" in text
    assert "443/tcp https" in text
    assert text.startswith("╭")
    assert text.endswith("╯")
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


def test_parallel_assets_keep_separate_boxes():
    screen = LiveScreen(min_interval=0)
    screen.update(asset="192.168.1.1", command="nmap -sV -p 22 192.168.1.1", status="running", force=True)
    screen.update(
        asset="192.168.1.42",
        command="nmap --script vuln -p 80 192.168.1.42",
        ask="Why run this?",
        answer="80/tcp open http",
        output="PORT STATE SERVICE\n80/tcp open http",
        force=True,
    )
    text = screen.render()
    assert text.count("╭") == 1
    assert "PARALLEL" in text
    assert "192.168.1.1" in text
    assert "192.168.1.42" in text
    assert "nmap -sV -p 22 192.168.1.1" in text
    assert "LLM ASK" in text
    assert "Why run this?" in text
    assert "LLM ANSWER" in text
    assert "80/tcp open http" in text
    screen.update(asset="4 hosts", phase="DONE", solo=True, force=True)
    closed = screen.render()
    assert closed.count("╭") == 1
    assert "192.168.1.1" not in closed
    assert "4 hosts" in closed


def test_state_keeps_the_full_command(tmp_path: Path):
    from audit_orchestrator.live_console import window_for

    screen = LiveScreen(frame_path=tmp_path / "audit-live.txt", min_interval=0)
    command = (
        "ffuf -u https://10.19.220.23:8088/FUZZ -w "
        "/usr/share/seclists/Discovery/Web-Content/raft-small-files-lowercase.txt "
        "-mc 200,301,302,403 -e .bak,.old,.backup,.zip,.tar.gz -t 20"
    )
    screen.update(asset="10.19.220.23", command=command, output="line\n" * 6, force=True)
    state = json.loads((tmp_path / "audit-live.json").read_text(encoding="utf-8"))
    assert state["lanes"][0]["command"] == command
    cols, _rows = window_for(state)
    assert cols >= len(command)


def test_waiting_command_clears_previous_response():
    screen = LiveScreen(min_interval=0)
    screen.update(
        asset="10.19.220.6",
        service="80/tcp http",
        command="wafw00f http://10.19.220.6:80",
        status="done",
        output="[~] Number of requests: 7\n[-] No WAF detected by the generic detection",
        force=True,
    )
    screen.update(
        asset="10.19.220.6",
        service="80/tcp http",
        command="nuclei -u http://10.19.220.6:80 -silent",
        status="running",
        force=True,
    )
    text = screen.render()
    assert "nuclei -u http://10.19.220.6:80" in text
    assert "RESPONSE" not in text
    assert "No WAF detected" not in text
    assert "WAFW00F" not in text


def test_response_is_kept_complete():
    screen = LiveScreen(min_interval=0)
    full = "\n".join(f"line {i} of the command reply" for i in range(12))
    screen.update(asset="192.168.1.1", output=full, force=True)
    text = screen.render()
    assert "line 0 of the command reply" in text
    assert "line 11 of the command reply" in text


def test_publish_replaces_frame_file(tmp_path: Path):
    frame = tmp_path / "audit-live.txt"
    screen = LiveScreen(frame_path=frame, min_interval=0)
    screen.update(asset="192.168.1.42", service="22/tcp ssh", command="nmap -sV", force=True)
    screen.update(command="nc -v -n -w 5 192.168.1.42 22", force=True)
    text = frame.read_text(encoding="utf-8")
    assert "192.168.1.42" in text
    assert "nc -v -n -w 5 192.168.1.42 22" in text
    assert "nmap -sV" not in text
    assert not (tmp_path / "audit-live.txt.tmp").exists()
