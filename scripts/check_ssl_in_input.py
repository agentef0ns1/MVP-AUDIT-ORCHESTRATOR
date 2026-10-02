#!/usr/bin/env python3
"""
Check if input file has SSL detection info
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_ssl_in_input.py <input_file>")
        print("")
        print("Example:")
        print("  python3 check_ssl_in_input.py /home/f0ns1/RedTeam/OCSR25/PoC/open_ports.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    print("="*70)
    print("  Checking SSL Detection in Input File")
    print("="*70)
    print()
    print(f"File: {input_file}")
    print()
    
    if not Path(input_file).exists():
        print(f"❌ File not found: {input_file}")
        sys.exit(1)
    
    # Parse with updated parser
    from audit_orchestrator.core.parser import parse_nmap_output
    
    try:
        targets = parse_nmap_output(input_file)
    except Exception as e:
        print(f"❌ Error parsing file: {e}")
        sys.exit(1)
    
    print(f"Found {len(targets)} target(s):")
    print()
    
    ssl_detected = False
    ssl_missing = False
    http_services = []
    
    for target, ports in targets.items():
        print(f"{target}:")
        for port in ports:
            port_num = port['port']
            service = port['service']
            service_lower = service.lower()
            
            # Check if it's an HTTP service
            is_http = 'http' in service_lower or service_lower in ('www', 'web', 'radan-http')
            
            if is_http:
                has_ssl = 'ssl' in service_lower or 'tls' in service_lower or service_lower == 'https'
                
                if has_ssl:
                    print(f"  ✅ {port_num}/{port['protocol']} - {service} (SSL detected)")
                    ssl_detected = True
                else:
                    print(f"  ⚠️  {port_num}/{port['protocol']} - {service} (NO SSL info)")
                    ssl_missing = True
                    http_services.append((target, port_num, service))
            else:
                print(f"  {port_num}/{port['protocol']} - {service}")
        print()
    
    # Summary
    print("="*70)
    print("  Summary")
    print("="*70)
    print()
    
    if ssl_missing:
        print("⚠️  Some HTTP services don't have SSL detection info")
        print()
        print("Services without SSL info:")
        for target, port, service in http_services:
            print(f"  - {target}:{port} ({service})")
        print()
        print("Recommendation:")
        print("  Regenerate input file with:")
        print(f"    nmap -sV -sC {' '.join(targets.keys())} -oN {input_file}")
        print()
        print("  Or use helper script:")
        print(f"    ./scripts/regenerate_with_ssl_detection.sh \\")
        print(f"        '{' '.join(targets.keys())}' \\")
        print(f"        {input_file}")
        return 1
    elif ssl_detected:
        print("✅ SSL detection info present in file")
        print("   File is ready for audit")
        return 0
    else:
        print("ℹ️  No HTTP services found that require SSL detection")
        return 0


if __name__ == "__main__":
    sys.exit(main())
