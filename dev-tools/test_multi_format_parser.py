#!/usr/bin/env python3
"""Tests for multi-format nmap parsing."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.parser import parse_nmap_output


def _parse(content: str) -> dict:
    suffix = ".xml" if content.lstrip().startswith("<?xml") else ".txt"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as handle:
        handle.write(content)
        path = handle.name
    try:
        return parse_nmap_output(path)
    finally:
        Path(path).unlink()


def test_format_normal():
    content = """
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 10.19.220.23
Host is up (0.01s latency).
PORT     STATE SERVICE        VERSION
22/tcp   open  ssh            OpenSSH 7.4
80/tcp   open  http           nginx 1.18.0
8088/tcp open  ssl/radan-http myServer
"""
    targets = _parse(content)
    ports = {p["port"]: p for p in targets["10.19.220.23"]}
    assert ports[22]["service"] == "ssh"
    assert ports[22]["version"] == "OpenSSH 7.4"
    assert ports[80]["version"] == "nginx 1.18.0"
    assert ports[8088]["service"] == "ssl/radan-http"
    assert ports[8088]["version"] == "myServer"


def test_format_grepable():
    content = """# Nmap 7.94 scan initiated
Host: 10.19.220.23 ()	Status: Up
Host: 10.19.220.23 ()	Ports: 22/open/tcp//ssh//OpenSSH 7.4/, 80/open/tcp//http//nginx 1.18.0/, 443/open/tcp//ssl|http//nginx 1.18.0/	Ignored State: filtered (997)
# Nmap done at
"""
    targets = _parse(content)
    ports = {p["port"]: p for p in targets["10.19.220.23"]}
    assert ports[22]["service"] == "ssh"
    assert ports[22]["version"] == "OpenSSH 7.4"
    assert ports[80]["service"] == "http"
    assert ports[443]["service"] == "ssl/http"
    assert "ssl" in ports[443]["service"]


def test_format_xml():
    content = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="10.19.220.23" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="7.4"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="http" product="nginx" version="1.18.0" tunnel="ssl"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""
    targets = _parse(content)
    ports = {p["port"]: p for p in targets["10.19.220.23"]}
    assert ports[22]["version"] == "OpenSSH 7.4"
    assert ports[443]["service"] == "ssl/http"
    assert ports[443]["version"] == "nginx 1.18.0"


def test_format_legacy():
    content = """10.19.220.25
Discovered open port 443/tcp on 10.19.220.25
443/tcp open ssl/http nginx
"""
    targets = _parse(content)
    port = targets["10.19.220.25"][0]
    assert port["port"] == 443
    assert port["service"] == "ssl/http"
    assert port["version"] == "nginx"


def test_format_concatenated():
    content = """10.19.220.1
22/tcp open ssh
80/tcp open http

10.19.220.2
443/tcp open https
3306/tcp open mysql

10.19.220.3
8080/tcp open http-proxy
"""
    targets = _parse(content)
    assert set(targets) == {"10.19.220.1", "10.19.220.2", "10.19.220.3"}
    assert [p["port"] for p in targets["10.19.220.1"]] == [22, 80]
    assert [p["service"] for p in targets["10.19.220.2"]] == ["https", "mysql"]
    assert targets["10.19.220.3"][0]["service"] == "http-proxy"
    assert all(p["port"] != 8080 for p in targets["10.19.220.1"])


def test_verbose_discovered_open_port():
    """Incomplete -v output: ports only appear as 'Discovered open port'."""
    content = """
Nmap scan report for 192.168.1.0 [host down]
Nmap scan report for 192.168.1.2 [host down]
Discovered open port 3389/tcp on 192.168.1.39
Discovered open port 22/tcp on 192.168.1.39
Discovered open port 80/tcp on 192.168.1.1
Discovered open port 443/tcp on 192.168.1.1
Discovered open port 22/tcp on 192.168.1.1
Completed Connect Scan against 192.168.1.39 in 1.66s (2 hosts left)
"""
    targets = _parse(content)
    assert "192.168.1.0" not in targets
    assert sorted(p["port"] for p in targets["192.168.1.39"]) == [22, 3389]
    assert sorted(p["port"] for p in targets["192.168.1.1"]) == [22, 80, 443]
    assert all(p["state"] == "open" for ports in targets.values() for p in ports)


def test_auto_detection():
    grepable = "# Nmap 7.94 scan initiated\nHost: 10.0.0.1 () Ports: 22/open/tcp//ssh///\n"
    xml = '<?xml version="1.0"?><nmaprun><host><address addr="10.0.0.2" addrtype="ipv4"/><ports><port protocol="tcp" portid="80"><state state="open"/><service name="http"/></port></ports></host></nmaprun>'
    plain = "10.0.0.3\n22/tcp open ssh\n"
    assert "10.0.0.1" in _parse(grepable)
    assert "10.0.0.2" in _parse(xml)
    assert "10.0.0.3" in _parse(plain)


def main():
    tests = [
        test_format_normal,
        test_format_grepable,
        test_format_xml,
        test_format_legacy,
        test_format_concatenated,
        test_verbose_discovered_open_port,
        test_auto_detection,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")


if __name__ == "__main__":
    main()
