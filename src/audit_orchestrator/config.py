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
        
        # Parallel execution settings
        self.max_concurrent_targets = int(os.environ.get(
            "AUDIT_MAX_CONCURRENT", 
            "10"
        ))
        
        # Auto-review before run
        self.auto_review_on_run = os.environ.get(
            "AUDIT_AUTO_REVIEW", 
            "true"
        ).lower() in ("true", "1", "yes")
        
        # Error threshold for failed target detection (0.8 = 80% error lines)
        self.review_error_threshold = float(os.environ.get(
            "AUDIT_ERROR_THRESHOLD",
            "0.8"
        ))
    
    @classmethod
    def from_args(
        cls,
        data_dir: Optional[str] = None,
        kali_server_url: Optional[str] = None,
    ) -> Settings:
        """Create settings from command line arguments"""
        return cls(data_dir=data_dir, kali_server_url=kali_server_url)
