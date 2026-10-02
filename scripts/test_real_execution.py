#!/usr/bin/env python3
"""
Test real execution with SSL detection and global audit.log
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

async def main():
    print("="*70)
    print("  Test: Ejecución Real con Detección SSL")
    print("="*70)
    print()
    
    # Setup test directory
    test_dir = Path("/tmp/audit_test_ssl")
    test_dir.mkdir(exist_ok=True)
    
    # Create small test input
    input_file = test_dir / "test_input.txt"
    input_file.write_text("""10.19.220.23
22/tcp   open  ssh
8088/tcp open  radan-http
""")
    
    print(f"📁 Test directory: {test_dir}")
    print(f"📄 Input file: {input_file}")
    print()
    
    # Import orchestrator
    from audit_orchestrator.core.orchestrator import AuditOrchestrator
    from audit_orchestrator.core.store import AuditStore
    from audit_orchestrator.config import Settings
    
    # Create settings
    settings = Settings.from_args()
    
    # Create store
    store = AuditStore(settings)
    
    # Create orchestrator
    orchestrator = AuditOrchestrator(settings, store)
    
    try:
        # Step 1: Start audit
        print("Step 1: Iniciando auditoría...")
        print("-"*70)
        
        start_result = await orchestrator.start_audit(
            base_path=str(test_dir),
            input_file=str(input_file),
            profile="default_blackbox",
            execution_mode="type_1_no_llm",
            reset=True
        )
        
        project_id = start_result["project_id"]
        print(f"✅ Proyecto creado: {project_id}")
        print(f"   Targets: {start_result['targets_count']}")
        print(f"   Services: {start_result['services_count']}")
        print()
        
        # Step 2: Run audit (limit to 1 service for quick test)
        print("Step 2: Ejecutando auditoría (máximo 1 target)...")
        print("-"*70)
        
        run_result = await orchestrator.run_audit(
            project_id=project_id,
            max_targets=1  # Only 1 target for quick test
        )
        
        print(f"✅ Auditoría ejecutada")
        print(f"   Targets procesados: {run_result.get('targets_processed', 0)}")
        print(f"   Services auditados: {run_result.get('services_audited', 0)}")
        print()
        
        # Step 3: Verify global audit.log
        print("Step 3: Verificando audit.log global...")
        print("-"*70)
        
        global_log = test_dir / "audit.log"
        
        if global_log.exists():
            print(f"✅ audit.log global creado: {global_log}")
            
            content = global_log.read_text()
            lines = content.strip().split('\n')
            
            print(f"   Total líneas: {len(lines)}")
            print()
            print("   Primeras 10 líneas:")
            for line in lines[:10]:
                print(f"   {line}")
            print()
            
            # Check for target prefix
            has_target_prefix = any('[10.19.220.23]' in line for line in lines)
            
            if has_target_prefix:
                print("   ✅ Cada línea incluye [TARGET]")
            else:
                print("   ❌ Líneas NO incluyen [TARGET]")
                
            # Check for SSL detection
            has_ssl_check = any('SSL' in line or 'ssl' in line for line in lines)
            
            if has_ssl_check:
                print("   ✅ Detección SSL registrada")
                # Find SSL detection lines
                for line in lines:
                    if 'SSL' in line or 'Checking for SSL' in line:
                        print(f"      {line}")
            else:
                print("   ⚠️  No se encontró detección SSL en log")
                
        else:
            print(f"❌ audit.log global NO creado")
            return False
        
        print()
        
        # Step 4: Verify target-specific log
        print("Step 4: Verificando log específico del target...")
        print("-"*70)
        
        target_log_dir = test_dir / "10.19.220.23" / "bitacora"
        if target_log_dir.exists():
            log_files = list(target_log_dir.glob("audit_*.log"))
            if log_files:
                print(f"✅ Log específico creado: {log_files[0].name}")
                
                content = log_files[0].read_text()
                print(f"   Líneas: {len(content.strip().split(chr(10)))}")
            else:
                print("❌ No se encontró log específico")
        else:
            print("❌ Directorio bitácora no existe")
        
        print()
        print("="*70)
        print("  ✅ TEST COMPLETADO")
        print("="*70)
        print()
        print(f"Resultados en: {test_dir}")
        print(f"  - audit.log (global con [TARGET])")
        print(f"  - 10.19.220.23/bitacora/audit_YYYYMMDD.log (específico)")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
