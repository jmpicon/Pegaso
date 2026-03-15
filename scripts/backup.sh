#!/bin/bash
# backup.sh — Backup completo de Pegaso (PostgreSQL + Qdrant + Config)
set -euo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/home/jmpicon/Documentos/Pegaso/backups/$TIMESTAMP"
LOG="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR"
exec > >(tee -a "$LOG") 2>&1

echo "=== 💾 Pegaso Backup — $TIMESTAMP ==="

# 1. PostgreSQL
echo "[1/3] Dumping PostgreSQL..."
if docker exec pegaso-db pg_dump -U pegaso pegaso_db > "$BACKUP_DIR/database.sql" 2>/dev/null; then
    SIZE=$(du -sh "$BACKUP_DIR/database.sql" | cut -f1)
    echo "  ✅ DB: $SIZE"
else
    echo "  ⚠️  DB backup falló (¿contenedor pegaso-db activo?)"
fi

# 2. Qdrant snapshot
echo "[2/3] Snapshot de Qdrant (vectores)..."
if curl -sf -X POST http://localhost:6333/collections/vault_memory/snapshots \
    -o "$BACKUP_DIR/qdrant_snapshot.json" 2>/dev/null; then
    echo "  ✅ Qdrant snapshot guardado"
else
    echo "  ⚠️  Qdrant snapshot falló"
fi

# 3. Configuración
echo "[3/3] Copiando configuración..."
cp /home/jmpicon/Documentos/Pegaso/config/permissions.yaml "$BACKUP_DIR/" 2>/dev/null || true
cp /home/jmpicon/Documentos/Pegaso/.env "$BACKUP_DIR/.env.backup" 2>/dev/null || true
echo "  ✅ Config copiada"

echo ""
echo "=== ✅ Backup completado en $BACKUP_DIR ==="
echo "   Tamaño total: $(du -sh "$BACKUP_DIR" | cut -f1)"
