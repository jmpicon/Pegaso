<div align="center">

# Pegaso

### IA personal local, privada y autoalojada

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![GPU](https://img.shields.io/badge/GPU-Optional-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://nvidia.com)

**Pegaso** combina chat local, RAG sobre tus documentos, búsqueda privada, voz offline, automatizaciones y observabilidad del sistema en un único stack Docker.

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
| `vLLM` | Inferencia local compatible con OpenAI, opcional con GPU |

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
   +------------------> vLLM :8008 (opcional, perfil gpu)
```

Todo el entorno se orquesta con `docker-compose.mvp.yml`.

---

## Requisitos

### Software

- Linux
- Docker 24+ con Compose v2
- Python 3 para scripts auxiliares
- Drivers NVIDIA + NVIDIA Container Toolkit si quieres usar `vLLM`

### Hardware

| Recurso | Mínimo orientativo | Recomendado |
|---|---|---|
| RAM | 16 GB | 32 GB |
| CPU | 4 cores | 8+ cores |
| GPU | opcional | NVIDIA con 6-8 GB VRAM o más |

Si no tienes GPU, Pegaso puede seguir funcionando y también puedes apuntarlo a un backend OpenAI-compatible externo cambiando `VLLM_API_BASE` en `.env`.

---

## Inicio rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/jmpicon/Pegaso.git
cd Pegaso
```

### 2. Configurar variables

```bash
cp .env.example .env
nano .env
```

Variables importantes:

```env
SECRET_KEY=tu_clave_secreta
POSTGRES_PASSWORD=tu_password
LLM_MODEL=TheBloke/Llama-3-8B-Instruct-AWQ
VLLM_API_BASE=http://vllm:8000/v1
```

### 3. Inicializar estructura

```bash
bash scripts/init.sh
```

### 4. Arrancar

Modo estándar, sin `vLLM` por GPU:

```bash
make start
```

Modo con GPU y `vLLM`:

```bash
bash scripts/install-nvidia-toolkit.sh
make start-gpu
```

### 5. Acceder

| Servicio | URL |
|---|---|
| UI | `http://localhost:3000` |
| Swagger | `http://localhost:8080/docs` |
| SearXNG | `http://localhost:8081` |
| Qdrant | `http://localhost:6333/dashboard` |
| vLLM | `http://localhost:8008/v1` |

---

## Instalación guiada

Si prefieres un asistente completo para preparar entorno, batería, toolkit NVIDIA y servicio systemd:

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

---

## Comandos útiles

```bash
make help
make start
make start-gpu
make stop
make restart
make status
make health
make logs
make logs-api
make logs-worker
make logs-watcher
make logs-vllm
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
├── scripts/
├── src/
├── data/          # ignorado por git
├── backups/       # ignorado por git
├── docker-compose.mvp.yml
├── Makefile
└── .env.example
```

---

## Seguridad y datos

- `.env`, `data/` y `backups/` están fuera de control de versiones.
- El repositorio está pensado para trabajar con datos locales y sensibles sin subirlos a Git.
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
