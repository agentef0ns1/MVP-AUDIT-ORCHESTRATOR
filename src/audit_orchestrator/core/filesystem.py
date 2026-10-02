"""
Filesystem management for audit workspaces
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from audit_orchestrator.core.errors import FilesystemError


class WorkspaceManager:
    """Manages filesystem structure for audit projects"""
    
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        if not self.base_path.exists():
            raise FilesystemError(f"Base path does not exist: {base_path}")
        
        if not self.base_path.is_dir():
            raise FilesystemError(f"Base path is not a directory: {base_path}")
    
    def create_target_workspace(
        self,
        target: str,
        ports: list[dict[str, Any]]
    ) -> dict[str, str]:
        """
        Create directory structure for a target.
        
        Structure:
            {base_path}/{target}/
                ├── enumeration/
                │   └── ports.json
                ├── bitacora/
                │   └── audit_{date}.log
                └── findings/
                    └── INDICE.md
        
        Returns:
            Dictionary with paths to created directories
        """
        # Sanitize target name for filesystem
        safe_target = self._sanitize_filename(target)
        target_dir = self.base_path / safe_target
        
        try:
            # Create main directories
            enumeration_dir = target_dir / "enumeration"
            bitacora_dir = target_dir / "bitacora"
            findings_dir = target_dir / "findings"
            
            enumeration_dir.mkdir(parents=True, exist_ok=True)
            bitacora_dir.mkdir(parents=True, exist_ok=True)
            findings_dir.mkdir(parents=True, exist_ok=True)
            
            # Create initial ports.json in enumeration
            ports_file = enumeration_dir / "ports.json"
            self._write_json(ports_file, {"target": target, "ports": ports})
            
            # Create initial bitacora log
            log_date = datetime.now().strftime("%Y%m%d")
            bitacora_file = bitacora_dir / f"audit_{log_date}.log"
            self._append_bitacora(
                bitacora_file,
                f"TARGET: {target}",
                f"Workspace created with {len(ports)} port(s)"
            )
            
            # Create findings index
            findings_index = findings_dir / "INDICE.md"
            self._create_findings_index(findings_index, target)
            
            return {
                "target_dir": str(target_dir),
                "enumeration": str(enumeration_dir),
                "bitacora": str(bitacora_dir),
                "findings": str(findings_dir)
            }
        
        except Exception as e:
            raise FilesystemError(f"Failed to create workspace for {target}: {e}")
    
    def write_enumeration_output(
        self,
        target: str,
        task_type: str,
        output: str,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Write enumeration output to file.
        
        Returns path to created file.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        safe_target = self._sanitize_filename(target)
        enumeration_dir = self.base_path / safe_target / "enumeration"
        
        if not enumeration_dir.exists():
            raise FilesystemError(f"Enumeration directory not found for {target}")
        
        # Generate filename
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{task_type}_{ts_str}.txt"
        output_file = enumeration_dir / filename
        
        try:
            output_file.write_text(output, encoding="utf-8")
            return str(output_file)
        except Exception as e:
            raise FilesystemError(f"Failed to write enumeration output: {e}")
    
    def append_bitacora(
        self,
        target: str,
        operation: str,
        details: Optional[str] = None,
        command: Optional[str] = None,
        result: str = "info"
    ) -> None:
        """
        Append entry to bitacora log files.
        
        Writes to:
        - Target-specific log: <target>/bitacora/audit_YYYYMMDD.log
        - Global log: audit.log (with [TARGET: X] prefix)
        
        Format:
            [2026-09-30 12:45:32] [10.19.220.23] SERVICE: 8088/tcp (radan-http)
            [2026-09-30 12:45:33] [10.19.220.23] TASK: whatweb
            [2026-09-30 12:45:33] [10.19.220.23] COMMAND: whatweb http://10.19.220.23:8088
            [2026-09-30 12:45:35] [10.19.220.23] RESULT: success (2.3s)
        """
        safe_target = self._sanitize_filename(target)
        bitacora_dir = self.base_path / safe_target / "bitacora"
        
        if not bitacora_dir.exists():
            raise FilesystemError(f"Bitacora directory not found for {target}")
        
        log_date = datetime.now().strftime("%Y%m%d")
        bitacora_file = bitacora_dir / f"audit_{log_date}.log"
        
        # Build log lines
        lines = [operation]
        if command:
            lines.append(f"COMMAND: {command}")
        if details:
            lines.append(details)
        if result:
            lines.append(f"RESULT: {result}")
        
        # Write to target-specific log
        self._append_bitacora(bitacora_file, *lines)
        
        # Write to global log with target prefix
        global_log = self.base_path / "audit.log"
        global_lines = [f"[{target}] {line}" for line in lines]
        self._append_bitacora(global_log, *global_lines)
    
    def create_finding(
        self,
        target: str,
        finding_id: str,
        severity: str,
        title: str,
        description: str = "",
        service: Optional[str] = None,
        cwe: Optional[str] = None,
        cvss_score: Optional[float] = None,
        evidence: str = "",
        exploit_available: bool = False,
        recommendation: str = "",
        references: list[str] = None
    ) -> str:
        """
        Create a finding markdown file.
        
        Returns path to created file.
        """
        safe_target = self._sanitize_filename(target)
        findings_dir = self.base_path / safe_target / "findings"
        
        if not findings_dir.exists():
            raise FilesystemError(f"Findings directory not found for {target}")
        
        # Get next finding number
        finding_num = self._get_next_finding_number(findings_dir)
        
        # Sanitize title for filename
        safe_title = self._sanitize_filename(title, max_length=50)
        filename = f"FIND-{finding_num:03d}-{severity.upper()}-{safe_title}.md"
        finding_file = findings_dir / filename
        
        # Generate markdown content
        content = self._format_finding_markdown(
            finding_id=finding_id,
            target=target,
            service=service,
            severity=severity,
            title=title,
            description=description,
            cwe=cwe,
            cvss_score=cvss_score,
            evidence=evidence,
            exploit_available=exploit_available,
            recommendation=recommendation,
            references=references or []
        )
        
        try:
            finding_file.write_text(content, encoding="utf-8")
            
            # Update findings index
            self._update_findings_index(findings_dir, finding_num, severity, title, filename)
            
            return str(finding_file)
        except Exception as e:
            raise FilesystemError(f"Failed to create finding: {e}")
    
    def get_target_dir(self, target: str) -> Path:
        """Get target directory path"""
        safe_target = self._sanitize_filename(target)
        return self.base_path / safe_target
    
    def target_exists(self, target: str) -> bool:
        """Check if target workspace exists"""
        return self.get_target_dir(target).exists()
    
    def _sanitize_filename(self, name: str, max_length: int = 255) -> str:
        """Sanitize string for use as filename"""
        # Replace invalid characters
        safe = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Replace multiple underscores with single
        safe = re.sub(r'_+', '_', safe)
        # Remove leading/trailing underscores and dots
        safe = safe.strip('_.')
        # Limit length
        if len(safe) > max_length:
            safe = safe[:max_length]
        return safe or "unnamed"
    
    def _write_json(self, file_path: Path, data: Any) -> None:
        """Write JSON data to file"""
        import json
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _append_bitacora(self, file_path: Path, *lines: str) -> None:
        """Append lines to bitacora with timestamps"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entries = []
        for line in lines:
            entries.append(f"[{timestamp}] {line}")
        
        content = "\n".join(entries) + "\n"
        
        with file_path.open("a", encoding="utf-8") as f:
            f.write(content)
    
    def _create_findings_index(self, file_path: Path, target: str) -> None:
        """Create initial findings index"""
        content = f"""# Findings Index - {target}

## Summary

No findings recorded yet.

## Findings by Severity

### Critical

### High

### Medium

### Low

### Info

---
*Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
        file_path.write_text(content, encoding="utf-8")
    
    def _get_next_finding_number(self, findings_dir: Path) -> int:
        """Get next sequential finding number"""
        existing = list(findings_dir.glob("FIND-*.md"))
        if not existing:
            return 1
        
        numbers = []
        for f in existing:
            match = re.match(r'FIND-(\d+)-', f.name)
            if match:
                numbers.append(int(match.group(1)))
        
        return max(numbers) + 1 if numbers else 1
    
    def _format_finding_markdown(
        self,
        finding_id: str,
        target: str,
        severity: str,
        title: str,
        description: str,
        service: Optional[str] = None,
        cwe: Optional[str] = None,
        cvss_score: Optional[float] = None,
        evidence: str = "",
        exploit_available: bool = False,
        recommendation: str = "",
        references: list[str] = None
    ) -> str:
        """Format finding as markdown"""
        lines = [
            f"# {title}",
            "",
            f"**Finding ID:** {finding_id}",
            f"**Target:** {target}",
        ]
        
        if service:
            lines.append(f"**Service:** {service}")
        
        lines.extend([
            f"**Severity:** {severity.upper()}",
        ])
        
        if cwe:
            lines.append(f"**CWE:** {cwe}")
        
        if cvss_score is not None:
            lines.append(f"**CVSS Score:** {cvss_score}")
        
        lines.extend([
            "",
            "## Descripción",
            "",
            description if description else "No description provided.",
            "",
        ])
        
        if evidence:
            lines.extend([
                "## Evidencia",
                "",
                evidence,
                "",
            ])
        
        if exploit_available:
            lines.extend([
                "## Exploit Disponible",
                "",
                "⚠️ Exploit público disponible para esta vulnerabilidad.",
                "",
            ])
        
        if recommendation:
            lines.extend([
                "## Recomendación",
                "",
                recommendation,
                "",
            ])
        
        if references:
            lines.extend([
                "## Referencias",
                "",
            ])
            for ref in references:
                lines.append(f"- {ref}")
            lines.append("")
        
        lines.extend([
            "---",
            f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])
        
        return "\n".join(lines)
    
    def _update_findings_index(
        self,
        findings_dir: Path,
        finding_num: int,
        severity: str,
        title: str,
        filename: str
    ) -> None:
        """Update findings index with new finding"""
        index_file = findings_dir / "INDICE.md"
        
        if not index_file.exists():
            return
        
        try:
            content = index_file.read_text(encoding="utf-8")
            
            # Find the appropriate severity section
            severity_upper = severity.upper()
            section_marker = f"### {severity_upper.capitalize()}"
            
            # Add entry after the severity header
            entry = f"- [{finding_num:03d}] [{title}]({filename})"
            
            # Find section and insert
            lines = content.split("\n")
            new_lines = []
            found_section = False
            
            for i, line in enumerate(lines):
                new_lines.append(line)
                
                if line.strip() == section_marker:
                    found_section = True
                    # Look ahead to insert before next section or at end
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith("###"):
                        j += 1
                    
                    # Insert entry
                    new_lines.append("")
                    new_lines.append(entry)
                    
                    # Add remaining lines
                    new_lines.extend(lines[i+1:j])
                    new_lines.extend(lines[j:])
                    break
            
            if not found_section:
                new_lines.append("")
                new_lines.append(section_marker)
                new_lines.append("")
                new_lines.append(entry)
            
            # Update last modified
            final_content = "\n".join(new_lines)
            final_content = re.sub(
                r'\*Last updated:.*\*',
                f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
                final_content
            )
            
            index_file.write_text(final_content, encoding="utf-8")
        
        except Exception as e:
            # Non-critical error, log but don't fail
            print(f"Warning: Could not update findings index: {e}")


def create_resumen_auditoria(
    base_path: str | Path,
    project_id: str,
    targets_summary: dict[str, Any],
    findings_summary: dict[str, Any]
) -> str:
    """
    Create executive summary report.
    
    Returns path to created file.
    """
    base_path = Path(base_path)
    resumen_file = base_path / "RESUMEN-AUDITORIA.md"
    
    content = f"""# Resumen Ejecutivo de Auditoría

**Project ID:** {project_id}
**Fecha:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Alcance

**Targets analizados:** {targets_summary.get('total', 0)}
**Servicios auditados:** {findings_summary.get('total_services', 0)}

## Estadísticas de Targets

- Completados: {targets_summary.get('completed', 0)}
- Fallidos: {targets_summary.get('failed', 0)}
- Pendientes: {targets_summary.get('pending', 0)}

## Hallazgos

**Total de findings:** {findings_summary.get('total', 0)}

### Por Severidad

- **Critical:** {findings_summary.get('critical', 0)}
- **High:** {findings_summary.get('high', 0)}
- **Medium:** {findings_summary.get('medium', 0)}
- **Low:** {findings_summary.get('low', 0)}
- **Info:** {findings_summary.get('info', 0)}

## Estructura de Archivos

Cada target auditado tiene su directorio con la siguiente estructura:

```
{base_path}/
├── [IP_o_hostname]/
│   ├── enumeration/     # Outputs de herramientas de enumeración
│   ├── bitacora/        # Logs de operaciones realizadas
│   └── findings/        # Vulnerabilidades detectadas
└── RESUMEN-AUDITORIA.md # Este archivo
```

## Próximos Pasos

1. Revisar todos los findings en cada directorio de target
2. Validar manualmente las vulnerabilidades detectadas
3. Priorizar remediación según severidad
4. Realizar pruebas de explotación controladas si es necesario

---
*Generado automáticamente por MVP Audit Orchestrator*
"""
    
    try:
        resumen_file.write_text(content, encoding="utf-8")
        return str(resumen_file)
    except Exception as e:
        raise FilesystemError(f"Failed to create resumen: {e}")
