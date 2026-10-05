"""
Client for communicating with MCP Kali Server
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from audit_orchestrator.core.errors import KaliClientError


class KaliMCPClient:
    """
    Client for executing commands via MCP Kali Server.
    
    The MCP Kali Server is expected to be running at the configured URL
    (default: http://127.0.0.1:5001) and expose command execution capabilities.
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:5001", timeout: int = 900):
        self.server_url = server_url.rstrip("/")
        self.default_timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._client = httpx.AsyncClient(timeout=self.default_timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """Run a command and return the fields Type 2 and Type 3 callers expect."""
        result = await self.execute_command(command, timeout=timeout)
        stdout = result.get("output") or ""
        return {
            **result,
            "stdout": stdout,
            "output": stdout,
            "stderr": result.get("stderr") or "",
            "exit_code": result.get("exit_code", -1),
            "success": bool(result.get("success")),
            "execution_time": result.get("duration") or result.get("execution_time") or 0,
        }

    async def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        """
        Execute a command via MCP Kali Server.
        
        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds (None = use default)
            working_dir: Working directory for command execution
            env: Environment variables
        
        Returns:
            {
                "success": bool,
                "output": str,
                "stderr": str,
                "exit_code": int,
                "duration": float,
                "timed_out": bool,
                "error": str | None
            }
        
        This method NEVER raises exceptions - always returns a result dict.
        """
        if timeout is None:
            timeout = self.default_timeout
        
        start_time = time.time()
        
        try:
            # Prepare request payload
            payload = {
                "command": command,
                "timeout": timeout
            }
            
            if working_dir:
                payload["working_dir"] = working_dir
            
            if env:
                payload["env"] = env
            
            # Execute via MCP Kali Server
            result = await self._execute_via_mcp(payload, timeout)
            
            duration = time.time() - start_time
            
            # Add duration to result
            result["duration"] = duration
            
            return result
        
        except Exception as e:
            # Catch ALL exceptions to prevent loops
            duration = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration": duration,
                "timed_out": False,
                "error": f"Unexpected error: {e}"
            }
    
    async def _execute_via_mcp(
        self,
        payload: dict[str, Any],
        timeout: int
    ) -> dict[str, Any]:
        """
        Execute command via Kali Server API.
        
        Uses the /api/command endpoint of the Kali Server.
        """
        if not self._client:
            self._client = httpx.AsyncClient(timeout=timeout + 10)
        
        try:
            # Use the correct Kali Server endpoint: /api/command
            # Expected payload format: {"command": "nmap -sV target"}
            kali_payload = {
                "command": payload["command"]
            }
            
            # Add optional parameters
            if "working_dir" in payload:
                kali_payload["cwd"] = payload["working_dir"]
            if "timeout" in payload:
                kali_payload["timeout"] = payload["timeout"]
            
            response = await self._client.post(
                f"{self.server_url}/api/command",
                json=kali_payload,
                timeout=timeout + 10  # Add buffer for network
            )
            
            if response.status_code == 200:
                result = response.json()
                # Kali Server returns: {"stdout": "...", "stderr": "...", "return_code": 0}
                # Note: Kali uses "return_code" not "exit_code"
                return_code = result.get("return_code", -1)
                return {
                    "success": return_code == 0,
                    "output": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": return_code,  # Normalize to "exit_code" for internal use
                    "timed_out": result.get("timed_out", False),
                    "error": result.get("error")
                }
            else:
                # Don't raise exception - return error result instead
                error_msg = f"Server returned {response.status_code}: {response.text[:200]}"
                return {
                    "success": False,
                    "output": "",
                    "stderr": error_msg,
                    "exit_code": -1,
                    "timed_out": False,
                    "error": error_msg
                }
        
        except httpx.TimeoutException:
            # Return error result instead of raising
            return {
                "success": False,
                "output": "",
                "stderr": "Request timed out",
                "exit_code": -1,
                "timed_out": True,
                "error": "Request to MCP Kali server timed out"
            }
        
        except httpx.ConnectError:
            # Return error result instead of raising
            error_msg = f"Could not connect to MCP Kali server at {self.server_url}"
            return {
                "success": False,
                "output": "",
                "stderr": error_msg,
                "exit_code": -1,
                "timed_out": False,
                "error": error_msg
            }
        
        except Exception as e:
            # Return error result instead of raising - prevents infinite loops
            error_msg = f"MCP communication error: {str(e)}"
            return {
                "success": False,
                "output": "",
                "stderr": error_msg,
                "exit_code": -1,
                "timed_out": False,
                "error": error_msg
            }
    
    async def check_connection(self) -> bool:
        """
        Check if MCP Kali server is accessible.
        
        Returns True if server responds, False otherwise.
        """
        try:
            if not self._client:
                self._client = httpx.AsyncClient(timeout=5)
            
            response = await self._client.get(
                f"{self.server_url}/health",
                timeout=5
            )
            
            return response.status_code == 200
        
        except Exception:
            return False
    
    async def get_server_info(self) -> dict[str, Any]:
        """Get MCP Kali server information"""
        try:
            if not self._client:
                self._client = httpx.AsyncClient(timeout=10)
            
            response = await self._client.get(
                f"{self.server_url}/info",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Server returned {response.status_code}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    async def install_tool(self, tool_name: str) -> dict[str, Any]:
        """
        Install a tool on the Kali system via MCP.
        
        Args:
            tool_name: Name of the tool to install
        
        Returns:
            Result dictionary with success status
        """
        command = f"apt-get update && apt-get install -y {tool_name}"
        return await self.execute_command(command, timeout=600)
    
    async def check_tool_installed(self, tool_name: str) -> bool:
        """
        Check if a tool is installed.
        
        Args:
            tool_name: Name of the tool
        
        Returns:
            True if installed, False otherwise
        """
        result = await self.execute_command(
            f"which {tool_name}",
            timeout=5
        )
        return result["success"] and result["exit_code"] == 0


class KaliClientFactory:
    """Factory for creating Kali MCP clients"""
    
    _instance: Optional[KaliMCPClient] = None
    _server_url: str = "http://127.0.0.1:5001"
    _default_timeout: int = 900
    
    @classmethod
    def configure(cls, server_url: str, default_timeout: int = 900):
        """Configure factory defaults"""
        cls._server_url = server_url
        cls._default_timeout = default_timeout
        cls._instance = None  # Reset instance
    
    @classmethod
    def create(cls, timeout: Optional[int] = None) -> KaliMCPClient:
        """Create a new Kali MCP client instance"""
        timeout = timeout if timeout is not None else cls._default_timeout
        return KaliMCPClient(cls._server_url, timeout)
    
    @classmethod
    def get_shared(cls) -> KaliMCPClient:
        """Get shared singleton instance"""
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance


async def test_kali_connection(server_url: str = "http://127.0.0.1:5001") -> dict[str, Any]:
    """
    Test connection to MCP Kali server.
    
    Returns diagnostic information.
    """
    async with KaliMCPClient(server_url, timeout=10) as client:
        result = {
            "server_url": server_url,
            "connected": False,
            "info": {},
            "error": None
        }
        
        try:
            # Check connection
            connected = await client.check_connection()
            result["connected"] = connected
            
            if connected:
                # Get server info
                info = await client.get_server_info()
                result["info"] = info
            else:
                result["error"] = "Server did not respond to health check"
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
