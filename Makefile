# ============================================================
# PEGASO — Makefile de comandos rápidos
# ============================================================
COMPOSE = docker compose -f docker-compose.mvp.yml
PROJECT_DIR = /home/jmpicon/Documentos/Pegaso

.PHONY: install install-service start stop restart logs status digest backup health index clean build help battery power-balanced power-perf power-save battery-setup fox-models fox-health fox-metrics tux tux-ops tux-friend resources processes system

## ── INSTALACIÓN ────────────────────────────────────────────
install:        ## Instalación completa guiada (NVIDIA + batería + systemd + arranque)
	@sudo bash $(PROJECT_DIR)/scripts/install.sh

install-service: ## Instala solo el servicio systemd de autoarranque
	@sudo bash $(PROJECT_DIR)/scripts/install-service.sh

## ── CICLO DE VIDA ──────────────────────────────────────────
start:          ## Arranca Pegaso (requiere modelo GGUF en ./models/)
	@echo "🐎 Iniciando Pegaso..."
	$(COMPOSE) up -d --build
	@echo "✅ Pegaso activo — http://localhost:3000"

stop:           ## Para todos los contenedores
	@echo "⏹  Parando Pegaso..."
	$(COMPOSE) down
	@echo "✅ Sistema detenido."

restart:        ## Reinicia el sistema completo
	$(MAKE) stop && $(MAKE) start

fox-models:     ## Lista modelos disponibles en Fox
	@curl -sf http://localhost:11436/v1/models | python3 -m json.tool

fox-health:     ## Estado del motor Fox (métricas de caché y rendimiento)
	@curl -sf http://localhost:11436/health | python3 -m json.tool

fox-metrics:    ## Métricas Prometheus de Fox (throughput, latencia, caché)
	@curl -sf http://localhost:11436/metrics

logs-llm:       ## Logs del motor LLM (Fox)
	$(COMPOSE) logs --tail=100 -f fox

rebuild:        ## Reconstruye imágenes desde cero (sin caché)
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

## ── BATERÍA ─────────────────────────────────────────────────
battery:        ## Estado de batería y consumo en tiempo real
	@curl -s http://localhost:8080/ops/battery | python3 -m json.tool

power-balanced: ## Perfil BALANCED: rendimiento + eficiencia (recomendado en batería)
	@curl -s -X POST "http://localhost:8080/ops/power-profile?profile=balanced" | python3 -m json.tool

power-perf:     ## Perfil PERFORMANCE: máximo rendimiento (enchufado)
	@curl -s -X POST "http://localhost:8080/ops/power-profile?profile=performance" | python3 -m json.tool

power-save:     ## Perfil SAVE: máximo ahorro (batería crítica)
	@curl -s -X POST "http://localhost:8080/ops/power-profile?profile=powersave" | python3 -m json.tool

battery-setup:  ## Instala config TLP optimizada para 7h de batería (requiere sudo)
	@sudo bash $(PROJECT_DIR)/scripts/battery-setup.sh

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

logs-fox:       ## Logs del motor LLM (Fox)
	$(COMPOSE) logs --tail=100 -f fox

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

## ── PEGASO TUX — Asistente pingüino ────────────────────────
tux:            ## 🐧 Inicia Pegaso Tux (asistente pingüino interactivo)
	@python3 $(PROJECT_DIR)/scripts/tux.py

tux-ops:        ## 🐧 Tux en modo Ops (sistema y hardware)
	@python3 $(PROJECT_DIR)/scripts/tux.py --persona ops

tux-friend:     ## 🐧 Tux en modo Friend (personal y motivación)
	@python3 $(PROJECT_DIR)/scripts/tux.py --persona friend

tux-status:     ## 🐧 Estado del sistema (batería, CPU, RAM, GPU)
	@python3 $(PROJECT_DIR)/scripts/tux.py --status

## ── RECURSOS Y SISTEMA ─────────────────────────────────────
resources:      ## Recursos del sistema en tiempo real (CPU, RAM, disco)
	@curl -s http://localhost:8080/ops/resources | python3 -m json.tool

processes:      ## Lista procesos ordenados por CPU
	@curl -s "http://localhost:8080/ops/processes?sort_by=cpu" | python3 -m json.tool

system:         ## Análisis completo del sistema con IA
	@curl -s http://localhost:8080/ops/system | python3 -c "import sys,json; d=json.load(sys.stdin); print('=== ANÁLISIS IA ===\n'); print(d.get('ai_analysis','N/A'))"

## ── AYUDA ───────────────────────────────────────────────────
help:           ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
