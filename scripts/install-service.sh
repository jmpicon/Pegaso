#!/bin/bash
# install-service.sh — Instala Pegaso como servicio de sistema (autoarranque)
set -e

PEGASO_DIR="/home/jmpicon/Documentos/Pegaso"
SERVICE_FILE="$PEGASO_DIR/scripts/pegaso.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "🐎 Instalando Pegaso como servicio del sistema..."

# Verificar que Docker está instalado
if ! command -v docker &>/dev/null; then
    echo "❌ Docker no está instalado. Instálalo primero."
    exit 1
fi

# Copiar unit file
sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/pegaso.service"
sudo chmod 644 "$SYSTEMD_DIR/pegaso.service"

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar el servicio para que arranque con el sistema
sudo systemctl enable pegaso.service

echo ""
echo "✅ Servicio instalado correctamente."
echo ""
echo "  Comandos disponibles:"
echo "  sudo systemctl start pegaso      # Arrancar ahora"
echo "  sudo systemctl stop pegaso       # Parar"
echo "  sudo systemctl status pegaso     # Ver estado"
echo "  sudo systemctl disable pegaso    # Desactivar autoarranque"
echo "  journalctl -u pegaso -f          # Ver logs en tiempo real"
echo ""
echo "  El sistema arrancará automáticamente en cada inicio."
