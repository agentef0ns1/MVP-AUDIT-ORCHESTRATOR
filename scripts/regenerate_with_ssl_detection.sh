#!/bin/bash
#
# Regenerate nmap output with SSL detection
# This ensures ssl-cert and other SSL scripts are included
#

if [ $# -lt 2 ]; then
    echo "Usage: $0 <targets> <output_file>"
    echo ""
    echo "Examples:"
    echo "  $0 '10.19.220.23' open_ports.txt"
    echo "  $0 '10.19.220.0/24' open_ports.txt"
    echo "  $0 targets.txt open_ports.txt"
    exit 1
fi

TARGETS="$1"
OUTPUT="$2"

echo "=================================================================="
echo "  Regenerating nmap output with SSL detection"
echo "=================================================================="
echo ""
echo "Targets: $TARGETS"
echo "Output:  $OUTPUT"
echo ""

# Check if targets is a file
if [ -f "$TARGETS" ]; then
    echo "Reading targets from file: $TARGETS"
    TARGET_ARG="-iL $TARGETS"
else
    echo "Scanning target(s): $TARGETS"
    TARGET_ARG="$TARGETS"
fi

echo ""
echo "Running nmap with:"
echo "  -sV : Version detection (shows ssl/http)"
echo "  -sC : Default scripts (includes ssl-cert, ssl-date, etc.)"
echo "  -p- : All ports (or specify: -p 22,80,443,8088)"
echo ""
echo "This will take a while..."
echo ""

# Run nmap with version detection and scripts
nmap -sV -sC $TARGET_ARG -oN "$OUTPUT"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=================================================================="
    echo "  ✅ Nmap scan complete"
    echo "=================================================================="
    echo ""
    echo "Output saved to: $OUTPUT"
    echo ""
    echo "Sample of output:"
    head -30 "$OUTPUT"
    echo ""
    echo "Now you can run:"
    echo "  audit_start_and_run(base_path='...', input_file='$(basename $OUTPUT)')"
else
    echo ""
    echo "=================================================================="
    echo "  ❌ Nmap scan failed (exit code: $EXIT_CODE)"
    echo "=================================================================="
    exit $EXIT_CODE
fi
