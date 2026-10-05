"""
Command normalization to prevent tool aliasing issues

This module ensures that security tool commands use absolute paths
to prevent any potential aliasing or PATH manipulation issues.
"""
from typing import Optional


TOOL_ABSOLUTE_PATHS = {
    # Fuzzing tools
    "ffuf": "/usr/bin/ffuf",
    "wfuzz": "/usr/bin/wfuzz",
    "gobuster": "/usr/bin/gobuster",
    "dirb": "/usr/bin/dirb",
    "feroxbuster": "/usr/bin/feroxbuster",
    "nuclei": "/usr/bin/nuclei",
    "arjun": "/usr/bin/arjun",
    
    # Web scanners
    "nikto": "/usr/bin/nikto",
    "whatweb": "/usr/bin/whatweb",
    "wafw00f": "/usr/bin/wafw00f",
    "wpscan": "/usr/bin/wpscan",
    "droopescan": "/usr/bin/droopescan",
    "joomscan": "/usr/bin/joomscan",
    "cmseek": "/usr/bin/cmseek",
    
    # SSL/TLS tools
    "sslscan": "/usr/bin/sslscan",
    "testssl.sh": "/usr/bin/testssl.sh",
    "testssl": "/usr/bin/testssl.sh",
    
    # Network tools
    "nmap": "/usr/bin/nmap",
    "masscan": "/usr/bin/masscan",
    "nc": "/usr/bin/nc",
    "netcat": "/usr/bin/netcat",
    
    # SSH tools
    "ssh-audit": "/usr/bin/ssh-audit",
    "ssh-keyscan": "/usr/bin/ssh-keyscan",
    
    # SMB/Windows tools
    "enum4linux": "/usr/bin/enum4linux",
    "smbclient": "/usr/bin/smbclient",
    
    # Other security tools
    "graphw00f": "/usr/bin/graphw00f",
    "trufflehog": "/usr/bin/trufflehog",
    "retire": "/usr/bin/retire",
    "wappalyzer": "/usr/bin/wappalyzer",
    "linkfinder": "/usr/bin/linkfinder",
    "git-dumper": "/usr/bin/git-dumper",
    "gitdumper": "/usr/bin/git-dumper",
    
    # Common utilities
    "wget": "/usr/bin/wget",
    "curl": "/usr/bin/curl",
    "grep": "/usr/bin/grep",
}


def normalize_command(command: str) -> str:
    """
    Replace tool names with absolute paths to prevent aliasing.
    
    This function extracts the first word of a command (the tool name)
    and replaces it with its absolute path if it's a known security tool.
    This prevents issues with shell aliases or PATH manipulation.
    
    Args:
        command: Original command string (e.g., "ffuf -u http://example.com")
    
    Returns:
        Command with absolute path (e.g., "/usr/bin/ffuf -u http://example.com")
    
    Examples:
        >>> normalize_command("ffuf -u http://example.com/FUZZ -w wordlist.txt")
        '/usr/bin/ffuf -u http://example.com/FUZZ -w wordlist.txt'
        
        >>> normalize_command("nmap -sV target")
        '/usr/bin/nmap -sV target'
        
        >>> normalize_command("echo hello")  # Unknown tool, unchanged
        'echo hello'
    """
    if not command or not command.strip():
        return command
    
    # Split command into tool and arguments
    parts = command.strip().split(maxsplit=1)
    if not parts:
        return command
    
    tool = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    
    # Check if tool needs normalization
    if tool in TOOL_ABSOLUTE_PATHS:
        absolute_path = TOOL_ABSOLUTE_PATHS[tool]
        normalized = f"{absolute_path} {rest}".strip() if rest else absolute_path
        return normalized
    
    # Tool not in our list, return unchanged
    return command


def extract_tool_from_command(command: str) -> Optional[str]:
    """
    Extract the tool name from a command string.
    
    Args:
        command: Command string
    
    Returns:
        Tool name (first word) or None if command is empty
    
    Examples:
        >>> extract_tool_from_command("ffuf -u http://example.com")
        'ffuf'
        
        >>> extract_tool_from_command("/usr/bin/nmap -sV target")
        '/usr/bin/nmap'
        
        >>> extract_tool_from_command("")
        None
    """
    if not command or not command.strip():
        return None
    
    parts = command.strip().split(maxsplit=1)
    return parts[0] if parts else None


def is_normalized(command: str) -> bool:
    """
    Check if a command already uses an absolute path.
    
    Args:
        command: Command string
    
    Returns:
        True if command starts with '/', False otherwise
    
    Examples:
        >>> is_normalized("/usr/bin/ffuf -u http://example.com")
        True
        
        >>> is_normalized("ffuf -u http://example.com")
        False
    """
    tool = extract_tool_from_command(command)
    return tool is not None and tool.startswith('/')
