<![CDATA[<div align="center">

# 🐎 Pegaso

### Your Private, Local-First AI — No Cloud, No Limits

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![GPU](https://img.shields.io/badge/GPU-NVIDIA_RTX_4060-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://nvidia.com)

**Pegaso** is a self-hosted, privacy-first AI assistant that runs entirely on your hardware.
Chat with your documents, get daily briefings, search the web privately, and automate your workflows — all offline.

[Getting Started](#-quick-start) · [Architecture](#-architecture) · [Features](#-features) · [API Docs](#-api-reference)

---

</div>

## 🧠 What is Pegaso?

Pegaso is not just a chatbot. It's a **personal AI operating system** built on open-source components, designed for developers, security researchers, and power users who value privacy.

It runs a full AI stack locally:

| Component | Role |
|---|---|
| **vLLM + Llama-3-8B-AWQ** | Fast GPU inference (OpenAI-compatible API) |
| **Qdrant** | Vector memory — your long-term AI memory |
| **PostgreSQL** | Conversation history & metadata |
| **Celery + Redis** | Async tasks, scheduled jobs (daily digest, backups) |
| **SearXNG** | Private metasearch engine (your local Google) |
| **Open-WebUI** | Beautiful chat interface |
| **Faster-Whisper** | Local speech-to-text (offline STT) |
| **espeak-ng** | Local text-to-speech (offline TTS) |

---

## ✨ Features

### 🎭 Three AI Personas

Pegaso dynamically switches between three personas based on context:

- **Pegaso Work** — Expert in DevOps, Cybersecurity, and Development. Analyzes your files, reviews code, and generates documentation.
- **Pegaso Friend** — Warm and empathetic. Handles wellbeing, motivational messages, and your daily digest.
- **Pegaso Ops** — System guardian. Manages backups, container health, and system maintenance.

### 📚 Intelligent Vault (RAG)

Drop files into the `data/vault/` folder — Pegaso indexes them automatically:

- Supports: `.txt`, `.md`, `.pdf`, `.docx`
- **Incremental indexing** with SHA-256 deduplication (only re-indexes changed files)
- **Real-time watcher** — files indexed within 2 seconds of being added
- Ask questions grounded in your own documents

### ☀️ Automated Daily Digest

Every morning at **07:30** Pegaso generates a personalized briefing:
1. A motivational greeting
2. Summary of your recent notes and tasks
3. A daily tech/security tip

Saved automatically to `data/digests/`. Trigger manually with `make digest`.

### 🔒 Privacy by Design

- **Zero telemetry** — no data leaves your machine
- **Allowlist-based access** — Pegaso only reads folders you explicitly permit
- **Audit log** for all file access
- All models run 100% offline after initial download

### 🎙️ Voice Interface

- **STT**: Faster-Whisper `base` model (Spanish, VAD-filtered)
- **TTS**: espeak-ng (offline, no internet needed)

### 🤖 Full Automation

Scheduled via Celery Beat (no cron needed):
- `07:30` — Daily Digest generation
- `03:00` — Full system backup (DB + vectors + config)
- `04:00 Sunday` — Old backup cleanup (>30 days)
- `Every hour` — Health check of all services

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Your Machine                          │
│                                                             │
│  ┌──────────┐    ┌─────────────────────────────────────┐   │
│  │          │    │           Docker Network             │   │
│  │  Browser │───▶│  Open-WebUI :3000                   │   │
│  │          │    │      │                               │   │
│  └──────────┘    │      ▼                               │   │
│                  │  Pegaso API :8080  ◀── REST/SSE      │   │
│  ┌──────────┐    │      │                               │   │
│  │  Voice   │───▶│  ┌───┴────────────────────────┐     │   │
│  │ (mic/spk)│    │  │  Services Layer             │     │   │
│  └──────────┘    │  │  ├── RAG Service (Qdrant)   │     │   │
│                  │  │  ├── Voice (Whisper/espeak)  │     │   │
│  ┌──────────┐    │  │  └── Permissions Manager     │     │   │
│  │  Vault   │───▶│  └───┬────────────────────────┘     │   │
│  │ (files)  │    │      │                               │   │
│  └──────────┘    │  ┌───▼───┐  ┌────────┐  ┌────────┐  │   │
│                  │  │ vLLM  │  │Qdrant  │  │  PG DB │  │   │
│  GPU RTX 4060    │  │:8008  │  │:6333   │  │:5432   │  │   │
│  ┌──────────┐    │  └───────┘  └────────┘  └────────┘  │   │
│  │ VRAM 8GB │───▶│  ┌────────┐ ┌────────┐ ┌─────────┐  │   │
│  └──────────┘    │  │ Redis  │ │SearXNG │ │ Celery  │  │   │
│                  │  │:6379   │ │:8081   │ │ Beat    │  │   │
│                  │  └────────┘ └────────┘ └─────────┘  │   │
│                  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Requirements

### Hardware
| Component | Minimum | Recommended |
|---|---|---|
| GPU | NVIDIA 6GB VRAM | RTX 4060 / 3070+ |
| RAM | 16 GB | 32 GB |
| Storage | 30 GB | 50 GB SSD |
| CPU | 4 cores | 8+ cores |

> **No GPU?** Pegaso still runs without vLLM. Connect it to any OpenAI-compatible API (Ollama, LM Studio, OpenAI itself) by updating `VLLM_API_BASE` in your `.env`.

### Software
- **Docker** 24.0+ with Docker Compose v2
- **NVIDIA Drivers** (580+ recommended) + **NVIDIA Container Toolkit** (for GPU)
- Linux (Ubuntu 22.04+, Debian 12, SlimOS)

---

## 🚀 Quick Start

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/pegaso.git
cd pegaso
```

### 2. Configure

```bash
cp .env.example .env
nano .env  # Set your SECRET_KEY and optionally change the model
```

Key variables:
```env
LLM_MODEL=TheBloke/Llama-3-8B-Instruct-AWQ   # ~4GB VRAM with AWQ
SECRET_KEY=your-random-secret-here
POSTGRES_PASSWORD=your-secure-password
```

### 3. Initialize

```bash
bash scripts/init.sh
```

### 4. Install NVIDIA Container Toolkit (GPU required for vLLM)

```bash
bash scripts/install-nvidia-toolkit.sh
```

> Skip this step if you're running without GPU — vLLM won't start but everything else will work.

### 5. Launch

```bash
make start
# or: docker compose -f docker-compose.mvp.yml up -d
```

First launch downloads the AI model (~4GB). Grab a coffee ☕

### 6. Access

| Service | URL | Description |
|---|---|---|
| **Chat UI** | http://localhost:3000 | Main interface (Open-WebUI) |
| **API Docs** | http://localhost:8080/docs | Swagger — all endpoints |
| **Search** | http://localhost:8081 | Private SearXNG |
| **Vector DB** | http://localhost:6333/dashboard | Qdrant memory dashboard |
| **LLM Engine** | http://localhost:8008/v1 | OpenAI-compatible endpoint |

---

## 📖 Usage

### Chat with Pegaso

Using the API directly:

```bash
# Standard chat (streaming)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Review my latest security notes", "persona": "work", "stream": true}'

# Friend mode
curl -X POST http://localhost:8080/chat \
  -d '{"message": "I am feeling overwhelmed today", "persona": "friend"}'
```

### Feed your Vault

```bash
# Add any file — it gets indexed automatically within 2 seconds
cp my-notes.md data/vault/
cp report.pdf data/vault/
cp project-specs.docx data/vault/

# Force re-index everything
make index
# or: curl -X POST http://localhost:8080/index/vault
```

### Daily Digest

```bash
# Generate now
make digest

# Automatic: runs every morning at 07:30 via Celery Beat
# Check today's digest:
cat data/digests/digest_$(date +%Y%m%d)*.txt
```

### Voice Interface

```bash
# Speech-to-Text (upload audio file)
curl -X POST http://localhost:8080/voice/stt \
  -F "file=@recording.wav"
# Returns: {"text": "your transcribed speech", "language": "es"}

# Text-to-Speech (returns WAV audio)
curl "http://localhost:8080/voice/tts?text=Hello+from+Pegaso" --output response.wav
aplay response.wav
```

### Private Web Search

```bash
make search Q="OWASP top 10 2024"
# or: curl "http://localhost:8080/search?q=your+query"
```

---

## 🛠️ Makefile Commands

```bash
make help         # Show all commands
make start        # Start all services
make stop         # Stop all services
make restart      # Restart everything
make status       # Container status
make health       # Full health check (JSON)
make logs         # Tail all logs
make logs-api     # API logs only
make digest       # Generate daily digest now
make backup       # Manual backup
make index        # Re-index vault
make shell-api    # Shell inside API container
make shell-db     # PostgreSQL shell
make qdrant-ui    # Open Qdrant dashboard
make ui           # Open Pegaso UI in browser
make clean        # Remove containers + volumes
```

---

## 📡 API Reference

### Chat
```
POST /chat                    # Chat with streaming SSE
GET  /chat/history/{session}  # Get conversation history
POST /v1/chat/completions     # OpenAI-compatible endpoint
GET  /v1/models               # List available models
```

### Vault & Search
```
POST /index/vault             # Re-index full vault
POST /index/file?path=...     # Index specific file
GET  /search?q=...            # Web search via SearXNG
```

### Voice
```
POST /voice/stt               # Speech-to-text (upload WAV/MP3)
GET  /voice/tts?text=...      # Text-to-speech (returns WAV)
```

### System
```
GET  /health                  # Quick health check
GET  /health/full             # Detailed status of all services
GET  /daily_digest            # Generate digest on demand
```

---

## 🤝 Autostart with systemd

Make Pegaso start automatically when your computer boots:

```bash
bash scripts/install-service.sh

# Then:
sudo systemctl start pegaso
sudo systemctl status pegaso
journalctl -u pegaso -f        # Live logs
```

---

## 🔧 Configuration

### Permissions (`config/permissions.yaml`)

Control which folders Pegaso can access:

```yaml
allowlist:
  paths:
    - /app/data/vault
    - /app/data/cloud_sync    # Sync with rclone/Syncthing
  commands:
    - ls
    - cat
    - git

capabilities:
  can_write_vault: false                      # Read-only vault by default
  require_confirmation_for_destructive: true
```

### Cloud Sync (Optional)

Pegaso reads from `data/cloud_sync/`. Sync any cloud service with:

```bash
# Google Drive via rclone
rclone bisync gdrive: ./data/cloud_sync/gdrive --resync

# Syncthing, Nextcloud, etc. — just point to data/cloud_sync/
```

See [CONNECTORS.md](CONNECTORS.md) for detailed instructions.

---

## 🔐 Backup & Recovery

Automated nightly backups at 03:00 include:
- PostgreSQL full dump
- Qdrant vector snapshot
- Configuration files

```bash
# Manual backup
make backup

# Backups location
ls backups/
```

---

## 🗺️ Roadmap

- [ ] Multi-user support with authentication
- [ ] Web scraping agent (Playwright)
- [ ] Email integration (IMAP/SMTP)
- [ ] Calendar & task sync
- [ ] Image understanding (LLaVA)
- [ ] Piper TTS for higher quality voice
- [ ] Enterprise mode (Grafana + Authentik SSO)
- [ ] Mobile companion app

---

## 🤝 Contributing

PRs are welcome! Please:
1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-idea`
3. Test with Docker: `make start`
4. Submit a PR with a clear description

---

## 📄 License

MIT — do whatever you want with it. If you build something cool, let us know!

---

<div align="center">

**Built with ❤️ for people who believe AI should be private, local, and yours.**

*Running on a Slimbook with RTX 4060 — no cloud required.*

</div>
]]>
