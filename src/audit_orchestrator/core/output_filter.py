"""Keep fuzzer enumeration files limited to detections."""
import re

FUZZ_TASK_TYPES = {
    "web_fuzzing",
    "param_fuzzing",
    "vhost_fuzzing",
    "backup_files",
    "api_fuzzing",
    "api_endpoints_enum",
    "param_discovery",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
_DETECTION_RE = re.compile(
    r"(\[Status:\s*\d+)"
    r"|(^https?://\S+)"
    r"|(^\d+:\s+\d{3}\b)"
    r"|(\(CODE:\s*\d+)",
    re.IGNORECASE,
)


def clean_fuzzer_output(output: str) -> str:
    """Drop banners and progress lines. Keep match lines only."""
    text = _ANSI_RE.sub("", output or "").replace("\r", "\n")
    kept: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "Progress:" in line:
            continue
        if re.search(r":\s+404\b", line):
            continue
        if not _DETECTION_RE.search(line):
            continue
        if line in seen:
            continue
        seen.add(line)
        kept.append(line)
    if not kept:
        return "No detections.\n"
    return "\n".join(kept) + "\n"


def clean_param_discovery_output(output: str) -> str:
    """Drop arjun chunk progress. Keep the final parameter result."""
    text = _ANSI_RE.sub("", output or "").replace("\r", "\n")
    kept: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "Processing chunks" in line:
            continue
        if line.startswith("[*]") or line.startswith("[!] Scanning") or line.startswith("(_|") or line.startswith("/_|"):
            continue
        if "parameter" not in line.lower() and not line.startswith("[+]"):
            continue
        if line in seen:
            continue
        seen.add(line)
        kept.append(line)
    if not kept:
        return "No parameters were discovered.\n"
    return "\n".join(kept) + "\n"


def prepare_enumeration_output(task_type: str, output: str) -> str:
    if task_type == "param_discovery":
        return clean_param_discovery_output(output)
    if task_type in FUZZ_TASK_TYPES:
        return clean_fuzzer_output(output)
    return output
