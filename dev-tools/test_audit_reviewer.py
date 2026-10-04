#!/usr/bin/env python3
"""
Test audit reviewer functionality

Usage:
    python3 dev-tools/test_audit_reviewer.py [project_id]
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.audit_reviewer import AuditReviewer
from audit_orchestrator.core.store import AuditStore
from audit_orchestrator.config import Settings


def test_reviewer(project_id: str = None, re_enqueue: bool = False):
    """Test audit reviewer"""
    print("=" * 70)
    print("Testing Audit Reviewer")
    print("=" * 70)
    print()
    
    settings = Settings.from_args()
    store = AuditStore(settings)
    
    # If no project_id provided, list available projects
    if not project_id:
        print("No project_id provided. Listing available projects:")
        print()
        
        with store.db.connection() as conn:
            cursor = conn.execute("""
                SELECT project_id, base_path, status, created_at 
                FROM projects 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            projects = cursor.fetchall()
            
            if not projects:
                print("No projects found. Create one with audit_start() first.")
                return
            
            print(f"{'Project ID':<40} {'Status':<15} {'Base Path'}")
            print("-" * 100)
            
            for project in projects:
                pid = project[0]
                bpath = project[1]
                status = project[2]
                print(f"{pid:<40} {status:<15} {bpath}")
            
            print()
            print("Usage: python3 dev-tools/test_audit_reviewer.py <project_id> [--re-enqueue]")
            return
    
    # Get project
    try:
        project = store.get_project(project_id)
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    base_path = Path(project["base_path"])
    
    print(f"Project ID: {project_id}")
    print(f"Base Path: {base_path}")
    print(f"Re-enqueue failed: {re_enqueue}")
    print()
    
    # Create reviewer
    reviewer = AuditReviewer(base_path, store)
    
    # Review project
    print("Reviewing project...")
    print()
    
    if re_enqueue:
        result = reviewer.review_project(project_id)
    else:
        # Review without re-enqueuing
        targets = store.get_targets(project_id)
        failed_targets = []
        
        for target in targets:
            failure_reason = reviewer._is_target_failed(target)
            if failure_reason:
                failed_targets.append({
                    "ip": target["ip_or_hostname"],
                    "target_id": target["target_id"],
                    "status": target["status"],
                    "reason": failure_reason
                })
        
        result = {
            "total_targets": len(targets),
            "failed_targets": failed_targets,
            "re_enqueued": 0,
            "report": reviewer._generate_services_report(project_id, targets)
        }
    
    # Display results
    print("=" * 70)
    print("Review Results")
    print("=" * 70)
    print()
    print(f"Total targets: {result['total_targets']}")
    print(f"Failed targets detected: {len(result['failed_targets'])}")
    
    if re_enqueue:
        print(f"Re-enqueued: {result['re_enqueued']}")
    
    print()
    
    if result['failed_targets']:
        print("Failed Targets:")
        print("-" * 70)
        for target in result['failed_targets']:
            print(f"  • {target['ip']} ({target['status']})")
            print(f"    Reason: {target['reason']}")
            print()
    else:
        print("✅ No failed targets detected!")
        print()
    
    # Save and display report preview
    report_path = base_path / "SERVICES_REPORT.md"
    report_path.write_text(result["report"], encoding="utf-8")
    
    print("=" * 70)
    print("Services Report Generated")
    print("=" * 70)
    print()
    print(f"Report saved to: {report_path}")
    print()
    print("Report preview (first 1000 chars):")
    print("-" * 70)
    print(result["report"][:1000])
    if len(result["report"]) > 1000:
        print("...")
        print(f"\n[Full report: {len(result['report'])} characters]")
    print()
    print("=" * 70)


def main():
    """Main entry point"""
    project_id = None
    re_enqueue = False
    
    for arg in sys.argv[1:]:
        if arg in ("--re-enqueue", "-r"):
            re_enqueue = True
        elif not arg.startswith("-"):
            project_id = arg
    
    test_reviewer(project_id, re_enqueue)


if __name__ == "__main__":
    main()
