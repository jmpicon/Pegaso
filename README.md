<div align="center">

# Pegaso

### IA personal local, privada y autoalojada

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![GPU](https://img.shields.io/badge/GPU-NVIDIA-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://nvidia.com)

**Pegaso** combina chat local, RAG sobre tus documentos, búsqueda privada, voz offline, automatizaciones y un motor LLM local de alto rendimiento con **Ferrumox (Fox)**, un motor de inferencia escrito en Rust que exprime al máximo la GPU.

[Inicio rápido](#inicio-rápido) · [Arquitectura](#arquitectura) · [Comandos](#comandos-útiles) · [API](#api-principal)

</div>

---

## Qué es Pegaso

Pegaso es un asistente de IA "local-first" pensado para correr en tu propia máquina, sin depender de SaaS para lo esencial. El proyecto está orientado a productividad técnica, documentación personal, experimentación con agentes y operación diaria del equipo.

Servicios principales del stack:

| Componente | Función |
|---|---|
| `FastAPI` | API principal, endpoints de chat, RAG, voz, digest y operaciones |
| `Open-WebUI` | Interfaz web principal |
| `PostgreSQL` | Historial de conversaciones |
| `Qdrant` | Memoria vectorial para RAG |
| `Redis + Celery` | Cola de tareas y trabajos programados |
| `SearXNG` | Búsqueda web privada |
| `Ferrumox (Fox)` | Motor LLM local en Rust — continuous batching, PagedAttention, prefix caching |
| `Perplexity CLI` | Agente opcional por terminal con herramientas para archivos, shell y sistema |

---

## Funcionalidades

### Personas

Pegaso expone tres perfiles de uso:

- `work`: DevOps, desarrollo y ciberseguridad.
- `friend`: tono cercano, motivación y digest diario.
- `ops`: diagnóstico del sistema, energía y mantenimiento.

### Vault con RAG

Los documentos añadidos a `data/vault/` se indexan para poder consultarlos desde el chat.

- Formatos previstos: `.txt`, `.md`, `.pdf`, `.docx`
- Reindexación manual con `make index`
- Watcher dedicado para indexación incremental

### Voz offline

- `POST /voice/stt`: transcripción de audio a texto
- `GET /voice/tts`: síntesis de voz con salida WAV

### Digest diario

- `GET /daily_digest`
- comando rápido: `make digest`
- salida en `data/digests/`

### Motor LLM — Ferrumox (Fox)

Pegaso usa **Fox** como motor de inferencia, diseñado para exprimir al máximo la GPU:

- API completamente compatible con OpenAI (`/v1/chat/completions`, `/v1/models`)
- Continuous batching con preemption LIFO
- PagedAttention con copy-on-write por bloques
- Prefix caching compatible con vLLM
- Muestreo real: temperatura, top_p, top_k
- Métricas Prometheus integradas
- Motor Rust sobre llama.cpp — soporte de modelos GGUF

El servicio queda accesible en la red Docker como `fox:8080` y en el host como `http://localhost:11436/v1`.

### CLI personal con Perplexity

Pegaso también puede ejecutarse como asistente por terminal con herramientas locales:

- CLI interactiva en `scripts/pegaso_cli.py`
- agente en `src/services/perplexity_agent.py`
- herramientas de sistema en `src/tools/computer_tools.py`
- requiere `PERPLEXITY_API_KEY` para activar este modo

### Operación del sistema

Pegaso incluye endpoints y comandos para revisar salud, batería y perfiles de energía:

- `GET /health`
- `GET /health/full`
- `GET /ops/battery`
- `POST /ops/power-profile`

---

## Arquitectura

```text
Browser/Open-WebUI :3000
        |
        v
 FastAPI Pegaso :8080
   |       |       |
   |       |       +--> SearXNG :8081
   |       +----------> PostgreSQL :5432
   +------------------> Qdrant :6333
   +------------------> Redis :6379
   +------------------> Celery worker / beat / watcher
   +------------------> Fox :8080 (LLM engine)
```

Todo el entorno se orquesta con `docker-compose.mvp.yml`.

---

## Requisitos

### Software

- Linux
- Docker 24+ con Compose v2 y NVIDIA Container Toolkit
- Python 3 para scripts auxiliares
- Modelo GGUF descargado en `./models/` antes de arrancar

### Hardware

| Recurso | Mínimo orientativo | Recomendado |
|---|---|---|
| RAM | 16 GB | 32 GB |
| CPU | 4 cores | 8+ cores |
| GPU NVIDIA | 6 GB VRAM | 8–16 GB VRAM |

Fox está optimizado para GPU NVIDIA. Para CPU-only, ajusta `FOX_GPU_MEMORY_FRACTION=0` en `.env`.

---

## Inicio rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/jmpicon/Pegaso.git
cd Pegaso
```

### 2. Descargar un modelo GGUF

Coloca un modelo GGUF en `./models/`. Ejemplos recomendados:

```bash
mkdir -p models
# Llama 3.2 3B (ligero, rápido)
wget -O models/llama-3.2-3b-instruct.Q8_0.gguf \
  https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q8_0.gguf

# Mistral 7B (balance rendimiento/calidad)
# wget -O models/mistral-7b-instruct.Q6_K.gguf <url>
```

Importante: el nombre del archivo que descargues debe coincidir con `FOX_MODEL_PATH`. Si guardas el modelo como `models/mi-modelo.gguf`, en `.env` debes usar `FOX_MODEL_PATH=/models/mi-modelo.gguf`.

### 3. Configurar variables

```bash
cp .env.example .env
nano .env
```

Variables clave:

```env
SECRET_KEY=tu_clave_secreta
POSTGRES_PASSWORD=tu_password

# Fox LLM
LLM_MODEL=llama-3.2-3b-instruct
VLLM_API_BASE=http://fox:8080/v1
FOX_MODEL_PATH=/models/llama-3.2-3b-instruct.Q8_0.gguf
FOX_MAX_CONTEXT_LEN=8192
FOX_GPU_MEMORY_FRACTION=0.90
FOX_MAX_BATCH_SIZE=32
```

Variables opcionales para la CLI con Perplexity:

```env
PERPLEXITY_API_KEY=tu_clave
PERPLEXITY_MODEL=sonar-pro
```

### 4. Inicializar estructura

```bash
bash scripts/init.sh
```

### 5. Arrancar servicios

```bash
make start
```

### 6. Acceder

| Servicio | URL |
|---|---|
| UI | `http://localhost:3000` |
| Swagger | `http://localhost:8080/docs` |
| SearXNG | `http://localhost:8081` |
| Qdrant | `http://localhost:6333/dashboard` |
| Fox API | `http://localhost:11436/v1` |
| Fox health | `http://localhost:11436/health` |
| Fox metrics | `http://localhost:11436/metrics` |

---

## Instalación guiada

Si prefieres un asistente completo para preparar entorno, batería y servicio systemd:

```bash
sudo bash scripts/install.sh
```

Para instalar solo el autoarranque:

```bash
sudo bash scripts/install-service.sh
```

---

## Uso básico

### Chat

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Resume mis notas de seguridad","persona":"work","stream":false}'
```

### OpenAI-compatible API

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"pegaso","messages":[{"role":"user","content":"Hola"}]}'
```

### Indexar el vault

```bash
cp mis_notas.md data/vault/
make index
```

### Búsqueda privada

```bash
make search Q="OWASP Top 10"
```

### Voz

```bash
curl -X POST http://localhost:8080/voice/stt -F "file=@grabacion.wav"
curl "http://localhost:8080/voice/tts?text=Hola%20desde%20Pegaso" --output respuesta.wav
```

### CLI con Perplexity

Modo interactivo:

```bash
python scripts/pegaso_cli.py
```

Modo de una sola orden:

```bash
python scripts/pegaso_cli.py "organiza ~/Descargas"
python scripts/pegaso_cli.py "dame información del sistema"
```

---

## Comandos útiles

```bash
make help
make start
make stop
make restart
make fox-models        # lista modelos disponibles en Fox
make fox-health        # estado del motor Fox
make fox-metrics       # métricas Prometheus de Fox
make status
make health
make logs
make logs-api
make logs-worker
make logs-watcher
make logs-llm
make logs-fox
make digest
make backup
make index
make battery
make power-balanced
make power-perf
make power-save
make shell-api
make shell-db
make redis-cli
make qdrant-ui
make ui
make clean
```

---

## API principal

### Chat y modelos

```text
POST /chat
GET  /chat/history/{session_id}
POST /v1/chat/completions
GET  /v1/models
```

### RAG y búsqueda

```text
POST /index/vault
POST /index/file?path=...
GET  /search?q=...
```

### Voz

```text
POST /voice/stt
GET  /voice/tts?text=...
```

### Sistema y operaciones

```text
GET  /health
GET  /health/full
GET  /daily_digest
GET  /ops/battery
POST /ops/power-profile?profile=balanced
```

---

## Estructura del proyecto

```text
.
├── config/
├── docker/
├── models/        # modelos GGUF (ignorado por git)
├── scripts/
├── src/
│   ├── services/
│   └── tools/
├── data/          # ignorado por git
├── backups/       # ignorado por git
├── docker-compose.mvp.yml
├── Makefile
└── .env.example
```

---

## Seguridad y datos

- `.env`, `data/`, `backups/` y `models/` están fuera de control de versiones.
- El repositorio está pensado para trabajar con datos locales y sensibles sin subirlos a Git.
- El motor LLM es Fox, configurado mediante `FOX_MODEL_PATH`, `LLM_MODEL` y `VLLM_API_BASE` en `.env`.
- La CLI con Perplexity es opcional y necesita `PERPLEXITY_API_KEY` en tu entorno o en `.env`.
- Revisa `CONNECTORS.md` y `SECURITY.md` para ampliar conectores y recomendaciones.

---

## Estado del proyecto

Proyecto en evolución activa. Algunas piezas están ya operativas y otras siguen siendo una base funcional para iterar.

Próximas líneas de trabajo:

- autenticación multiusuario
- más integraciones externas
- mejora del pipeline de voz
- más automatización y observabilidad

---

## Licencia

MIT. Consulta el fichero `LICENSE`.
