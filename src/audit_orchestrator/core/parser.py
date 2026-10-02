"""
Parser for nmap output and structured input files
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from audit_orchestrator.core.errors import ParserError


def parse_nmap_output(file_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """
    Parse nmap output file to extract targets and their open ports.
    
    Supports format:
        10.19.220.23
        Discovered open port 22/tcp on 10.19.220.23
        22/tcp   open  ssh
        2000/tcp open  cisco-sccp
    
    Returns:
        {
            "10.19.220.23": [
                {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
                {"port": 2000, "protocol": "tcp", "state": "open", "service": "cisco-sccp"}
            ]
        }
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise ParserError(f"File not found: {file_path}")
    
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise ParserError(f"Error reading file: {e}")
    
    # Check if it's JSON format
    if content.strip().startswith("{"):
        return parse_json_format(content)
    
    # Parse plain text nmap format
    return parse_plaintext_format(content)


def parse_plaintext_format(content: str) -> dict[str, list[dict[str, Any]]]:
    """
    Parse plain text nmap output format.
    
    Format patterns:
    - IP line: just the IP/hostname alone
    - Discovered line: "Discovered open port 22/tcp on 10.19.220.23"
    - Port detail line: "22/tcp   open  ssh"
    """
    targets: dict[str, list[dict[str, Any]]] = {}
    current_target: str | None = None
    
    # Regex patterns
    ip_pattern = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$')
    hostname_pattern = re.compile(r'^([a-zA-Z0-9][a-zA-Z0-9\-\.]+[a-zA-Z0-9])$')
    nmap_report_pattern = re.compile(
        r'Nmap scan report for ([\d\.]+|[a-zA-Z0-9][a-zA-Z0-9\-\.]+[a-zA-Z0-9])'
    )
    discovered_pattern = re.compile(
        r'Discovered open port (\d+)/(tcp|udp) on ([\d\.]+|[a-zA-Z0-9\-\.]+)'
    )
    port_detail_pattern = re.compile(
        r'^(\d+)/(tcp|udp)\s+(open|filtered|closed)\s+(.+?)(?:\s|$)'
    )
    
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if it's an IP address or hostname (target identifier)
        ip_match = ip_pattern.match(line)
        hostname_match = hostname_pattern.match(line) if not ip_match else None
        nmap_report_match = nmap_report_pattern.search(line)
        
        if ip_match:
            current_target = ip_match.group(1)
            if current_target not in targets:
                targets[current_target] = []
        elif hostname_match and len(line) < 100:  # Reasonable hostname length
            current_target = hostname_match.group(1)
            if current_target not in targets:
                targets[current_target] = []
        elif nmap_report_match:
            # Handle "Nmap scan report for X" format
            current_target = nmap_report_match.group(1)
            if current_target not in targets:
                targets[current_target] = []
        
        # Check for "Discovered open port" line
        discovered_match = discovered_pattern.search(line)
        if discovered_match:
            port = int(discovered_match.group(1))
            protocol = discovered_match.group(2)
            target = discovered_match.group(3)
            
            # Make sure we have this target
            if target not in targets:
                targets[target] = []
                current_target = target
        
        # Check for port detail line (more reliable for service info)
        port_detail_match = port_detail_pattern.match(line)
        if port_detail_match and current_target:
            port = int(port_detail_match.group(1))
            protocol = port_detail_match.group(2)
            state = port_detail_match.group(3)
            service = port_detail_match.group(4).strip()
            
            # Check if this port already exists
            existing = next(
                (p for p in targets[current_target] if p["port"] == port),
                None
            )
            
            if existing:
                # Update with more detailed info
                existing["state"] = state
                existing["service"] = service
            else:
                # Add new port
                targets[current_target].append({
                    "port": port,
                    "protocol": protocol,
                    "state": state,
                    "service": service
                })
    
    # Remove duplicates and sort ports
    for target in targets:
        seen = set()
        unique_ports = []
        for port_info in targets[target]:
            port_key = (port_info["port"], port_info["protocol"])
            if port_key not in seen:
                seen.add(port_key)
                unique_ports.append(port_info)
        
        targets[target] = sorted(unique_ports, key=lambda x: x["port"])
    
    return targets


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
