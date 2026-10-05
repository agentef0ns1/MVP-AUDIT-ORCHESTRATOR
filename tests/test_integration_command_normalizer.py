"""
Integration test to verify command normalization works in orchestrator
"""
from audit_orchestrator.core.command_normalizer import normalize_command


def test_real_audit_commands():
    """Test actual commands from audit profiles"""
    
    # Commands from default_blackbox.json profile
    test_cases = [
        # HTTP fuzzing
        {
            "template": "ffuf -u http://{target}:{port}/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,301,302,401,403 -t 20 -fs 0 -timeout 10",
            "expected_tool": "/usr/bin/ffuf"
        },
        # HTTPS backup files (the problematic one)
        {
            "template": "ffuf -u https://{target}:{port}/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-small-files-lowercase.txt -mc 200,301,302,403 -e .bak,.old,.backup,.zip,.tar.gz -t 20 2>&1 || true",
            "expected_tool": "/usr/bin/ffuf"
        },
        # wfuzz for API fuzzing
        {
            "template": "wfuzz -z file,/usr/share/seclists/Fuzzing/api-endpoints.txt http://{target}:{port}/api/FUZZ -hc 404 --hh BBB 2>&1 || true",
            "expected_tool": "/usr/bin/wfuzz"
        },
        # nmap scans
        {
            "template": "nmap -sV -p {port} {target}",
            "expected_tool": "/usr/bin/nmap"
        },
        {
            "template": "nmap -sC -p {port} {target}",
            "expected_tool": "/usr/bin/nmap"
        },
        # Web scanners
        {
            "template": "whatweb https://{target}:{port}",
            "expected_tool": "/usr/bin/whatweb"
        },
        {
            "template": "wafw00f https://{target}:{port}",
            "expected_tool": "/usr/bin/wafw00f"
        },
        {
            "template": "nikto -h http://{target}:{port} -Tuning 123bde -maxtime 4m",
            "expected_tool": "/usr/bin/nikto"
        },
        # SSL tools
        {
            "template": "sslscan {target}:{port}",
            "expected_tool": "/usr/bin/sslscan"
        },
        {
            "template": "testssl.sh --fast --warnings off {target}:{port}",
            "expected_tool": "/usr/bin/testssl.sh"
        },
    ]
    
    for test_case in test_cases:
        # Format with sample values
        command = test_case["template"].format(
            target="10.19.220.6",
            port=80,
            protocol="tcp"
        )
        
        # Normalize
        normalized = normalize_command(command)
        
        # Verify
        assert normalized.startswith(test_case["expected_tool"]), \
            f"Expected {test_case['expected_tool']}, got: {normalized.split()[0]}"
        
        print(f"✓ {test_case['expected_tool'].split('/')[-1]}: {normalized[:80]}...")


if __name__ == "__main__":
    test_real_audit_commands()
    print("\n✅ All integration tests passed!")
