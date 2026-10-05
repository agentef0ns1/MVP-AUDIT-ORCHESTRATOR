"""Terminal launch stays out of the MCP stdout and opens one window."""
from pathlib import Path

from audit_orchestrator.core.live_terminal import (
    build_terminal_argv,
    lock_held,
    open_live_terminal,
    resolve_emulator,
)


def test_build_terminal_argv_matches_emulator(monkeypatch):
    viewer = ["python", "-m", "audit_orchestrator.live_console", "/tmp/ws"]
    assert build_terminal_argv("/usr/bin/gnome-terminal", viewer)[:2] == [
        "/usr/bin/gnome-terminal",
        "--",
    ]
    assert build_terminal_argv("/usr/bin/kitty", viewer)[0] == "/usr/bin/kitty"
    assert build_terminal_argv("/usr/bin/xterm", viewer)[1] == "-e"
    monkeypatch.setattr(
        "audit_orchestrator.core.live_terminal.os.path.realpath",
        lambda path: "/usr/bin/xfce4-terminal.wrapper",
    )
    argv = build_terminal_argv("/usr/bin/x-terminal-emulator", viewer)
    assert "--geometry=220x50" in argv
    assert argv[argv.index("-H") + 1] == "-x"
    assert argv[argv.index("-x") + 1:] == viewer


def test_resolve_emulator_prefers_env(monkeypatch):
    monkeypatch.setattr(
        "audit_orchestrator.core.live_terminal.shutil.which",
        lambda name: "/bin/custom" if name == "my-term" else None,
    )
    assert resolve_emulator({"AUDIT_LIVE_TERMINAL": "my-term"}) == "/bin/custom"
    assert resolve_emulator({}) is None


def test_open_skips_without_display(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(
        "audit_orchestrator.core.live_terminal.graphical_env",
        lambda: None,
    )
    assert open_live_terminal(tmp_path) is False
    assert not (tmp_path / ".audit-live.lock").exists()
    assert "DISPLAY" in (tmp_path / ".audit-live.error").read_text(encoding="utf-8")


def test_open_skips_when_lock_is_held(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(
        "audit_orchestrator.core.live_terminal.resolve_emulator",
        lambda env=None: "/usr/bin/xterm",
    )
    lock = tmp_path / ".audit-live.lock"
    lock.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(
        "audit_orchestrator.core.live_terminal.lock_held",
        lambda path, now=None: True,
    )
    assert open_live_terminal(tmp_path) is False


def test_lock_held_for_fresh_empty_file(tmp_path: Path):
    lock = tmp_path / ".audit-live.lock"
    lock.write_text("", encoding="utf-8")
    assert lock_held(lock) is True
    assert lock_held(lock, now=lock.stat().st_mtime + 30) is False
