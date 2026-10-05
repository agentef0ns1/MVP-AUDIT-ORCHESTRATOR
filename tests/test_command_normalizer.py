"""
Unit tests for command_normalizer module
"""
import pytest
from audit_orchestrator.core.command_normalizer import (
    normalize_command,
    extract_tool_from_command,
    is_normalized,
    TOOL_ABSOLUTE_PATHS
)


class TestNormalizeCommand:
    """Tests for normalize_command function"""
    
    def test_ffuf_normalization(self):
        """Test that ffuf command is normalized correctly"""
        cmd = "ffuf -u http://target/FUZZ -w wordlist.txt -mc 200,301,302"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/ffuf ")
        assert "http://target/FUZZ" in result
        assert "-w wordlist.txt" in result
    
    def test_wfuzz_normalization(self):
        """Test that wfuzz command is normalized correctly"""
        cmd = "wfuzz -z file,wordlist.txt http://target/FUZZ"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/wfuzz ")
        assert "wordlist.txt" in result
    
    def test_nmap_normalization(self):
        """Test that nmap command is normalized correctly"""
        cmd = "nmap -sV -p 80 10.0.0.1"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/nmap ")
        assert "-sV" in result
        assert "10.0.0.1" in result
    
    def test_nikto_normalization(self):
        """Test that nikto command is normalized correctly"""
        cmd = "nikto -h http://target:80 -Tuning 123"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/nikto ")
        assert "-h http://target:80" in result
    
    def test_whatweb_normalization(self):
        """Test that whatweb command is normalized correctly"""
        cmd = "whatweb https://target:443"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/whatweb ")
        assert "https://target:443" in result
    
    def test_testssl_normalization(self):
        """Test that testssl.sh command is normalized correctly"""
        cmd = "testssl.sh --fast target:443"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/testssl.sh ")
        assert "--fast" in result
    
    def test_unknown_tool_unchanged(self):
        """Test that unknown tools are not modified"""
        cmd = "unknowntool -x -y -z"
        result = normalize_command(cmd)
        assert result == cmd
    
    def test_empty_command(self):
        """Test that empty commands are handled"""
        assert normalize_command("") == ""
        assert normalize_command("   ") == "   "
    
    def test_command_with_no_args(self):
        """Test normalization of command with no arguments"""
        cmd = "ffuf"
        result = normalize_command(cmd)
        assert result == "/usr/bin/ffuf"
    
    def test_complex_ffuf_command(self):
        """Test complex ffuf command from audit profile"""
        cmd = "ffuf -u https://10.19.220.6:80/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-small-files-lowercase.txt -mc 200,301,302,403 -e .bak,.old,.backup,.zip,.tar.gz -t 20 2>&1 || true"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/ffuf ")
        assert "-u https://10.19.220.6:80/FUZZ" in result
        assert "-mc 200,301,302,403" in result
        assert "-e .bak,.old,.backup,.zip,.tar.gz" in result


class TestExtractToolFromCommand:
    """Tests for extract_tool_from_command function"""
    
    def test_extract_simple_tool(self):
        """Test extracting tool from simple command"""
        assert extract_tool_from_command("ffuf -u http://target") == "ffuf"
        assert extract_tool_from_command("nmap -sV target") == "nmap"
    
    def test_extract_tool_with_path(self):
        """Test extracting tool with absolute path"""
        assert extract_tool_from_command("/usr/bin/ffuf -u http://target") == "/usr/bin/ffuf"
    
    def test_extract_from_empty(self):
        """Test extracting tool from empty command"""
        assert extract_tool_from_command("") is None
        assert extract_tool_from_command("   ") is None
    
    def test_extract_tool_only(self):
        """Test extracting tool when command has no arguments"""
        assert extract_tool_from_command("ffuf") == "ffuf"


class TestIsNormalized:
    """Tests for is_normalized function"""
    
    def test_normalized_command(self):
        """Test that absolute path commands are detected as normalized"""
        assert is_normalized("/usr/bin/ffuf -u http://target") is True
        assert is_normalized("/usr/bin/nmap -sV target") is True
    
    def test_not_normalized_command(self):
        """Test that relative commands are detected as not normalized"""
        assert is_normalized("ffuf -u http://target") is False
        assert is_normalized("nmap -sV target") is False
    
    def test_empty_command(self):
        """Test that empty commands return False"""
        assert is_normalized("") is False
        assert is_normalized("   ") is False


class TestToolAbsolutePaths:
    """Tests for TOOL_ABSOLUTE_PATHS dictionary"""
    
    def test_all_paths_are_absolute(self):
        """Test that all tool paths are absolute"""
        for tool, path in TOOL_ABSOLUTE_PATHS.items():
            assert path.startswith("/"), f"Tool {tool} path {path} is not absolute"
    
    def test_critical_tools_present(self):
        """Test that critical security tools are in the mapping"""
        critical_tools = [
            "ffuf", "wfuzz", "nmap", "nikto", "whatweb", 
            "sslscan", "testssl.sh", "gobuster", "dirb"
        ]
        for tool in critical_tools:
            assert tool in TOOL_ABSOLUTE_PATHS, f"Critical tool {tool} missing from TOOL_ABSOLUTE_PATHS"
    
    def test_no_unexpected_duplicate_paths(self):
        """Test that there are no unexpected duplicate mappings"""
        from collections import Counter
        paths = list(TOOL_ABSOLUTE_PATHS.values())
        counts = Counter(paths)
        
        # These duplicates are intentional (tool name variations)
        expected_duplicates = {
            "/usr/bin/testssl.sh": ["testssl", "testssl.sh"],
            "/usr/bin/git-dumper": ["git-dumper", "gitdumper"]
        }
        
        for path, count in counts.items():
            if count > 1:
                # Check if this is an expected duplicate
                assert path in expected_duplicates, f"Unexpected duplicate path: {path}"
                # Verify the tools that map to this path
                tools_with_path = [tool for tool, p in TOOL_ABSOLUTE_PATHS.items() if p == path]
                assert set(tools_with_path) == set(expected_duplicates[path]), \
                    f"Unexpected tools for {path}: {tools_with_path}"


class TestRealWorldScenarios:
    """Tests for real-world audit scenarios"""
    
    def test_http_fuzzing_scenario(self):
        """Test HTTP fuzzing command normalization"""
        cmd = "ffuf -u http://10.19.220.6:80/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,301,302,401,403 -t 20 -fs 0 -timeout 10"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/ffuf ")
        assert all(param in result for param in ["-u", "-w", "-mc", "-t", "-fs", "-timeout"])
    
    def test_https_fuzzing_scenario(self):
        """Test HTTPS fuzzing command normalization"""
        cmd = "ffuf -u https://10.19.220.6:443/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,301,302,401,403 -t 20 -fs 0 -timeout 10"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/ffuf ")
        assert "https://10.19.220.6:443/FUZZ" in result
    
    def test_backup_files_scenario(self):
        """Test backup files fuzzing command normalization (the problematic case)"""
        cmd = "ffuf -u https://10.19.220.6:80/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-small-files-lowercase.txt -mc 200,301,302,403 -e .bak,.old,.backup,.zip,.tar.gz -t 20 2>&1 || true"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/ffuf ")
        # Verify critical parameters are preserved
        assert "-e .bak,.old,.backup,.zip,.tar.gz" in result
        assert "2>&1 || true" in result
    
    def test_nmap_version_scan(self):
        """Test nmap version scan normalization"""
        cmd = "nmap -sV -p 22,80,443 10.19.220.6"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/nmap ")
        assert "-sV -p 22,80,443 10.19.220.6" in result
    
    def test_wfuzz_api_fuzzing(self):
        """Test wfuzz API fuzzing (should remain wfuzz, not ffuf)"""
        cmd = "wfuzz -z file,/usr/share/seclists/Fuzzing/api-endpoints.txt http://target/api/FUZZ -hc 404 --hh BBB 2>&1 || true"
        result = normalize_command(cmd)
        assert result.startswith("/usr/bin/wfuzz ")
        assert "api-endpoints.txt" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
