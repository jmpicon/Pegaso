#!/bin/bash
# ============================================================
# install-nvidia-toolkit.sh
# Instala NVIDIA Container Toolkit para usar GPU en Docker
# Compatible con Ubuntu/Debian (SlimOS, Ubuntu 22.04+)
# ============================================================
set -euo pipefail

echo ""
echo "=== NVIDIA Container Toolkit Installer ==="
echo ""

# Verificar que el usuario tiene GPU NVIDIA
if ! nvidia-smi &>/dev/null; then
    echo "ERROR: nvidia-smi no encontrado. Instala los drivers NVIDIA primero."
    exit 1
fi

GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)
echo "GPU detectada: $GPU"
echo ""

# Verificar que Docker está corriendo
if ! docker info &>/dev/null; then
    echo "ERROR: Docker no está corriendo. Inicia Docker primero."
    exit 1
fi

echo "[1/4] Añadiendo repositorio NVIDIA..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

echo "[2/4] Instalando nvidia-container-toolkit..."
sudo apt-get update -qq
sudo apt-get install -y nvidia-container-toolkit

echo "[3/4] Configurando runtime NVIDIA en Docker..."
sudo nvidia-ctk runtime configure --runtime=docker

echo "[4/4] Reiniciando Docker daemon..."
sudo systemctl restart docker

echo ""
echo "=== Verificando instalación ==="
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi 2>/dev/null \
    && echo "✅ GPU disponible en Docker!" \
    || echo "⚠️  Prueba: docker run --rm --gpus all ubuntu nvidia-smi"

echo ""
echo "✅ Instalación completada. Ahora ejecuta:"
echo "   cd /home/\$USER/Documentos/Pegaso"
echo "   docker compose -f docker-compose.mvp.yml up -d vllm"
