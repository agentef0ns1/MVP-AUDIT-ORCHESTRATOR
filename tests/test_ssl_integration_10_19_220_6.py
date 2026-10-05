"""
Integration test for SSL detection on real target 10.19.220.6
"""
import pytest
from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.config import Settings
from audit_orchestrator.core.store import AuditStore
from audit_orchestrator.core.kali_client import KaliMCPClient
from audit_orchestrator.core.filesystem import WorkspaceManager
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
async def real_kali_client():
    """Real Kali client for integration testing"""
    client = KaliMCPClient(server_url="http://127.0.0.1:5001")
    yield client


@pytest.fixture
def temp_workspace():
    """Mocked workspace for testing"""
    from unittest.mock import MagicMock
    workspace = MagicMock(spec=WorkspaceManager)
    workspace.append_bitacora = MagicMock()
    return workspace


@pytest.mark.anyio
@pytest.mark.integration
class TestRealSSLDetection:
    """Integration tests against real target 10.19.220.6"""
    
    async def test_port_80_no_ssl_detection(self, real_kali_client, temp_workspace):
        """Test that port 80 (HTTP) is NOT detected as SSL"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        # Use a minimal mock store
        from unittest.mock import MagicMock
        store = MagicMock(spec=AuditStore)
        
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=80,
            service_name="http",
            kali_client=real_kali_client,
            workspace=temp_workspace
        )
        
        assert result is False, "Port 80 with service 'http' should NOT have SSL detected"
        
        # Check bitacora logged correctly
        calls = temp_workspace.append_bitacora.call_args_list
        assert len(calls) > 0, "Should have logged bitacora"
        # Should mention HTTP, not HTTPS
        logged_messages = " ".join([str(call) for call in calls])
        assert "HTTP" in logged_messages or "http" in logged_messages
    
    async def test_port_443_ssl_detection(self, real_kali_client, temp_workspace):
        """Test that port 443 (HTTPS) IS detected as SSL"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        from unittest.mock import MagicMock
        store = MagicMock(spec=AuditStore)
        
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=443,
            service_name="https",
            kali_client=real_kali_client,
            workspace=temp_workspace
        )
        
        assert result is True, "Port 443 with service 'https' should have SSL detected"
        
        # Check bitacora logged correctly
        calls = temp_workspace.append_bitacora.call_args_list
        assert len(calls) > 0, "Should have logged bitacora"
        logged_messages = " ".join([str(call) for call in calls])
        assert "HTTPS" in logged_messages or "https" in logged_messages or "SSL" in logged_messages
    
    async def test_port_22_ssh_no_web_detection(self, real_kali_client, temp_workspace):
        """Test that port 22 (SSH) is handled correctly - no web SSL detection needed"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        from unittest.mock import MagicMock
        store = MagicMock(spec=AuditStore)
        
        orchestrator = AuditOrchestrator(settings, store)
        
        # SSH service should not trigger SSL detection logic (only for web services)
        # This tests that non-web services don't inappropriately go through SSL detection
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=22,
            service_name="ssh",
            kali_client=real_kali_client,
            workspace=temp_workspace
        )
        
        # Should not detect as web SSL (SSH is not a web service)
        # The function should return False for SSH since it's not an SSL/TLS web service
        assert result is False, "SSH service should not be treated as HTTPS"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
