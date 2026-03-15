#!/bin/bash
# init.sh - Setup inicial

echo "🐎 Inicializando Pegaso..."

# Crear carpetas necesarias
mkdir -p data/vault data/pgdata data/qdrant data/cloud_sync data/digests backups config/searxng

# Asegurar permisos de ejecución
chmod +x scripts/*.sh

# Crear config de SearXNG si no existe
if [ ! -f config/searxng/settings.yml ]; then
    echo "writing default searxng settings..."
    cat <<EOF > config/searxng/settings.yml
use_default_settings: true
server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "ultrasecret"
EOF
fi

# Crear archivo de ejemplo para RAG
cat <<EOF > data/vault/tareas_pendientes.txt
TAREAS DE HOY:
1. Revisar configuración de seguridad de Pegaso.
2. Implementar cifrado en reposo para el Vault.
3. Hacer ejercicio 30 minutos.
4. Leer sobre arquitecturas multi-agente.
EOF

echo "✅ Todo listo. Ejecuta: docker compose -f docker-compose.mvp.yml up -d"
