"""Redraw the audit in place, wrapping to the current terminal width."""
from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Any

from audit_orchestrator.core.live_terminal import FRAME_NAME, LOCK_NAME, STATE_NAME


def _read_state(base_path: Path) -> dict[str, Any] | None:
    path = base_path / STATE_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _read_frame(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "waiting for audit...\n"


def window_for(state: dict[str, Any]) -> tuple[int, int]:
    """Columns and rows that fit the full command lines and the replies."""
    lanes = state.get("lanes") or []
    longest = 80
    reply_lines = 0
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        for key in ("command", "ask", "answer", "output", "last"):
            text = str(lane.get(key) or "")
            if text == "-":
                continue
            for line in text.splitlines() or [""]:
                longest = max(longest, len(line))
                reply_lines += 1
    cols = min(max(longest + 4, 100), 240)
    rows = min(max(8 + len(lanes) * 2 + reply_lines, 24), 80)
    return cols, rows


def visible_text(kind: str, value: object) -> str:
    """Drop empty fields and the stale Type 3 placeholder the old server still publishes."""
    text = str(value or "").strip()
    if not text or text == "-":
        return ""
    if kind == "ask" and text == "Which profile step is waiting?":
        return ""
    if kind == "answer" and text == "ssh 22":
        return ""
    return str(value).replace("\r", "")


def build_view(state: dict[str, Any]):
    """One panel. Commands and replies wrap to the console width, nothing is cut."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    lanes = [lane for lane in (state.get("lanes") or []) if isinstance(lane, dict)]
    clock = str(state.get("clock") or "")
    active = sum(1 for lane in lanes if lane.get("status") not in {"completed", "failed", "idle", "-"})
    table = Table(expand=True, show_lines=False, pad_edge=False)
    table.add_column("TARGET", overflow="fold", no_wrap=False, ratio=2)
    table.add_column("PORT", overflow="fold", no_wrap=False, ratio=2)
    table.add_column("STATE", overflow="fold", no_wrap=False, ratio=2)
    table.add_column("COMMAND", overflow="fold", no_wrap=False, ratio=4)
    for lane in lanes:
        table.add_row(
            str(lane.get("asset") or "-"),
            str(lane.get("service") or "-"),
            str(lane.get("status") or "-"),
            str(lane.get("command") or "-"),
        )
    blocks: list[Any] = [table]
    for lane in lanes:
        parts: list[Any] = []
        for title, key in (
            ("COMMAND", "command"),
            ("RESPONSE", "output"),
            ("LLM ASK", "ask"),
            ("LLM ANSWER", "answer"),
        ):
            text = visible_text(key, lane.get(key))
            if not text:
                continue
            parts.append(Text(f"{title}\n{text}", overflow="fold"))
        if not parts:
            continue
        blocks.append(Panel(Group(*parts), title=str(lane.get("asset") or "-"), expand=True))
    return Panel(
        Group(*blocks),
        title=f"AUDIT LIVE {clock}   {len(lanes)} assets   {active} active",
        expand=True,
        padding=(0, 1),
    )


def run(base_path: Path) -> None:
    from rich.live import Live
    from rich.text import Text

    frame_path = base_path / FRAME_NAME
    lock = base_path / LOCK_NAME
    lock.write_text(str(os.getpid()), encoding="utf-8")
    redraw = False

    def on_resize(_signum: int, _frame: object) -> None:
        nonlocal redraw
        redraw = True

    previous = signal.getsignal(signal.SIGWINCH)
    signal.signal(signal.SIGWINCH, on_resize)
    try:
        state = _read_state(base_path)
        current_key = ""
        view = build_view(state) if state else Text(_read_frame(frame_path))
        with Live(view, refresh_per_second=4, screen=True, vertical_overflow="ellipsis") as live:
            while True:
                state = _read_state(base_path)
                size = shutil.get_terminal_size(fallback=(120, 40))
                key = ""
                if state is not None:
                    key = json.dumps(state, ensure_ascii=False) + f"|{size.columns}x{size.lines}"
                else:
                    key = _read_frame(frame_path) + f"|{size.columns}x{size.lines}"
                if key != current_key or redraw:
                    live.console.width = size.columns
                    if state is not None:
                        live.update(build_view(state), refresh=True)
                    else:
                        live.update(Text(_read_frame(frame_path)), refresh=True)
                    current_key = key
                    redraw = False
                time.sleep(0.25)
    finally:
        signal.signal(signal.SIGWINCH, previous)
        try:
            if lock.exists() and lock.read_text(encoding="utf-8").strip() == str(os.getpid()):
                lock.unlink()
        except OSError:
            pass


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: audit-orchestrator-live BASE_PATH", file=sys.stderr)
        raise SystemExit(2)
    base = Path(sys.argv[1]).expanduser().resolve()
    if not base.is_dir():
        print(f"not a directory: {base}", file=sys.stderr)
        raise SystemExit(2)
    try:
        run(base)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
