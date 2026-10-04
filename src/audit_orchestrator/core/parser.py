"""
Parser for nmap output and structured input files
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from audit_orchestrator.core.errors import ParserError


def parse_nmap_output(file_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """
    Parse nmap output file to extract targets and their open ports.

    Auto-detects:
    - XML output (-oX), including a single document
    - JSON structured format
    - Grepable output (-oG), including several scans concatenated
    - Normal / legacy plaintext (-oN, or a for-loop of `echo IP; nmap | grep open`)

    Returns a mapping of target -> list of port dicts. Each port has
    port, protocol, state, service, and optional version.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise ParserError(f"File not found: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise ParserError(f"Error reading file: {e}")

    stripped = content.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<nmaprun"):
        return parse_xml_format(content)
    if stripped.startswith("{"):
        return parse_json_format(content)
    if _looks_like_grepable(content):
        return parse_grepable_format(content)
    return parse_plaintext_format(content)


def _looks_like_grepable(content: str) -> bool:
    """True when the file is nmap -oG output, possibly several scans concatenated."""
    has_host_ports = any(
        line.startswith("Host:") and "Ports:" in line
        for line in content.splitlines()
    )
    return has_host_ports and ("# Nmap" in content or "Status:" in content)


def parse_grepable_format(content: str) -> dict[str, list[dict[str, Any]]]:
    """
    Parse nmap grepable output (-oG).

    Each host is one line:
        Host: 10.19.220.23 () Ports: 22/open/tcp//ssh//OpenSSH 7.4/, 80/open/tcp//http//nginx 1.18.0/

    Several scans concatenated in one file are merged by target.
    Field layout: port/state/proto/owner/service/rpcinfo/version/
    """
    targets: dict[str, list[dict[str, Any]]] = {}

    for line in content.split("\n"):
        if not line.startswith("Host:") or "Ports:" not in line:
            continue

        match = re.match(r"Host:\s+([\d.]+|[\w.\-]+)\s+\([^)]*\)", line)
        if not match:
            continue
        target = match.group(1)

        ports_match = re.search(r"Ports:\s+(.+?)(?:\s+Ignored State:|\s+Seq Index:|\s+IP ID Seq:|$)", line)
        if not ports_match:
            continue

        ports: list[dict[str, Any]] = []
        for entry in ports_match.group(1).split(", "):
            entry = entry.strip().rstrip(",")
            if not entry:
                continue
            parts = entry.split("/")
            if len(parts) < 3 or not parts[0].isdigit():
                continue

            service = parts[4] if len(parts) > 4 and parts[4] else "unknown"
            service = service.replace("|", "/")

            port_info: dict[str, Any] = {
                "port": int(parts[0]),
                "state": parts[1] or "open",
                "protocol": parts[2] or "tcp",
                "service": service,
            }

            version = ""
            if len(parts) > 6 and parts[6]:
                version = parts[6]
            elif len(parts) > 5 and parts[5]:
                version = parts[5]
            if version:
                port_info["version"] = version

            ports.append(port_info)

        if not ports:
            continue
        if target in targets:
            targets[target].extend(ports)
        else:
            targets[target] = ports

    return _dedupe_and_sort(targets)


def parse_xml_format(content: str) -> dict[str, list[dict[str, Any]]]:
    """
    Parse nmap XML output (-oX).

    Extracts address or hostname, port, protocol, state, service name,
    optional product/version, and ssl/tls tunnel prefix.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ParserError(f"Invalid XML format: {e}")

    targets: dict[str, list[dict[str, Any]]] = {}

    for host in root.findall(".//host"):
        addr_elem = host.find('.//address[@addrtype="ipv4"]')
        if addr_elem is None:
            addr_elem = host.find(".//address")
        if addr_elem is None:
            continue
        target = addr_elem.get("addr")
        if not target:
            continue

        hostname_elem = host.find(".//hostname")
        if hostname_elem is not None and hostname_elem.get("name"):
            target = hostname_elem.get("name") or target

        ports: list[dict[str, Any]] = []
        for port_elem in host.findall(".//port"):
            portid = port_elem.get("portid")
            if not portid or not portid.isdigit():
                continue

            state_elem = port_elem.find("state")
            state = state_elem.get("state") if state_elem is not None else "unknown"

            service_elem = port_elem.find("service")
            service = "unknown"
            version = None
            if service_elem is not None:
                service = service_elem.get("name", "unknown") or "unknown"
                version_parts = []
                if service_elem.get("product"):
                    version_parts.append(service_elem.get("product"))
                if service_elem.get("version"):
                    version_parts.append(service_elem.get("version"))
                if service_elem.get("extrainfo"):
                    version_parts.append(service_elem.get("extrainfo"))
                if version_parts:
                    version = " ".join(part for part in version_parts if part)
                tunnel = service_elem.get("tunnel")
                if tunnel in ("ssl", "tls"):
                    service = f"{tunnel}/{service}"

            port_info: dict[str, Any] = {
                "port": int(portid),
                "protocol": port_elem.get("protocol", "tcp") or "tcp",
                "state": state or "unknown",
                "service": service,
            }
            if version:
                port_info["version"] = version
            ports.append(port_info)

        if ports:
            targets[target] = ports

    return _dedupe_and_sort(targets)


def _dedupe_and_sort(targets: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Drop duplicate port/protocol pairs and sort by port number."""
    for target in list(targets):
        seen: set[tuple[int, str]] = set()
        unique_ports = []
        for port_info in targets[target]:
            port_key = (port_info["port"], port_info["protocol"])
            if port_key in seen:
                continue
            seen.add(port_key)
            unique_ports.append(port_info)
        targets[target] = sorted(unique_ports, key=lambda x: x["port"])
    return targets


def parse_plaintext_format(content: str) -> dict[str, list[dict[str, Any]]]:
    """
    Parse plain text nmap output, including several scans concatenated.

    Handles:
    - A bare IP or hostname line (for-loop: `echo $i; nmap ... | grep open`)
    - "Nmap scan report for <target>"
    - "Discovered open port 22/tcp on <target>" (verbose -v, even if the scan is unfinished)
    - "22/tcp open ssh" and "22/tcp open ssh OpenSSH 7.4"
    """
    targets: dict[str, list[dict[str, Any]]] = {}
    current_target: str | None = None

    ip_pattern = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$")
    hostname_pattern = re.compile(r"^([a-zA-Z0-9][a-zA-Z0-9\-\.]+[a-zA-Z0-9])$")
    nmap_report_pattern = re.compile(
        r"Nmap scan report for (?:[^\s(]+\s+\()?([\d.]+|[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9])\)?"
    )
    discovered_pattern = re.compile(
        r"Discovered open port (\d+)/(tcp|udp) on ([\d.]+|[a-zA-Z0-9\-\.]+)"
    )
    # Service token, then optional version text.
    port_detail_pattern = re.compile(
        r"^(\d+)/(tcp|udp)\s+(open|filtered|closed)\s+(\S+)(?:\s+(.+))?$"
    )

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        ip_match = ip_pattern.match(line)
        hostname_match = hostname_pattern.match(line) if not ip_match else None
        nmap_report_match = nmap_report_pattern.search(line)

        if ip_match:
            current_target = ip_match.group(1)
            targets.setdefault(current_target, [])
            continue
        if hostname_match and len(line) < 100 and "/" not in line:
            current_target = hostname_match.group(1)
            targets.setdefault(current_target, [])
            continue
        if nmap_report_match and "[host down]" not in line.lower():
            current_target = nmap_report_match.group(1)
            targets.setdefault(current_target, [])

        discovered_match = discovered_pattern.search(line)
        if discovered_match:
            port = int(discovered_match.group(1))
            protocol = discovered_match.group(2)
            target = discovered_match.group(3)
            targets.setdefault(target, [])
            current_target = target
            already = next(
                (p for p in targets[target] if p["port"] == port and p["protocol"] == protocol),
                None,
            )
            if already is None:
                targets[target].append({
                    "port": port,
                    "protocol": protocol,
                    "state": "open",
                    "service": "unknown",
                })
            continue

        port_detail_match = port_detail_pattern.match(line)
        if port_detail_match and current_target:
            port = int(port_detail_match.group(1))
            protocol = port_detail_match.group(2)
            state = port_detail_match.group(3)
            service = port_detail_match.group(4).strip()
            version = (port_detail_match.group(5) or "").strip()

            existing = next(
                (p for p in targets[current_target] if p["port"] == port and p["protocol"] == protocol),
                None,
            )
            port_data: dict[str, Any] = {
                "port": port,
                "protocol": protocol,
                "state": state,
                "service": service,
            }
            if version and version != service:
                port_data["version"] = version

            if existing:
                existing.update(port_data)
            else:
                targets[current_target].append(port_data)

    return _dedupe_and_sort(targets)


def parse_json_format(content: str) -> dict[str, list[dict[str, Any]]]:
    """
    Parse structured JSON format.
    
    Expected format:
    {
      "targets": [
        {
          "ip": "10.19.220.23",
          "hostname": "server1.local",
          "ports": [
            {"port": 22, "protocol": "tcp", "service": "ssh", "version": "OpenSSH 7.4"}
          ]
        }
      ]
    }
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ParserError(f"Invalid JSON format: {e}")
    
    if "targets" not in data:
        raise ParserError("JSON format must have 'targets' key")
    
    targets: dict[str, list[dict[str, Any]]] = {}
    
    for target_data in data["targets"]:
        # Determine the target identifier (prefer hostname, fallback to IP)
        target_id = target_data.get("hostname") or target_data.get("ip")
        if not target_id:
            continue
        
        ports = []
        for port_data in target_data.get("ports", []):
            port_info = {
                "port": port_data["port"],
                "protocol": port_data.get("protocol", "tcp"),
                "state": port_data.get("state", "open"),
                "service": port_data.get("service", "unknown")
            }
            
            # Optional fields
            if "version" in port_data:
                port_info["version"] = port_data["version"]
            
            ports.append(port_info)
        
        targets[target_id] = sorted(ports, key=lambda x: x["port"])
    
    return targets


def validate_targets(targets: dict[str, list[dict[str, Any]]]) -> bool:
    """
    Validate parsed targets data structure.
    
    Raises ParserError if validation fails.
    Removes targets with no ports (valid in real scans - host up but no open ports).
    """
    if not targets:
        raise ParserError("No targets found in input file")
    
    # Filter out targets with no ports and validate the rest
    targets_to_remove = []
    
    for target, ports in targets.items():
        if not ports:
            # Target has no open ports - valid scenario, remove from list
            targets_to_remove.append(target)
            continue
        
        for port_info in ports:
            if "port" not in port_info:
                raise ParserError(f"Port info missing 'port' field for target {target}")
            
            if not isinstance(port_info["port"], int):
                raise ParserError(f"Port must be integer, got {type(port_info['port'])}")
            
            if port_info["port"] < 1 or port_info["port"] > 65535:
                raise ParserError(f"Invalid port number: {port_info['port']}")
            
            if "protocol" not in port_info:
                port_info["protocol"] = "tcp"  # Default
            
            if "state" not in port_info:
                port_info["state"] = "open"  # Default
    
    # Remove targets with no ports
    for target in targets_to_remove:
        del targets[target]
    
    # Check if we have any valid targets left
    if not targets:
        raise ParserError("No targets with open ports found in input file")
    
    return True


def get_target_count(targets: dict[str, list[dict[str, Any]]]) -> int:
    """Get total number of targets"""
    return len(targets)


def get_total_port_count(targets: dict[str, list[dict[str, Any]]]) -> int:
    """Get total number of ports across all targets"""
    return sum(len(ports) for ports in targets.values())


def get_service_types(targets: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Get unique service types across all targets"""
    services = set()
    for ports in targets.values():
        for port_info in ports:
            service = port_info.get("service", "unknown")
            services.add(service)
    return services


def format_targets_summary(targets: dict[str, list[dict[str, Any]]]) -> str:
    """
    Generate a human-readable summary of parsed targets.
    """
    lines = [
        f"Targets found: {get_target_count(targets)}",
        f"Total ports: {get_total_port_count(targets)}",
        ""
    ]
    
    for target, ports in sorted(targets.items()):
        lines.append(f"{target}: {len(ports)} port(s)")
        for port_info in ports[:5]:  # Show first 5 ports
            lines.append(
                f"  - {port_info['port']}/{port_info['protocol']} "
                f"({port_info.get('service', 'unknown')})"
            )
        if len(ports) > 5:
            lines.append(f"  ... and {len(ports) - 5} more")
    
    return "\n".join(lines)
