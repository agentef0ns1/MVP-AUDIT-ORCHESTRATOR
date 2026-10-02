"""
Command validator for maintaining security constraints
"""
import re
from typing import List


# Allowed reconnaissance and security scanning tools
ALLOWED_TOOLS = [
    # Network scanning
    "nmap", "masscan", "nc", "netcat",
    # Web scanning
    "whatweb", "wafw00f", "nikto", "wpscan", "droopescan", "joomscan", "cmseek",
    # Fuzzing and enumeration
    "ffuf", "gobuster", "dirb", "dirbuster", "feroxbuster", "wfuzz", "arjun",
    # SSL/TLS
    "sslscan", "testssl", "testssl.sh",
    # SSH
    "ssh-audit", "ssh-keyscan",
    # SMB
    "enum4linux", "smbclient",
    # Database
    "redis-cli",
    # Content discovery
    "wget", "curl", "grep", "linkfinder",
    # JavaScript/Code analysis
    "trufflehog", "retire", "wappalyzer",
    # GraphQL
    "graphw00f",
    # Version control
    "git-dumper", "gitdumper",
    # Security headers
    "shcheck", "shcheck.py",
]

# Commands blocked (DoS, brute-force online, destructive)
BLOCKED_COMMANDS = [
    "hping3",
    "slowloris",
    "thc-ssl-dos",
    "hydra",
    "medusa",
    "ncrack",
    "rm -rf",
    "dd if=",
    ":(){ :|:& };:",  # Fork bomb
    "mkfs.",  # Format filesystem
    ">/dev/sd",  # Write to disk
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
    "halt",
    "poweroff",
]

# Blocked patterns (regex)
BLOCKED_PATTERNS = [
    r"while\s+true.*do",  # Infinite loops
    r"for\s+i\s+in.*\d{4,}",  # Long loops (1000+ iterations)
    r">\s*/dev/sd",  # Write to disk devices
    r"rm\s+-rf\s+/",  # Recursive delete from root
    r"chmod\s+777",  # Dangerous permissions
    r"&&\s*rm\s+-rf",  # Command chain with recursive delete
    r"\|\s*bash",  # Pipe to bash (dangerous)
    r"curl.*\|\s*sh",  # Download and execute
    r"wget.*\|\s*sh",  # Download and execute
]


def validate_safe_command(command: str) -> tuple[bool, str]:
    """
    Validate that the command respects security restrictions.
    
    Restrictions enforced:
    - Only allowed reconnaissance tools can be used
    - No DoS attacks (hping3, slowloris, etc.)
    - No online brute-force (hydra, medusa, ncrack)
    - No destructive commands (rm -rf, dd, mkfs)
    - No infinite or very long loops
    - No system shutdown/reboot commands
    - No dangerous permission changes
    - No download-and-execute patterns
    
    Args:
        command: Command to validate
    
    Returns:
        Tuple of (is_valid, reason)
        - is_valid: True if command is safe, False otherwise
        - reason: Explanation if command is blocked, empty string if safe
    """
    if not command or not command.strip():
        return False, "Empty command not allowed"
    
    command_lower = command.lower()
    
    # Extract the base command (first word, handling sudo/timeout/etc.)
    parts = command.strip().split()
    base_cmd = parts[0] if parts else ""
    if base_cmd in ["sudo", "timeout", "time"]:
        base_cmd = parts[1] if len(parts) > 1 else ""
    
    # Check if command uses an allowed tool (allow basic shell commands too)
    basic_shell_commands = ["echo", "cat", "head", "tail", "grep", "awk", "sed", "cut", 
                           "sort", "uniq", "wc", "mkdir", "ls", "cd", "pwd", "true", "false"]
    cmd_allowed = False
    for tool in ALLOWED_TOOLS + basic_shell_commands:
        if base_cmd == tool or base_cmd.endswith("/" + tool):
            cmd_allowed = True
            break
    
    if not cmd_allowed and base_cmd:
        # Allow shell redirections and pipe operations
        if base_cmd not in [">", ">>", "|", "&&", "||", "2>&1"]:
            return False, f"Tool '{base_cmd}' is not in the allowed tools list (security policy)"
    
    # Check blocked commands
    for blocked in BLOCKED_COMMANDS:
        if blocked.lower() in command_lower:
            return False, f"Blocked command detected: '{blocked}' (security policy violation)"
    
    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command_lower):
            return False, f"Blocked pattern detected: '{pattern}' (security policy violation)"
    
    # Additional checks for command injection attempts
    if ";;" in command or ";" in command and "|" in command:
        # Allow single semicolons and pipes, but be careful with combinations
        suspicious_patterns = [
            r";\s*rm",
            r";\s*dd",
            r";\s*shutdown",
            r";\s*reboot",
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, command_lower):
                return False, f"Suspicious command chain detected (security policy violation)"
    
    return True, ""


def get_safety_guidelines() -> str:
    """
    Get human-readable safety guidelines for LLM-generated commands.
    
    Returns:
        String with safety guidelines
    """
    return """
Security Constraints for Command Execution:

PROHIBITED ACTIONS:
1. Denial of Service (DoS) attacks
   - No flood attacks (hping3, slowloris, etc.)
   - No resource exhaustion attacks
   - No infinite loops or very long loops

2. Brute-Force Attacks (Online)
   - No password brute-forcing (hydra, medusa, ncrack)
   - No authentication bypass attempts via brute-force

3. Destructive Operations
   - No file system destruction (rm -rf, dd, mkfs)
   - No system shutdown/reboot commands
   - No disk device manipulation

4. Dangerous Patterns
   - No download-and-execute (curl|sh, wget|sh)
   - No dangerous permission changes (chmod 777)
   - No command injection attempts

ALLOWED ACTIONS:
1. Reconnaissance and enumeration
   - Network scanning (nmap, masscan with rate limits)
   - Service enumeration (nikto, whatweb, wpscan)
   - Directory/file enumeration (gobuster, dirb, dirbuster)

2. Vulnerability verification (non-exploitative)
   - Check if vulnerability exists (e.g., curl to test endpoint)
   - Version detection
   - Configuration analysis

3. Safe PoC tests
   - Read-only operations
   - Non-destructive tests
   - Proof of vulnerability without exploitation

GUIDELINES:
- Always prefer read-only operations
- Use timeouts to prevent hanging
- Respect rate limits on network operations
- Document reasoning for each command
- Stop if uncertain about safety
"""
