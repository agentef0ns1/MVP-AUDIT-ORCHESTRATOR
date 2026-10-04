#!/usr/bin/env python3
"""
Test parallel audit execution

Usage:
    python3 dev-tools/test_parallel_execution.py [project_id] [max_concurrent]
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.core.store import AuditStore
from audit_orchestrator.config import Settings


async def test_parallel(project_id: str = None, max_concurrent: int = 5):
    """Test parallel audit execution"""
    print("=" * 70)
    print("Testing Parallel Audit Execution")
    print("=" * 70)
    print()
    
    settings = Settings.from_args()
    store = AuditStore(settings)
    orch = AuditOrchestrator(settings, store)
    
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
            print("Usage: python3 dev-tools/test_parallel_execution.py <project_id> [max_concurrent]")
            return
    
    # Get project info
    try:
        project = store.get_project(project_id)
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print(f"Project ID: {project_id}")
    print(f"Base Path: {project['base_path']}")
    print(f"Profile: {project['profile']}")
    print(f"Max Concurrent: {max_concurrent}")
    print()
    
    # Get pending targets
    pending_targets = store.get_all_pending_targets(project_id)
    print(f"Pending targets: {len(pending_targets)}")
    print()
    
    if not pending_targets:
        print("No pending targets. Project may be completed or failed.")
        
        # Show statistics
        stats = store.get_project_statistics(project_id)
        print()
        print("Project Statistics:")
        print(f"  Total targets: {stats.get('total_targets', 0)}")
        print(f"  Completed: {stats.get('targets_completed', 0)}")
        print(f"  Failed: {stats.get('targets_failed', 0)}")
        print(f"  Pending: {stats.get('targets_pending', 0)}")
        return
    
    print("Starting parallel execution...")
    print()
    
    import time
    start_time = time.time()
    
    try:
        result = await orch.run_audit_parallel(
            project_id=project_id,
            max_concurrent=max_concurrent,
            auto_review=True
        )
        
        duration = time.time() - start_time
        
        print()
        print("=" * 70)
        print("Execution Results")
        print("=" * 70)
        print()
        print(f"✅ Completed: {result['targets_completed']}")
        print(f"❌ Failed: {result['targets_failed']}")
        print(f"📊 Total processed: {result['targets_processed']}")
        print(f"🔍 Services audited: {result['services_audited']}")
        print(f"🚨 Findings created: {result['findings_created']}")
        
        if result.get('re_enqueued', 0) > 0:
            print(f"🔄 Re-enqueued: {result['re_enqueued']}")
        
        print()
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"🚀 Parallel: {result.get('parallel', False)}")
        print(f"🔢 Concurrency: {result.get('max_concurrent', 'N/A')}")
        print()
        
        # Performance metrics
        if result['targets_processed'] > 0:
            avg_time = duration / result['targets_processed']
            print(f"📈 Average time per target: {avg_time:.2f}s")
        
        print()
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point"""
    project_id = sys.argv[1] if len(sys.argv) > 1 else None
    max_concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    asyncio.run(test_parallel(project_id, max_concurrent))


if __name__ == "__main__":
    main()
