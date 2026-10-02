"""
Tool installation and verification for security audit tools
"""
from __future__ import annotations

from typing import Optional

# Mapping: command name → package name (for apt/apt-get)
TOOL_PACKAGES = {
    # Network scanning
    "nmap": "nmap",
    "masscan": "masscan",
    
    # Web scanning
    "nikto": "nikto",
    "whatweb": "whatweb",
    "wafw00f": "wafw00f",
    "wpscan": "wpscan",
    "ffuf": "ffuf",
    "dirb": "dirb",
    "gobuster": "gobuster",
    "nuclei": "nuclei",
    
    # SSL/TLS
    "sslscan": "sslscan",
    "testssl.sh": "testssl.sh",
    "sslyze": "sslyze",
    
    # SSH
    "ssh-audit": "ssh-audit",
    
    # SMB/Windows
    "enum4linux": "enum4linux",
    "smbclient": "smbclient",
    "rpcclient": "samba-common-bin",
    
    # DNS
    "dig": "dnsutils",
    "nslookup": "dnsutils",
    "host": "bind9-host",
    
    # Database
    "mysql": "mysql-client",
    "psql": "postgresql-client",
    
    # General utilities
    "curl": "curl",
    "wget": "wget",
    "nc": "netcat-traditional",
    "telnet": "telnet",
    
    # Python tools that might need pip
    "impacket-smbclient": "python3-impacket",
    "impacket-psexec": "python3-impacket",
}

# Tools that are scripts or don't match standard package names
SPECIAL_CASES = {
    "testssl.sh": {
        "check": "which testssl.sh || which testssl",
        "install": "apt-get update && apt-get install -y testssl.sh || (cd /opt && git clone --depth 1 https://github.com/drwetter/testssl.sh.git && ln -sf /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh)"
    },
    "nuclei": {
        "check": "which nuclei",
        "install": "apt-get update && apt-get install -y nuclei || (cd /tmp && wget https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_linux_amd64.zip && unzip nuclei_linux_amd64.zip && mv nuclei /usr/local/bin/ && chmod +x /usr/local/bin/nuclei)"
    },
    "ffuf": {
        "check": "which ffuf",
        "install": "apt-get update && apt-get install -y ffuf || (cd /tmp && wget https://github.com/ffuf/ffuf/releases/latest/download/ffuf_linux_amd64.tar.gz && tar -xzf ffuf_linux_amd64.tar.gz && mv ffuf /usr/local/bin/ && chmod +x /usr/local/bin/ffuf)"
    }
}


def extract_tool_name(command: str) -> Optional[str]:
    """
    Extract tool name from command string.
    
    Examples:
        "nmap -sV -p 80 10.0.0.1" → "nmap"
        "nikto -h http://example.com" → "nikto"
        "curl -I http://example.com" → "curl"
        "testssl.sh --fast example.com" → "testssl.sh"
    
    Args:
        command: Full command string
    
    Returns:
        Tool name (first word) or None if empty
    """
    if not command or not command.strip():
        return None
    
    # Get first word (the tool/binary name)
    parts = command.strip().split()
    if not parts:
        return None
    
    tool = parts[0]
    
    # Handle full paths (e.g., "/usr/bin/nmap" → "nmap")
    if "/" in tool:
        tool = tool.split("/")[-1]
    
    return tool


def get_package_name(tool: str) -> str:
    """
    Get package name for a tool.
    
    Args:
        tool: Tool name (e.g., "nmap", "nikto")
    
    Returns:
        Package name for apt-get install (defaults to tool name)
    """
    return TOOL_PACKAGES.get(tool, tool)


def is_special_case(tool: str) -> bool:
    """Check if tool requires special installation handling"""
    return tool in SPECIAL_CASES


def get_check_command(tool: str) -> str:
    """
    Get command to check if tool is installed.
    
    Args:
        tool: Tool name
    
    Returns:
        Shell command to check installation (exit 0 if installed)
    """
    if tool in SPECIAL_CASES:
        return SPECIAL_CASES[tool]["check"]
    
    # Standard check using 'which'
    return f"which {tool}"


def get_install_command(tool: str) -> str:
    """
    Get command to install a tool.
    
    Args:
        tool: Tool name
    
    Returns:
        Shell command to install the tool
    """
    if tool in SPECIAL_CASES:
        return SPECIAL_CASES[tool]["install"]
    
    # Standard apt-get install
    package = get_package_name(tool)
    return f"apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y {package}"


def needs_installation(tool: str, check_output: str) -> bool:
    """
    Determine if tool needs installation based on check command output.
    
    Args:
        tool: Tool name
        check_output: Output from check command
    
    Returns:
        True if tool needs to be installed
    """
    # If check command succeeded (which found the tool), no install needed
    # We'll determine this based on exit_code in the caller
    return True  # Placeholder, actual logic in orchestrator
