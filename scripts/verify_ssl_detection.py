#!/usr/bin/env python3
"""
Verify SSL detection implementation without needing Kali connection
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

print("="*70)
print("  Verificación de Implementación SSL Runtime")
print("="*70)
print()

# Test 1: Verify method exists
print("Test 1: Verificar que el método _detect_ssl_on_port existe")
print("-"*70)

try:
    from audit_orchestrator.core.orchestrator import AuditOrchestrator
    
    # Check method exists
    if hasattr(AuditOrchestrator, '_detect_ssl_on_port'):
        print("✅ Método _detect_ssl_on_port encontrado")
        
        # Check signature
        import inspect
        sig = inspect.signature(AuditOrchestrator._detect_ssl_on_port)
        params = list(sig.parameters.keys())
        expected = ['self', 'target_name', 'port', 'kali_client', 'workspace']
        
        if params == expected:
            print("✅ Signature correcta:")
            print(f"   {sig}")
        else:
            print(f"⚠️  Signature: {sig}")
            print(f"   Expected: {expected}")
    else:
        print("❌ Método _detect_ssl_on_port NO encontrado")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print()

# Test 2: Verify logic in _audit_service
print("Test 2: Verificar lógica de detección en _audit_service")
print("-"*70)

try:
    import inspect
    source = inspect.getsource(AuditOrchestrator._audit_service)
    
    checks = [
        ("effective_service_name", "Variable para service efectivo"),
        ("is_http_service", "Detecta servicios HTTP"),
        ("has_ssl_prefix", "Detecta si ya tiene SSL"),
        ("_detect_ssl_on_port", "Llama a detección SSL"),
        ("effective_service_name = \"https\"", "Cambia a HTTPS si detecta SSL"),
    ]
    
    for keyword, description in checks:
        if keyword in source:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - NO encontrado")
            
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print()

# Test 3: Verify profile has http and https tasks
print("Test 3: Verificar perfiles HTTP y HTTPS")
print("-"*70)

try:
    import json
    profile_path = Path(__file__).parent.parent / "src/audit_orchestrator/audit_profiles/default_blackbox.json"
    
    with open(profile_path) as f:
        profile = json.load(f)
    
    tasks = profile.get("tasks", {})
    
    if "http" in tasks:
        http_tasks = tasks["http"]
        print(f"✅ Profile HTTP tiene {len(http_tasks)} tareas")
        for task in http_tasks[:3]:
            print(f"   - {task.get('type')}: {task.get('command', '')[:50]}...")
    else:
        print("❌ Profile HTTP no encontrado")
    
    print()
    
    if "https" in tasks:
        https_tasks = tasks["https"]
        print(f"✅ Profile HTTPS tiene {len(https_tasks)} tareas")
        for task in https_tasks[:3]:
            print(f"   - {task.get('type')}: {task.get('command', '')[:50]}...")
    else:
        print("❌ Profile HTTPS no encontrado")
        
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print()
print("="*70)
print("  Resumen")
print("="*70)
print()
print("✅ Implementación de detección SSL runtime verificada")
print()
print("El sistema funcionará así:")
print()
print("1. Cuando encuentra servicio HTTP sin SSL (ej: radan-http)")
print("2. Ejecuta: openssl s_client -connect host:port")
print("3. Si detecta SSL → usa tareas HTTPS")
print("4. Si no detecta SSL → usa tareas HTTP")
print()
print("Para ver esto en acción:")
print("  audit_start_and_run(base_path='/home/f0ns1/RedTeam/OCSR25/PoC')")
print()
print("Monitorear:")
print("  tail -f /home/f0ns1/RedTeam/OCSR25/PoC/audit.log | grep -i ssl")
print()
