#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
# Fox (Ferrumox) — arranque nativo en el host
# Corre en el host directamente (acceso a glibc 2.39 y GPU)
# La API Docker se conecta vía 172.17.0.1:11436 o host.docker.internal
# ══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Cargar variables de entorno ──────────────────────────────
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# ── Configuración por defecto ────────────────────────────────
FOX_BINARY="${PROJECT_DIR}/fox-binary"
FOX_MODEL_PATH="${FOX_MODEL_PATH:-/home/jmpicon/.lmstudio/models/lmstudio-community/DeepSeek-R1-Distill-Qwen-7B-GGUF/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf}"
FOX_PORT="${FOX_PORT:-11436}"
FOX_MAX_CONTEXT_LEN="${FOX_MAX_CONTEXT_LEN:-16384}"
FOX_MAX_BATCH_SIZE="${FOX_MAX_BATCH_SIZE:-32}"
FOX_LOG_DIR="${PROJECT_DIR}/data/logs"

mkdir -p "$FOX_LOG_DIR"

# ── Verificaciones ────────────────────────────────────────────
if [ ! -f "$FOX_BINARY" ]; then
    echo "❌ Fox binary no encontrado en $FOX_BINARY"
    echo "   Ejecuta: make fox-build"
    exit 1
fi

if [ ! -f "$FOX_MODEL_PATH" ]; then
    echo "❌ Modelo GGUF no encontrado: $FOX_MODEL_PATH"
    echo "   Ajusta FOX_MODEL_PATH en .env"
    echo ""
    echo "   Modelos disponibles:"
    find /home/jmpicon -name "*.gguf" 2>/dev/null | head -5 | sed 's/^/     /'
    exit 1
fi

# ── Matar instancia anterior si existe ───────────────────────
if pgrep -f "fox-binary serve" > /dev/null 2>&1; then
    echo "⏹  Parando Fox anterior..."
    pkill -f "fox-binary serve" || true
    sleep 1
fi

echo "🦊 Arrancando Fox (Ferrumox) en el host..."
echo "   Modelo:  $(basename "$FOX_MODEL_PATH")"
echo "   Puerto:  $FOX_PORT"
echo "   Contexto: ${FOX_MAX_CONTEXT_LEN} tokens"
echo "   API:     http://localhost:${FOX_PORT}/v1"
echo "   Logs:    $FOX_LOG_DIR/fox.log"
echo ""

# ── Detectar GPU NVIDIA ───────────────────────────────────────
if nvidia-smi &>/dev/null; then
    echo "   GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
    GPU_OPTS=""
else
    echo "   GPU: no detectada, usando CPU"
    GPU_OPTS=""
fi

# ── Arrancar Fox en background ────────────────────────────────
FOX_MODEL_PATH="$FOX_MODEL_PATH" \
FOX_PORT="$FOX_PORT" \
FOX_MAX_CONTEXT_LEN="$FOX_MAX_CONTEXT_LEN" \
FOX_MAX_BATCH_SIZE="$FOX_MAX_BATCH_SIZE" \
RUST_LOG="${RUST_LOG:-ferrumox=info}" \
    nohup "$FOX_BINARY" serve \
    >> "$FOX_LOG_DIR/fox.log" 2>&1 &

FOX_PID=$!
echo "   PID: $FOX_PID"

# ── Esperar a que Fox esté listo ──────────────────────────────
echo ""
echo -n "   Esperando a Fox"
for i in $(seq 1 60); do
    sleep 1
    if curl -sf "http://localhost:${FOX_PORT}/v1/models" >/dev/null 2>&1; then
        echo ""
        echo "✅ Fox listo en http://localhost:${FOX_PORT}/v1"
        echo ""
        curl -s "http://localhost:${FOX_PORT}/v1/models" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('data', []):
    print(f'   Modelo: {m[\"id\"]}')
" 2>/dev/null || true
        exit 0
    fi
    echo -n "."
done

echo ""
echo "⚠️  Fox tardó más de 60s. Revisa logs: tail -f $FOX_LOG_DIR/fox.log"
