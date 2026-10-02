"""
Custom exceptions for audit orchestrator
"""


class AuditOrchestratorError(Exception):
    """Base exception for audit orchestrator"""
    
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ProjectNotFoundError(AuditOrchestratorError):
    """Project not found in database"""
    
    def __init__(self, project_id: str):
        super().__init__(
            "project_not_found",
            f"Project not found: {project_id}"
        )


class TargetNotFoundError(AuditOrchestratorError):
    """Target not found in database"""
    
    def __init__(self, target_id: str):
        super().__init__(
            "target_not_found",
            f"Target not found: {target_id}"
        )


class ServiceNotFoundError(AuditOrchestratorError):
    """Service not found in database"""
    
    def __init__(self, service_id: str):
        super().__init__(
            "service_not_found",
            f"Service not found: {service_id}"
        )


class InvalidInputError(AuditOrchestratorError):
    """Invalid input data"""
    
    def __init__(self, message: str):
        super().__init__("invalid_input", message)


class KaliClientError(AuditOrchestratorError):
    """Error communicating with MCP Kali server"""
    
    def __init__(self, message: str):
        super().__init__("kali_client_error", message)


class ParserError(AuditOrchestratorError):
    """Error parsing input file"""
    
    def __init__(self, message: str):
        super().__init__("parser_error", message)


class FilesystemError(AuditOrchestratorError):
    """Error creating filesystem structure"""
    
    def __init__(self, message: str):
        super().__init__("filesystem_error", message)
