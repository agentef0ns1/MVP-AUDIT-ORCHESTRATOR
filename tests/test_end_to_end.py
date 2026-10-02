"""
End-to-end test without requiring MCP server or special permissions
"""
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_workflow():
    """Test the basic workflow without actually executing commands"""
    print("🔍 Testing end-to-end workflow...")
    
    try:
        from audit_orchestrator.config import Settings
        from audit_orchestrator.core.store import AuditStore
        from audit_orchestrator.core.filesystem import WorkspaceManager
        from audit_orchestrator.core.parser import parse_nmap_output
        
        # Create temporary directories
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create a test input file
            test_input = tmpdir / "test_ports.txt"
            test_input.write_text("""10.0.0.1
Discovered open port 22/tcp on 10.0.0.1
Discovered open port 80/tcp on 10.0.0.1
22/tcp   open  ssh
80/tcp   open  http

10.0.0.2
Discovered open port 443/tcp on 10.0.0.2
443/tcp  open  https
""")
            
            print(f"   ✅ Created test input file")
            
            # Test parser
            targets = parse_nmap_output(test_input)
            print(f"   ✅ Parsed {len(targets)} target(s)")
            
            assert len(targets) == 2, "Should have 2 targets"
            assert "10.0.0.1" in targets, "Should have target 10.0.0.1"
            assert len(targets["10.0.0.1"]) == 2, "10.0.0.1 should have 2 ports"
            
            # Test database
            db_path = tmpdir / "test.db"
            settings = Settings(data_dir=str(tmpdir))
            settings.db_path = db_path
            
            store = AuditStore(settings)
            print(f"   ✅ Created store with database")
            
            # Create project
            project = store.create_project(
                base_path=str(tmpdir),
                input_file="test_ports.txt",
                profile="default_blackbox"
            )
            project_id = project["project_id"]
            print(f"   ✅ Created project: {project_id}")
            
            # Create workspace
            workspace = WorkspaceManager(tmpdir)
            
            for target_name, ports in targets.items():
                # Create workspace
                ws_paths = workspace.create_target_workspace(target_name, ports)
                print(f"   ✅ Created workspace for {target_name}")
                
                # Verify directories exist
                assert Path(ws_paths["enumeration"]).exists()
                assert Path(ws_paths["bitacora"]).exists()
                assert Path(ws_paths["findings"]).exists()
                
                # Create target in database
                target = store.create_target(
                    project_id=project_id,
                    ip_or_hostname=target_name,
                    work_dir=ws_paths["target_dir"],
                    ports=ports
                )
                target_id = target["target_id"]
                
                # Create services
                for port_info in ports:
                    service = store.create_service(
                        target_id=target_id,
                        port=port_info["port"],
                        protocol=port_info.get("protocol", "tcp"),
                        service_name=port_info.get("service"),
                        max_time_seconds=900
                    )
                    print(f"      ✅ Created service: {port_info['port']}/{port_info['protocol']}")
                
                # Test bitacora
                workspace.append_bitacora(
                    target_name,
                    "TEST: Test operation",
                    details="This is a test",
                    result="success"
                )
                
                # Test finding creation
                finding_path = workspace.create_finding(
                    target=target_name,
                    finding_id="test-001",
                    severity="high",
                    title="Test Finding",
                    description="This is a test finding",
                    service=f"{ports[0]['port']}/tcp",
                    evidence="Test evidence"
                )
                print(f"      ✅ Created test finding: {Path(finding_path).name}")
                
                # Create finding in database
                db_finding = store.create_finding(
                    project_id=project_id,
                    target_id=target_id,
                    severity="high",
                    title="Test Finding",
                    description="This is a test"
                )
                print(f"      ✅ Created finding in database: {db_finding['finding_id']}")
            
            # Get statistics
            stats = store.get_project_statistics(project_id)
            print(f"\n   📊 Statistics:")
            print(f"      Targets: {stats['total_targets']}")
            print(f"      Services: {stats['total_services']}")
            print(f"      Findings: {stats['total_findings']}")
            
            # Test querying
            targets_list = store.get_targets_by_project(project_id)
            print(f"   ✅ Retrieved {len(targets_list)} target(s) from database")
            
            findings_list = store.get_findings_by_project(project_id)
            print(f"   ✅ Retrieved {len(findings_list)} finding(s) from database")
            
            print(f"\n✅ End-to-end workflow test passed!")
            return True
    
    except Exception as e:
        print(f"\n❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_workflow()
    sys.exit(0 if success else 1)
