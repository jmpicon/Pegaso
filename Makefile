# ============================================================
# PEGASO — Makefile de comandos rápidos
# ============================================================
COMPOSE = docker compose -f docker-compose.mvp.yml
PROJECT_DIR = /home/jmpicon/Documentos/Pegaso

.PHONY: start stop restart logs status digest backup health index clean build help

## ── CICLO DE VIDA ──────────────────────────────────────────
start:          ## Arranca todo el sistema Pegaso
	@echo "🐎 Iniciando Pegaso..."
	$(COMPOSE) up -d --build
	@echo "✅ Pegaso activo — http://localhost:3000"

stop:           ## Para todos los contenedores
	@echo "⏹  Parando Pegaso..."
	$(COMPOSE) down
	@echo "✅ Sistema detenido."

restart:        ## Reinicia el sistema completo
	$(MAKE) stop && $(MAKE) start

rebuild:        ## Reconstruye imágenes desde cero (sin caché)
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

## ── OBSERVABILIDAD ─────────────────────────────────────────
status:         ## Estado de todos los contenedores
	$(COMPOSE) ps

health:         ## Health check de todos los servicios
	@curl -s http://localhost:8080/health/full | python3 -m json.tool

logs:           ## Logs de todos los servicios (últimas 100 líneas)
	$(COMPOSE) logs --tail=100 -f

logs-api:       ## Logs solo del API
	$(COMPOSE) logs --tail=100 -f api

logs-worker:    ## Logs del worker Celery
	$(COMPOSE) logs --tail=100 -f worker

logs-watcher:   ## Logs del Vault Watcher
	$(COMPOSE) logs --tail=100 -f watcher

logs-vllm:      ## Logs del motor LLM
	$(COMPOSE) logs --tail=100 -f vllm

## ── OPERACIONES ────────────────────────────────────────────
digest:         ## Genera el Daily Digest ahora mismo
	@echo "☀️  Generando Daily Digest..."
	@curl -s http://localhost:8080/daily_digest | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['digest'])"

backup:         ## Lanza backup manual ahora
	@echo "💾 Iniciando backup manual..."
	@bash $(PROJECT_DIR)/scripts/backup.sh

index:          ## Re-indexa todo el vault
	@echo "🔍 Re-indexando vault..."
	@curl -s -X POST http://localhost:8080/index/vault | python3 -m json.tool

search:         ## Búsqueda web: make search Q="tu consulta"
	@curl -s "http://localhost:8080/search?q=$(Q)" | python3 -m json.tool | head -50

## ── DESARROLLO ─────────────────────────────────────────────
shell-api:      ## Abre shell en el contenedor API
	$(COMPOSE) exec api bash

shell-db:       ## Abre psql en la base de datos
	$(COMPOSE) exec db psql -U pegaso -d pegaso_db

redis-cli:      ## Abre redis-cli
	$(COMPOSE) exec redis redis-cli

qdrant-ui:      ## Abre el dashboard de Qdrant en el navegador
	@xdg-open http://localhost:6333/dashboard 2>/dev/null || echo "Abre: http://localhost:6333/dashboard"

ui:             ## Abre Pegaso UI en el navegador
	@xdg-open http://localhost:3000 2>/dev/null || echo "Abre: http://localhost:3000"

## ── LIMPIEZA ────────────────────────────────────────────────
clean:          ## Elimina contenedores, redes y volúmenes anónimos
	$(COMPOSE) down -v --remove-orphans

clean-digests:  ## Limpia todos los digests generados
	@rm -f $(PROJECT_DIR)/data/digests/*.txt
	@echo "🗑  Digests eliminados."

## ── AYUDA ───────────────────────────────────────────────────
help:           ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
