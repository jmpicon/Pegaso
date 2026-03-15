#!/usr/bin/env bash
# ============================================================
# Configura Ollama para escuchar en todas las interfaces
# Necesario para que los contenedores Docker puedan acceder
# al Ollama del host via host.docker.internal:11434
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}[Pegaso] Configurando Ollama para escuchar en 0.0.0.0:11434...${NC}"

DROPIN_DIR="/etc/systemd/system/ollama.service.d"
DROPIN_FILE="$DROPIN_DIR/pegaso-override.conf"

mkdir -p "$DROPIN_DIR"
cat > "$DROPIN_FILE" <<EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

echo -e "${GREEN}[OK] Drop-in creado: $DROPIN_FILE${NC}"

systemctl daemon-reload
systemctl restart ollama

echo -e "${GREEN}[OK] Ollama reiniciado — escuchando en 0.0.0.0:11434${NC}"

# Verificar
sleep 3
if ss -tlnp | grep -q "0.0.0.0:11434"; then
    echo -e "${GREEN}[OK] Verificado: Ollama escucha en 0.0.0.0:11434${NC}"
else
    echo -e "${YELLOW}[WARN] Puerto 11434 no visible aún — espera unos segundos e intenta 'make health'${NC}"
fi
