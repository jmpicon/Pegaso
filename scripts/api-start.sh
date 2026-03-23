#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
# Pegaso API — arranque nativo en el host
# Se conecta a Fox (localhost:11436) y a Docker services (localhost:*)
# ══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Cargar .env
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Sobreescribir URLs para usar localhost (host nativo)
export VLLM_API_BASE="http://localhost:11436/v1"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
export REDIS_URL="redis://localhost:6379/0"
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost/${POSTGRES_DB}"
export ALLOWLIST_PATH="${PROJECT_DIR}/data/vault"
export LEARNING_DIR="${PROJECT_DIR}/data/vault/learning"

LOG_DIR="${PROJECT_DIR}/data/logs"
mkdir -p "$LOG_DIR"

# Matar instancia anterior
pkill -f "uvicorn src.api.main:app" 2>/dev/null && sleep 1 || true

echo "🚀 Arrancando Pegaso API en el host..."
echo "   Fox:     $VLLM_API_BASE"
echo "   Puerto:  8080"
echo "   Logs:    $LOG_DIR/api.log"

# Activar virtualenv si existe
if [ -d "$PROJECT_DIR/.venv" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

nohup python -m uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 2 \
    --log-level info \
    >> "$LOG_DIR/api.log" 2>&1 &

echo "   PID: $!"
echo "✅ API iniciada: http://localhost:8080"
