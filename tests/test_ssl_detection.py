"""
Tests for improved SSL detection logic
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.config import Settings
from audit_orchestrator.core.store import AuditStore
from audit_orchestrator.core.kali_client import KaliMCPClient
from audit_orchestrator.core.filesystem import WorkspaceManager
from pathlib import Path


@pytest.fixture
def mock_kali_client():
    """Mock Kali client for testing"""
    client = AsyncMock(spec=KaliMCPClient)
    return client


@pytest.fixture
def mock_workspace():
    """Mock workspace manager"""
    workspace = MagicMock(spec=WorkspaceManager)
    workspace.append_bitacora = MagicMock()
    return workspace


@pytest.mark.anyio
class TestSSLDetection:
    """Test SSL detection logic"""
    
    async def test_detect_ssl_by_service_name_https(self, mock_kali_client, mock_workspace):
        """Test SSL detection via service name 'https'"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=8080,
            service_name="https",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is True, "Should detect SSL for service name 'https'"
        mock_workspace.append_bitacora.assert_called()
        # Should not call openssl test since service name is definitive
        mock_kali_client.execute_command.assert_not_called()
    
    async def test_detect_ssl_by_service_name_ssl_http(self, mock_kali_client, mock_workspace):
        """Test SSL detection via service name 'ssl/http'"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.23",
            port=8088,
            service_name="ssl/radan-http",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is True, "Should detect SSL for service name with 'ssl' prefix"
        mock_kali_client.execute_command.assert_not_called()
    
    async def test_no_ssl_by_service_name_http(self, mock_kali_client, mock_workspace):
        """Test NO SSL detection for service name 'http'"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=8080,
            service_name="http",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is False, "Should NOT detect SSL for service name 'http'"
        mock_kali_client.execute_command.assert_not_called()
    
    async def test_port_80_always_http(self, mock_kali_client, mock_workspace):
        """Test that port 80 is always treated as HTTP"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=80,
            service_name="unknown",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is False, "Port 80 should always be HTTP"
        mock_kali_client.execute_command.assert_not_called()
    
    async def test_port_443_always_https(self, mock_kali_client, mock_workspace):
        """Test that port 443 is always treated as HTTPS"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=443,
            service_name="unknown",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is True, "Port 443 should always be HTTPS"
        mock_kali_client.execute_command.assert_not_called()
    
    async def test_common_http_ports(self, mock_kali_client, mock_workspace):
        """Test common HTTP alternate ports"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        http_ports = [8080, 8000, 8008, 3000, 5000]
        
        for port in http_ports:
            result = await orchestrator._detect_ssl_on_port(
                target_name="10.19.220.6",
                port=port,
                service_name="unknown",
                kali_client=mock_kali_client,
                workspace=mock_workspace
            )
            assert result is False, f"Port {port} should default to HTTP"
    
    async def test_common_https_ports(self, mock_kali_client, mock_workspace):
        """Test common HTTPS alternate ports"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        https_ports = [8443, 9443, 10443]
        
        for port in https_ports:
            result = await orchestrator._detect_ssl_on_port(
                target_name="10.19.220.6",
                port=port,
                service_name="unknown",
                kali_client=mock_kali_client,
                workspace=mock_workspace
            )
            assert result is True, f"Port {port} should default to HTTPS"
    
    async def test_openssl_test_with_real_ssl(self, mock_kali_client, mock_workspace):
        """Test openssl detection when real SSL is present"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        # Mock successful SSL detection
        mock_kali_client.execute_command.return_value = {"exit_code": 0}
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=9999,  # Unknown port
            service_name="unknown",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is True, "Should detect SSL via openssl test"
        mock_kali_client.execute_command.assert_called_once()
    
    async def test_openssl_test_without_ssl(self, mock_kali_client, mock_workspace):
        """Test openssl detection when no SSL is present"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        # Mock failed SSL detection
        mock_kali_client.execute_command.return_value = {"exit_code": 1}
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=9999,  # Unknown port
            service_name="unknown",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is False, "Should NOT detect SSL via openssl test"
        mock_kali_client.execute_command.assert_called_once()
    
    async def test_error_handling_defaults_to_http(self, mock_kali_client, mock_workspace):
        """Test that errors default appropriately"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        # Mock error in openssl test
        mock_kali_client.execute_command.side_effect = Exception("Connection error")
        
        # Port 80 should default to HTTP
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=80,
            service_name="unknown",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        assert result is False, "Error on port 80 should default to HTTP"
        
        # Port 443 should default to HTTPS
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=443,
            service_name="unknown",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        assert result is True, "Error on port 443 should default to HTTPS"


class TestRealWorldScenarios:
    """Test real-world scenarios from OCSR25 audit"""
    
    @pytest.mark.anyio
    async def test_port_80_http_service(self, mock_kali_client, mock_workspace):
        """Test 10.19.220.6:80 with service 'http' - should be HTTP"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=80,
            service_name="http",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is False, "10.19.220.6:80 (http) should be HTTP"
    
    @pytest.mark.anyio
    async def test_port_443_https_service(self, mock_kali_client, mock_workspace):
        """Test 10.19.220.6:443 with service 'https' - should be HTTPS"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.6",
            port=443,
            service_name="https",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is True, "10.19.220.6:443 (https) should be HTTPS"
    
    @pytest.mark.anyio
    async def test_port_8088_ssl_radan_http(self, mock_kali_client, mock_workspace):
        """Test port 8088 with service 'ssl/radan-http' - should be HTTPS"""
        settings = Settings(kali_server_url="http://127.0.0.1:5001")
        store = MagicMock(spec=AuditStore)
        orchestrator = AuditOrchestrator(settings, store)
        
        result = await orchestrator._detect_ssl_on_port(
            target_name="10.19.220.23",
            port=8088,
            service_name="ssl/radan-http",
            kali_client=mock_kali_client,
            workspace=mock_workspace
        )
        
        assert result is True, "Port 8088 with ssl/radan-http should be HTTPS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
