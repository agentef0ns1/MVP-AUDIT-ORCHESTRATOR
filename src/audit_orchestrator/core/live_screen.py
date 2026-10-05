"""Single-frame audit status screen published to an optional sink.

The orchestrator updates fields at milestones and republishes the whole
frame. A frame file, when set, is replaced on every publish so a separate
terminal can redraw it. With neither sink nor file, publish is a no-op.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from audit_orchestrator.core.live_terminal import STATE_NAME, write_live_frame, write_live_state


_LANE_FIELDS = (
    "asset",
    "service",
    "phase",
    "mcp",
    "llm",
    "command",
    "status",
    "last",
    "progress",
    "output",
    "ask",
    "answer",
)


def _blank_lane() -> dict[str, str]:
    return {
        "asset": "-",
        "service": "-",
        "phase": "PROCESS",
        "mcp": "-",
        "llm": "idle",
        "command": "-",
        "status": "idle",
        "last": "-",
        "progress": "-",
        "output": "-",
        "ask": "-",
        "answer": "-",
    }


def excerpt(text: str, lines: int | None = None) -> str:
    """Clean a command or model reply. The live view keeps the full text."""
    raw = (text or "").replace("\r", "").strip()
    if not raw:
        return "-"
    if lines is None:
        return raw
    kept: list[str] = []
    for line in raw.splitlines():
        kept.append(line)
        if len(kept) >= lines:
            break
    return "\n".join(kept)


class LiveScreen:
    """All parallel assets in one frame. Each publish replaces the screen."""

    WIDTH = 120

    def __init__(
        self,
        sink: Callable[[str], None] | None = None,
        min_interval: float = 0.4,
        frame_path: Path | None = None,
    ):
        self.sink = sink
        self.min_interval = min_interval
        self.frame_path = frame_path
        self.lanes: dict[str, dict[str, str]] = {}
        self.order: list[str] = []
        self._active = "-"
        self._mirror(_blank_lane())
        self._started = time.monotonic()
        self._last_sent = 0.0
        self._last_phase = ""
        self._last_asset = ""

    def _mirror(self, lane: dict[str, str]) -> None:
        for key in _LANE_FIELDS:
            setattr(self, key, lane.get(key, "-"))

    def update(self, *, force: bool = False, solo: bool = False, **fields: Any) -> None:
        """Update one asset box. solo replaces every box with this one."""
        if solo:
            self.lanes.clear()
            self.order.clear()
            self._active = "-"
        key = fields.get("asset")
        if key is None:
            key = self._active
        key = "-" if key is None else str(key)
        if key != "-" and self.order == ["-"]:
            self.lanes.pop("-", None)
            self.order.clear()
        if key not in self.lanes:
            self.lanes[key] = _blank_lane()
            self.order.append(key)
        lane = self.lanes[key]
        incoming = dict(fields)
        new_command = incoming.get("command")
        command_changed = (
            new_command is not None
            and str(new_command) != lane.get("command", "-")
        )
        waiting = incoming.get("status") == "running" or command_changed
        if waiting and "output" not in incoming:
            incoming["output"] = "-"
        # A profile command is not an LLM turn. Drop the previous question
        # unless this update explicitly replaces it.
        if incoming.get("phase") == "COMMAND" or incoming.get("llm") == "idle":
            incoming.setdefault("ask", "-")
            incoming.setdefault("answer", "-")
        elif incoming.get("ask") in {"-", "Which profile step is waiting?"}:
            incoming["ask"] = "-"
            incoming.setdefault("answer", "-")
        if incoming.get("answer") == "ssh 22":
            incoming["answer"] = "-"
        for name, value in incoming.items():
            if name not in _LANE_FIELDS:
                continue
            lane[name] = "-" if value is None else str(value)
        lane["asset"] = key
        self._active = key
        self._mirror(lane)
        self.publish(force=force)

    def publish(self, force: bool = False) -> None:
        phase_or_asset = self.phase != self._last_phase or self.asset != self._last_asset
        now = time.monotonic()
        if not force and not phase_or_asset and (now - self._last_sent) < self.min_interval:
            return
        self._last_phase = self.phase
        self._last_asset = self.asset
        self._last_sent = now
        frame = self.render()
        if self.frame_path is not None:
            try:
                write_live_frame(self.frame_path, frame)
                write_live_state(self.frame_path.with_name(STATE_NAME), self.snapshot())
            except Exception:
                pass
        if self.sink is None:
            return
        try:
            self.sink(frame)
        except Exception:
            return

    def snapshot(self) -> dict[str, Any]:
        """Full text for each asset. The viewer wraps it to the window width."""
        elapsed = int(time.monotonic() - self._started)
        clock = f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"
        lanes = [dict(self.lanes[key]) for key in self.order] or [_blank_lane()]
        return {"clock": clock, "lanes": lanes}

    def render(self) -> str:
        elapsed = int(time.monotonic() - self._started)
        clock = f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"
        lanes = [self.lanes[key] for key in self.order] or [_blank_lane()]
        inner = self.WIDTH - 2

        def row(text: str) -> str:
            return "│" + text[:inner].ljust(inner) + "│"

        def field(label: str, value: str) -> str:
            return row(f" {label:<8}  {value}")

        def section(title: str) -> str:
            left = f"─ {title} "
            return "├" + left + ("─" * max(inner - len(left), 1)) + "┤"

        def wrapped(text: str) -> list[str]:
            width = inner - 2
            lines: list[str] = []
            for raw in text.splitlines() or [""]:
                chunk = raw
                if chunk == "":
                    lines.append(row(" "))
                    continue
                while len(chunk) > width:
                    lines.append(row(f" {chunk[:width]}"))
                    chunk = chunk[width:]
                lines.append(row(f" {chunk}"))
            return lines

        def block(title: str, text: str) -> list[str]:
            if not text or text == "-":
                return []
            return [section(title), *wrapped(text)]

        left = "─ AUDIT LIVE "
        right = f" {clock} ─"
        top = "╭" + left + ("─" * max(inner - len(left) - len(right), 1)) + right + "╮"
        bottom = "╰" + ("─" * inner) + "╯"
        running = sum(1 for lane in lanes if lane["status"] not in {"completed", "failed", "idle"})
        body = [
            top,
            field("PARALLEL", f"{len(lanes)} assets   {running} active"),
            section("ASSETS"),
        ]
        for lane in lanes:
            body.append(row(
                f" {lane['asset']:<18} {lane['service']:<22} {lane['status']:<12} {lane['command']}"
            ))
        for lane in lanes:
            body.append(section(lane["asset"]))
            body.append(field("TARGET", lane["asset"]))
            body.append(field("PORT", lane["service"]))
            body.append(field("PHASE", lane["phase"]))
            body.append(field("STATE", lane["status"]))
            body.append(field("MCP", lane["mcp"]))
            body.append(field("LLM", lane["llm"]))
            body.extend(block("COMMAND", lane["command"]))
            body.extend(block("RESPONSE", lane["output"]))
            body.extend(block("LLM ASK", lane["ask"]))
            body.extend(block("LLM ANSWER", lane["answer"]))
            body.append(field("LAST", lane["last"]))
        progress = next((lane["progress"] for lane in reversed(lanes) if lane["progress"] != "-"), "-")
        body.append(field("PROGRESS", progress))
        body.append(bottom)
        return "\n".join(body)

    def message(self) -> str:
        """Fenced frame so a markdown viewer keeps the column padding."""
        return "```text\n" + self.render() + "\n```"
