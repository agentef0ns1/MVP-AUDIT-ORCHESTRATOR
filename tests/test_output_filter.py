"""Fuzzer output should keep detections and drop progress."""
from pathlib import Path

from audit_orchestrator.core.output_filter import (
    clean_fuzzer_output,
    clean_param_discovery_output,
)


SAMPLE = """
 :: URL              : http://10.19.220.6:80/FUZZ
\x1b[2K:: Progress: [1/4614] :: Job [1/1] :: 0 req/sec :: Duration: [0:00:00] :: Errors: 0 ::
\x1b[2K404.html                [Status: 200, Size: 33, Words: 6, Lines: 1, Duration: 53ms]\x1b[0m
\x1b[2K:: Progress: [656/65088] :: Job [1/1] :: 374 req/sec :: Duration: [0:00:01] :: Errors: 0 ::
\x1b[2K.                       [Status: 301, Size: 172, Words: 5, Lines: 8, Duration: 53ms]\x1b[0m
\x1b[2K:: Progress: [2210/65088] :: Job [1/1] :: 375 req/sec :: Duration: [0:00:06] :: Errors: 0 ::
"""


def test_drops_progress_and_keeps_status_lines():
    cleaned = clean_fuzzer_output(SAMPLE)
    assert "Progress:" not in cleaned
    assert "404.html" in cleaned
    assert "[Status: 200" in cleaned
    assert "[Status: 301" in cleaned
    assert cleaned.count("\n") == 2


def test_param_discovery_keeps_only_the_final_result():
    raw = """
\x1b[92m    _
   /_| _ '
  (  |/ /(//) v2.2.7
      _/      \x1b[0m
\x1b[1;97m[*]\x1b[0m Scanning 0/1: http://10.19.220.6:80/
\x1b[1;97m[*]\x1b[0m Probing the target for stability
\x1b[1;93m[!]\x1b[0m Processing chunks: 1/103
\x1b[1;93m[!]\x1b[0m Processing chunks: 103/103
\x1b[1;93m[!]\x1b[0m No parameters were discovered.
"""
    cleaned = clean_param_discovery_output(raw)
    assert "Processing chunks" not in cleaned
    assert "Probing" not in cleaned
    assert cleaned.strip() == "[!] No parameters were discovered."


def test_api_fuzz_drops_hidden_404_rows():
    raw = (
        "000000001:   404        0 L      6 W        33 Ch        \"health\"\n"
        "000000004:   200        10 L     20 W       100 Ch       \"users\"\n"
    )
    cleaned = clean_fuzzer_output(raw)
    assert "404" not in cleaned
    assert "users" in cleaned


def test_real_audit_fuzz_files_lose_progress():
    paths = [
        Path("/home/f0ns1/RedTeam/OCSR25/infra/Audit/10.19.220.6/enumeration/param_fuzzing_20261005_103403.txt"),
        Path("/home/f0ns1/RedTeam/OCSR25/infra/Audit/10.19.220.6/enumeration/param_fuzzing_20261005_105701.txt"),
        Path("/home/f0ns1/RedTeam/OCSR25/infra/Audit/10.19.220.6/enumeration/backup_files_20261005_103745.txt"),
    ]
    for path in paths:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_fuzzer_output(raw)
        assert "Progress:" not in cleaned
        assert ":: Method" not in cleaned
        assert len(cleaned.splitlines()) < len(raw.splitlines())
