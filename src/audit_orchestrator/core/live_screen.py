"""Single-frame audit status screen published to an optional sink.

The orchestrator updates fields at milestones and republishes the whole
frame. With no sink, publish is a no-op so audits behave as before.
"""
from __future__ import annotations

import time
from typing import Any, Callable


class LiveScreen:
    """Fixed-row ASCII status. Each publish sends the full frame."""

    WIDTH = 50

    def __init__(
        self,
        sink: Callable[[str], None] | None = None,
        min_interval: float = 0.4,
    ):
        self.sink = sink
        self.min_interval = min_interval
        self.asset = "-"
        self.service = "-"
        self.phase = "PROCESS"
        self.mcp = "-"
        self.llm = "idle"
        self.command = "-"
        self.status = "idle"
        self.last = "-"
        self.progress = "-"
        self._started = time.monotonic()
        self._last_sent = 0.0
        self._last_phase = ""
        self._last_asset = ""

    def update(self, *, force: bool = False, **fields: Any) -> None:
        for key, value in fields.items():
            if not hasattr(self, key) or key.startswith("_") or key in ("sink", "min_interval"):
                continue
            setattr(self, key, "-" if value is None else str(value))
        self.publish(force=force)

    def publish(self, force: bool = False) -> None:
        phase_or_asset = self.phase != self._last_phase or self.asset != self._last_asset
        now = time.monotonic()
        if not force and not phase_or_asset and (now - self._last_sent) < self.min_interval:
            return
        self._last_phase = self.phase
        self._last_asset = self.asset
        self._last_sent = now
        if self.sink is None:
            return
        try:
            self.sink(self.render())
        except Exception:
            return

    def render(self) -> str:
        elapsed = int(time.monotonic() - self._started)
        clock = f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"
        inner = self.WIDTH - 2

        def line(text: str = "") -> str:
            clipped = text[:inner]
            return "|" + clipped.ljust(inner) + "|"

        def row(label: str, value: str) -> str:
            body = f" {label:<8}  {value}"
            return line(body)

        title = f" AUDIT LIVE"
        title_line = "|" + title + clock.rjust(inner - len(title)) + "|"
        bar = "+" + ("-" * inner) + "+"
        return "\n".join([
            bar,
            title_line,
            bar,
            row("ASSET", self.asset),
            row("SERVICE", self.service),
            row("PHASE", self.phase),
            row("MCP", self.mcp),
            row("LLM", self.llm),
            bar,
            row("COMMAND", self.command),
            row("STATUS", self.status),
            bar,
            row("LAST", self.last),
            row("PROGRESS", self.progress),
            bar,
        ])

    def message(self) -> str:
        """Fenced frame so a markdown viewer keeps the column padding."""
        return "```text\n" + self.render() + "\n```"
