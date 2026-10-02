#!/bin/bash
set -e

echo "=== Installing MVP Audit Orchestrator ==="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install package in editable mode
echo "Installing audit-orchestrator..."
pip install -e .

# Create data directory
DATA_DIR="${HOME}/.local/share/audit-orchestrator"
echo "Creating data directory: ${DATA_DIR}"
mkdir -p "${DATA_DIR}"

echo ""
echo "=== Installation complete! ==="
echo ""
echo "To activate the virtual environment, run:"
echo "  source .venv/bin/activate"
echo ""
echo "Data directory: ${DATA_DIR}"
echo ""
echo "Add to your MCP client configuration:"
echo '{'
echo '  "audit-orchestrator": {'
echo '    "command": "'$(pwd)'/.venv/bin/python",'
echo '    "args": ['
echo '      "-m", "audit_orchestrator.mcp_server",'
echo '      "--data-dir", "'${DATA_DIR}'"'
echo '    ],'
echo '    "timeout": 3600'
echo '  }'
echo '}'
