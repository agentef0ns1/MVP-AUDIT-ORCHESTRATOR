"""
Test parser with real open_ports.txt file
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.parser import (
    parse_nmap_output,
    validate_targets,
    format_targets_summary,
    get_target_count,
    get_total_port_count
)


def test_parse_real_file():
    """Test parsing the actual open_ports.txt file"""
    input_file = Path("/home/f0ns1/RedTeam/OCSR25/PoC/open_ports.txt")
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return False
    
    print(f"📄 Parsing {input_file}")
    
    try:
        # Parse the file
        targets = parse_nmap_output(input_file)
        
        # Validate
        validate_targets(targets)
        
        # Print summary
        print("\n" + "="*60)
        print(format_targets_summary(targets))
        print("="*60)
        
        # Print statistics
        print(f"\n📊 Statistics:")
        print(f"   Total targets: {get_target_count(targets)}")
        print(f"   Total ports: {get_total_port_count(targets)}")
        
        # Print first 3 targets in detail
        print(f"\n🎯 Sample targets (first 3):")
        for i, (target, ports) in enumerate(list(targets.items())[:3], 1):
            print(f"\n   {i}. {target} ({len(ports)} port(s))")
            for port_info in ports[:5]:  # First 5 ports
                print(f"      - {port_info['port']}/{port_info['protocol']} "
                      f"({port_info.get('service', 'unknown')})")
            if len(ports) > 5:
                print(f"      ... and {len(ports) - 5} more")
        
        print(f"\n✅ Parser test successful!")
        return True
    
    except Exception as e:
        print(f"\n❌ Parser test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_parse_real_file()
    sys.exit(0 if success else 1)
