"""Write the live frame and open one terminal viewer per workspace.

Stdout of the MCP process stays JSON-RPC. The viewer is a separate
process started in a graphical terminal.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

FRAME_NAME = "audit-live.txt"
STATE_NAME = "audit-live.json"
LOCK_NAME = ".audit-live.lock"
_STARTING_GRACE_S = 5.0

_EMULATORS = (
    "x-terminal-emulator",
    "gnome-terminal",
    "kitty",
    "alacritty",
    "xterm",
)


def write_live_frame(path: Path, frame: str) -> None:
    """Replace the frame file atomically so a reader never sees a torn box."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(frame + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_live_state(path: Path, payload: dict[str, Any]) -> None:
    """Structured lanes so the viewer can reflow to the real terminal width."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def resolve_emulator(env: dict[str, str] | None = None) -> str | None:
    """First usable terminal emulator, or AUDIT_LIVE_TERMINAL when set."""
    values = os.environ if env is None else env
    custom = values.get("AUDIT_LIVE_TERMINAL", "").strip()
    if custom:
        found = shutil.which(custom)
        if found:
            return found
        if os.path.isabs(custom) and os.path.isfile(custom):
            return custom
        return None
    for name in _EMULATORS:
        found = shutil.which(name)
        if found:
            return found
    return None


def build_terminal_argv(emulator: str, viewer: list[str]) -> list[str]:
    """Command line that runs the viewer inside the chosen emulator."""
    name = Path(emulator).name
    real = Path(os.path.realpath(emulator)).name
    if name in {"gnome-terminal", "kgx"}:
        return [emulator, "--", *viewer]
    if name == "kitty":
        return [emulator, *viewer]
    if name == "wezterm":
        return [emulator, "start", "--", *viewer]
    if name.startswith("xfce4-terminal") or real.startswith("xfce4-terminal"):
        binary = shutil.which("xfce4-terminal") or emulator
        return [binary, "--geometry=220x50", "-H", "-x", *viewer]
    return [emulator, "-e", *viewer]


def graphical_env() -> dict[str, str] | None:
    """Display variables for a new terminal.

    The MCP process often starts without DISPLAY. Reuse the session of
    another process of the same user when that happens.
    """
    keys = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")
    current = {key: os.environ[key] for key in keys if os.environ.get(key)}
    if current.get("DISPLAY") or current.get("WAYLAND_DISPLAY"):
        return current
    uid = os.getuid()
    found: dict[str, str] = {}
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            raw = (entry / "environ").read_bytes()
        except OSError:
            continue
        vals: dict[str, str] = {}
        for item in raw.split(b"\0"):
            if b"=" not in item:
                continue
            key, value = item.split(b"=", 1)
            if key in {b"DISPLAY", b"WAYLAND_DISPLAY", b"XAUTHORITY", b"DBUS_SESSION_BUS_ADDRESS"}:
                vals[key.decode()] = value.decode(errors="replace")
        if not vals.get("DISPLAY") and not vals.get("WAYLAND_DISPLAY"):
            continue
        found = vals
        if vals.get("DBUS_SESSION_BUS_ADDRESS"):
            return vals
    return found or None


def viewer_command(base_path: Path) -> list[str]:
    return [sys.executable, "-m", "audit_orchestrator.live_console", str(base_path)]


def lock_held(lock: Path, now: float | None = None) -> bool:
    """True when a viewer owns the lock or one just started and has not written its pid."""
    try:
        text = lock.read_text(encoding="utf-8").strip()
        age = (time.time() if now is None else now) - lock.stat().st_mtime
    except OSError:
        return False
    if not text:
        return age < _STARTING_GRACE_S
    try:
        pid = int(text)
    except ValueError:
        return False
    if pid <= 0:
        return age < _STARTING_GRACE_S
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def open_live_terminal(base_path: str | Path) -> bool:
    """Open one live window for this workspace. Failures never stop the audit."""
    try:
        return _open_live_terminal(Path(base_path))
    except Exception:
        return False


def _note(base: Path, message: str) -> None:
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / ".audit-live.error").write_text(message + "\n", encoding="utf-8")
    except OSError:
        return


def _open_live_terminal(base: Path) -> bool:
    if os.environ.get("AUDIT_LIVE_DISABLE") == "1":
        _note(base, "AUDIT_LIVE_DISABLE=1")
        return False
    gui = graphical_env()
    if gui is None:
        _note(base, "no graphical session (DISPLAY/WAYLAND_DISPLAY)")
        return False
    emulator = resolve_emulator()
    if emulator is None:
        _note(base, "no terminal emulator found")
        return False
    base.mkdir(parents=True, exist_ok=True)
    lock = base / LOCK_NAME
    if lock.exists() and lock_held(lock):
        return False
    try:
        lock.unlink(missing_ok=True)
    except OSError:
        return False
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    os.close(fd)
    argv = build_terminal_argv(emulator, viewer_command(base.resolve()))
    env = os.environ.copy()
    env.update(gui)
    try:
        subprocess.Popen(
            argv,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except Exception as exc:
        lock.unlink(missing_ok=True)
        _note(base, f"failed to open terminal: {exc}")
        return False
    try:
        (base / ".audit-live.error").unlink(missing_ok=True)
    except OSError:
        pass
    return True
