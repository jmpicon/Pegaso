#!/bin/bash
# ============================================================
# install.sh — Instalador completo de Pegaso
# Ejecuta: sudo bash scripts/install.sh
# ============================================================
set -euo pipefail

# ── Colores ─────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✅ $*${RESET}"; }
info() { echo -e "${CYAN}  ℹ️  $*${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠️  $*${RESET}"; }
fail() { echo -e "${RED}  ❌ $*${RESET}"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}▶ $*${RESET}"; }
ask()  {
    echo -e "${YELLOW}  ? $1 [s/N]: ${RESET}\c"
    read -r answer
    [[ "$answer" =~ ^[sS]$ ]]
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

# ── Banner ───────────────────────────────────────────────────
echo -e "${BOLD}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║        🐎  PEGASO — INSTALADOR            ║"
echo "  ║   IA Personal Local · Privacy-First       ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "  Proyecto: ${CYAN}$PROJECT_DIR${RESET}"
echo -e "  Usuario:  ${CYAN}$REAL_USER${RESET}"
echo ""

# ── [0] Verificar que se ejecuta con sudo ────────────────────
step "[0/6] Verificando permisos"
if [[ $EUID -ne 0 ]]; then
    fail "Este script necesita sudo. Ejecuta: sudo bash scripts/install.sh"
fi
ok "Ejecutando como root (sudo)"

# ── [1] Prerequisitos del sistema ───────────────────────────
step "[1/6] Verificando prerequisitos"

# Docker
if ! command -v docker &>/dev/null; then
    fail "Docker no está instalado. Instálalo desde https://docs.docker.com/engine/install/"
fi
DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+')
ok "Docker $DOCKER_VER"

# Docker Compose v2
if ! docker compose version &>/dev/null; then
    fail "Docker Compose v2 no encontrado. Actualiza Docker."
fi
ok "Docker Compose v2"

# GPU
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    ok "GPU detectada: $GPU_NAME"
    HAS_GPU=true
else
    warn "No se detectó GPU NVIDIA (nvidia-smi no disponible)"
    HAS_GPU=false
fi

# TLP
if command -v tlp &>/dev/null; then
    ok "TLP instalado (gestión de energía)"
    HAS_TLP=true
else
    warn "TLP no instalado — se instalará durante la configuración de batería"
    HAS_TLP=false
fi

# Python3
if ! command -v python3 &>/dev/null; then
    fail "Python3 no encontrado. Instálalo: sudo apt install python3"
fi
ok "Python3 disponible"

# ── [2] Inicialización del proyecto ─────────────────────────
step "[2/6] Inicializando estructura del proyecto"

cd "$PROJECT_DIR"

# Crear directorios de datos
mkdir -p data/vault data/pgdata data/qdrant data/cloud_sync data/digests \
         data/redis data/open-webui backups config/searxng
ok "Directorios de datos creados"

# Permisos de scripts
chmod +x scripts/*.sh
ok "Scripts con permisos de ejecución"

# .env desde .env.example si no existe
if [[ ! -f .env ]]; then
    cp .env.example .env
    # Generar SECRET_KEY aleatoria
    NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/" .env
    warn ".env creado desde .env.example — revisa y ajusta las contraseñas en .env"
else
    ok ".env ya existe"
fi

# SearXNG config
if [[ ! -f config/searxng/settings.yml ]]; then
    SEARX_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    cat > config/searxng/settings.yml << SEARXEOF
use_default_settings: true
server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "$SEARX_SECRET"
SEARXEOF
    ok "Config SearXNG generada"
fi

# Nota de bienvenida en el vault
if [[ ! -f data/vault/bienvenida.md ]]; then
    cat > data/vault/bienvenida.md << 'VAULTEOF'
# Bienvenido a Pegaso

Soy tu asistente de IA personal. Este archivo está en tu Vault y puedo leerlo.

## Para empezar

- Añade tus notas, documentos y tareas a esta carpeta
- Soporto: .txt, .md, .pdf, .docx
- Te indexo automáticamente en menos de 2 segundos

## Mis personalidades

- **Work**: DevOps, Ciberseguridad, Desarrollo
- **Friend**: Bienestar, motivación, día a día
- **Ops**: Estado del sistema, backups, energía
VAULTEOF
    ok "Nota de bienvenida añadida al Vault"
fi

# ── [3] NVIDIA Container Toolkit ────────────────────────────
step "[3/6] NVIDIA Container Toolkit (GPU para Fox)"

if [[ "$HAS_GPU" == "true" ]]; then
    if docker info 2>/dev/null | grep -q "nvidia"; then
        ok "NVIDIA Container Toolkit ya está configurado en Docker"
    else
        if ask "¿Instalar NVIDIA Container Toolkit? (necesario para Fox con GPU)"; then
            bash "$SCRIPT_DIR/install-nvidia-toolkit.sh"
            ok "NVIDIA Container Toolkit instalado"
        else
            info "Omitido. Puedes instalarlo después con: sudo bash scripts/install-nvidia-toolkit.sh"
        fi
    fi
else
    warn "Sin GPU NVIDIA — Fox necesita GPU para rendimiento óptimo. Ajusta FOX_GPU_MEMORY_FRACTION=0 en .env para CPU."
fi

# ── [4] Optimización de batería ──────────────────────────────
step "[4/6] Optimización de batería (TLP)"

BAT_STATUS=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo "unknown")
if [[ "$BAT_STATUS" != "unknown" ]]; then
    if ask "¿Configurar TLP para 7h de batería con rendimiento optimizado?"; then
        # Instalar TLP si no está
        if [[ "$HAS_TLP" == "false" ]]; then
            apt-get install -y tlp tlp-rdw -qq
            ok "TLP instalado"
        fi
        bash "$SCRIPT_DIR/battery-setup.sh"
        ok "Batería optimizada"
    else
        info "Omitido. Puedes hacerlo después con: make battery-setup"
    fi
else
    info "No se detectó batería — omitiendo optimización de energía"
fi

# ── [5] Servicio systemd (autoarranque) ──────────────────────
step "[5/6] Servicio systemd (autoarranque con el sistema)"

SERVICE_FILE="/etc/systemd/system/pegaso.service"
if [[ -f "$SERVICE_FILE" ]]; then
    ok "Servicio pegaso.service ya instalado"
else
    if ask "¿Instalar Pegaso como servicio del sistema? (arrancará solo al encender el PC)"; then
        # Ajustar usuario en el service file
        sed "s|User=jmpicon|User=$REAL_USER|g; \
             s|Group=jmpicon|Group=$REAL_USER|g; \
             s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g; \
             s|ExecStart=.*up.*|ExecStart=/usr/bin/docker compose -f $PROJECT_DIR/docker-compose.mvp.yml up -d --remove-orphans|g; \
             s|ExecStop=.*|ExecStop=/usr/bin/docker compose -f $PROJECT_DIR/docker-compose.mvp.yml down|g; \
             s|EnvironmentFile=.*|EnvironmentFile=$PROJECT_DIR/.env|g" \
            "$SCRIPT_DIR/pegaso.service" > "$SERVICE_FILE"
        chmod 644 "$SERVICE_FILE"
        systemctl daemon-reload
        systemctl enable pegaso.service
        ok "Servicio instalado y habilitado (arrancará con el sistema)"
        info "Comandos: sudo systemctl start|stop|status pegaso"
    else
        info "Omitido. Puedes instalarlo después con: make install-service"
    fi
fi

# ── [6] Primer arranque ──────────────────────────────────────
step "[6/6] Primer arranque de Pegaso"

if ask "¿Arrancar Pegaso ahora?"; then
    # Ejecutar como el usuario real, no como root
    sudo -u "$REAL_USER" bash -c "cd '$PROJECT_DIR' && docker compose -f docker-compose.mvp.yml up -d --build"
    echo ""
    ok "Pegaso arrancando... (puede tardar 1-2 min la primera vez)"
    info "Espera a que todos los servicios estén healthy y accede a:"
    echo ""
    echo -e "    ${BOLD}http://localhost:3000${RESET}  → Chat (Open-WebUI)"
    echo -e "    ${BOLD}http://localhost:8080/docs${RESET}  → API Swagger"
    echo -e "    ${BOLD}http://localhost:8081${RESET}  → Búsqueda privada"
else
    info "Arrancar más tarde con: make start"
fi

# ── Resumen final ────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║      ✅  Instalación completada           ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "  ${BOLD}Comandos esenciales:${RESET}"
echo -e "  ${CYAN}make start${RESET}        → Arrancar Pegaso (pon modelo GGUF en ./models/ primero)"
echo -e "  ${CYAN}make status${RESET}       → Ver contenedores"
echo -e "  ${CYAN}make health${RESET}       → Health check completo"
echo -e "  ${CYAN}make battery${RESET}      → Estado de batería"
echo -e "  ${CYAN}make digest${RESET}       → Daily Digest ahora"
echo -e "  ${CYAN}make help${RESET}         → Todos los comandos"
echo ""
