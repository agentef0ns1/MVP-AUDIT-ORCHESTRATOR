"""
Configuration management for audit orchestrator
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class Settings:
    """Global settings for the audit orchestrator"""
    
    def __init__(
        self,
        data_dir: Optional[str] = None,
        kali_server_url: Optional[str] = None,
    ):
        # Data directory for SQLite database
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path.home() / ".local" / "share" / "audit-orchestrator"
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite database path
        self.db_path = self.data_dir / "audit_state.db"
        
        # MCP Kali Server URL
        self.kali_server_url = kali_server_url or os.environ.get(
            "KALI_SERVER_URL", 
            "http://127.0.0.1:5001"
        )
        
        # Maximum time per service (seconds) - 15 minutes
        self.max_time_per_service = 900
        
        # Default audit profile
        self.default_profile = "default_blackbox"
    
    @classmethod
    def from_args(
        cls,
        data_dir: Optional[str] = None,
        kali_server_url: Optional[str] = None,
    ) -> Settings:
        """Create settings from command line arguments"""
        return cls(data_dir=data_dir, kali_server_url=kali_server_url)
