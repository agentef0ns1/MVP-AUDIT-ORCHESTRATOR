#!/bin/bash
#
# Script para configurar el puerto del servidor Kali MCP
# Uso: ./scripts/configure-kali-port.sh [puerto] [host]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Configurador de Puerto Kali MCP - Audit Orchestrator   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Default values
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="5001"

# Parse arguments
HOST="${2:-$DEFAULT_HOST}"
PORT="${1:-$DEFAULT_PORT}"

# Construct URL
KALI_URL="http://${HOST}:${PORT}"

echo -e "${YELLOW}Configuración actual:${NC}"
if [ -n "$KALI_SERVER_URL" ]; then
    echo -e "  KALI_SERVER_URL: ${GREEN}${KALI_SERVER_URL}${NC}"
else
    echo -e "  KALI_SERVER_URL: ${RED}no configurada (usando default: http://127.0.0.1:5001)${NC}"
fi
echo ""

echo -e "${YELLOW}Nueva configuración:${NC}"
echo -e "  Host: ${GREEN}${HOST}${NC}"
echo -e "  Puerto: ${GREEN}${PORT}${NC}"
echo -e "  URL completa: ${GREEN}${KALI_URL}${NC}"
echo ""

# Test connection
echo -e "${YELLOW}Probando conexión...${NC}"
if curl -s -m 5 "${KALI_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Servidor Kali MCP responde correctamente${NC}"
else
    echo -e "${RED}⚠️  Advertencia: No se pudo conectar al servidor${NC}"
    echo -e "${YELLOW}   Verifica que el servidor Kali MCP esté corriendo en ${KALI_URL}${NC}"
fi
echo ""

# Ask for confirmation
read -p "¿Deseas aplicar esta configuración? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Configuración cancelada${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Aplicando configuración...${NC}"

# Export for current session
export KALI_SERVER_URL="${KALI_URL}"
echo -e "${GREEN}✅ Variable exportada para la sesión actual${NC}"

# Ask if permanent
echo ""
read -p "¿Deseas hacer esta configuración permanente? (se añadirá a ~/.bashrc) [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    BASHRC="$HOME/.bashrc"
    
    # Remove old configuration if exists
    sed -i '/export KALI_SERVER_URL=/d' "$BASHRC" 2>/dev/null || true
    
    # Add new configuration
    echo "" >> "$BASHRC"
    echo "# Audit Orchestrator - Kali MCP Server URL" >> "$BASHRC"
    echo "export KALI_SERVER_URL=\"${KALI_URL}\"" >> "$BASHRC"
    
    echo -e "${GREEN}✅ Configuración añadida a ${BASHRC}${NC}"
    echo -e "${YELLOW}   Ejecuta 'source ~/.bashrc' o abre una nueva terminal para aplicar${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Configuración completada${NC}"
echo ""
echo -e "Para verificar:"
echo -e "  ${YELLOW}echo \$KALI_SERVER_URL${NC}"
echo ""
echo -e "Para probar la conexión:"
echo -e "  ${YELLOW}curl ${KALI_URL}/health${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
