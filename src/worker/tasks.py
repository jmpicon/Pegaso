"""
Tareas Celery de Pegaso con schedule automático via RedBeat.
"""
import os
import asyncio
import time
import glob
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from src.services.rag_service import rag_service

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery("pegaso_tasks", broker=REDIS_URL, backend=REDIS_URL)

# Configuración de Celery Beat (RedBeat)
app.conf.update(
    timezone="Europe/Madrid",
    enable_utc=False,
    redbeat_redis_url=REDIS_URL,
    beat_schedule={
        # Daily Digest cada mañana a las 7:30
        "daily-digest-morning": {
            "task": "src.worker.tasks.daily_summary_task",
            "schedule": crontab(hour=7, minute=30),
            "args": ("José",),
        },
        # Backup nocturno a las 3:00 AM
        "nightly-backup": {
            "task": "src.worker.tasks.backup_task",
            "schedule": crontab(hour=3, minute=0),
        },
        # Limpieza de backups viejos (>30 días) cada domingo
        "weekly-cleanup": {
            "task": "src.worker.tasks.cleanup_old_backups_task",
            "schedule": crontab(hour=4, minute=0, day_of_week=0),
        },
        # Health check cada hora
        "hourly-health": {
            "task": "src.worker.tasks.health_check_task",
            "schedule": crontab(minute=0),
        },
    },
    task_routes={
        "src.worker.tasks.index_vault_task": {"queue": "indexing"},
        "src.worker.tasks.daily_summary_task": {"queue": "default"},
        "src.worker.tasks.backup_task": {"queue": "default"},
    },
)


@app.task(name="src.worker.tasks.index_vault_task", queue="indexing")
def index_vault_task(folder_path: str):
    """Indexa una carpeta completa del vault."""
    print(f"[Task] Indexando carpeta: {folder_path}")
    return rag_service.index_folder(folder_path)


@app.task(name="src.worker.tasks.index_file_task", queue="indexing")
def index_file_task(file_path: str):
    """Indexa un archivo específico del vault."""
    return rag_service.index_file(file_path)


@app.task(name="src.worker.tasks.daily_summary_task")
def daily_summary_task(user_name: str = "José"):
    """
    Daily Digest: saludo motivador + resumen de notas + consejo técnico.
    Se ejecuta automáticamente a las 7:30 AM vía Celery Beat.
    """
    import httpx

    context_docs = rag_service.search("tareas pendientes objetivos proyectos", limit=5)
    context_text = "\n".join([doc.get("content", "") for doc in context_docs])

    prompt = f"""Eres Pegaso, el asistente IA personal de {user_name}. Hoy es {datetime.now().strftime('%A %d de %B de %Y')}.

MISIÓN: Genera el Daily Digest matutino siguiendo esta estructura exacta:

---
☀️ **SALUDO** (2-3 líneas motivadoras y personales, menciona el día)

📋 **RESUMEN DE NOTAS** (puntos clave de las notas del vault, máx. 5 bullets)

🔐 **CONSEJO DEL DÍA** (un consejo técnico de seguridad o desarrollo, práctico y breve)
---

NOTAS DEL VAULT:
{context_text if context_text else "Sin notas recientes en el vault."}

Genera el digest ahora:"""

    try:
        vllm_url = f"{os.getenv('VLLM_API_BASE', 'http://vllm:8000/v1')}/chat/completions"
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                vllm_url,
                json={
                    "model": os.getenv("LLM_MODEL"),
                    "messages": [
                        {"role": "system", "content": "Eres Pegaso, un asistente IA local, cercano y profesional."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
            )
            content = response.json()["choices"][0]["message"]["content"]

        digest_path = f"/app/data/digests/digest_{datetime.now().strftime('%Y%m%d')}.txt"
        os.makedirs("/app/data/digests", exist_ok=True)
        with open(digest_path, "w", encoding="utf-8") as f:
            f.write(f"# Daily Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(content)

        print(f"[Task] Daily Digest guardado en {digest_path}")
        return {"status": "ok", "path": digest_path}

    except Exception as e:
        print(f"[Task] Error generando digest: {e}")
        return {"error": str(e)}


@app.task(name="src.worker.tasks.backup_task")
def backup_task():
    """Realiza backup completo: Postgres + Qdrant snapshot + config."""
    import subprocess
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"/app/backups/{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)

    results = {}

    # 1. Dump PostgreSQL
    try:
        result = subprocess.run(
            ["pg_dump", "-h", "db", "-U", os.getenv("POSTGRES_USER", "pegaso"),
             os.getenv("POSTGRES_DB", "pegaso_db")],
            capture_output=True, timeout=60,
            env={**os.environ, "PGPASSWORD": os.getenv("POSTGRES_PASSWORD", "")},
        )
        db_path = f"{backup_dir}/database.sql"
        with open(db_path, "wb") as f:
            f.write(result.stdout)
        results["database"] = "ok"
    except Exception as e:
        results["database"] = f"error: {e}"

    # 2. Snapshot Qdrant
    try:
        import httpx
        resp = httpx.post(
            f"http://qdrant:6333/collections/vault_memory/snapshots",
            timeout=30,
        )
        snap_path = f"{backup_dir}/qdrant_snapshot.json"
        with open(snap_path, "w") as f:
            f.write(resp.text)
        results["qdrant"] = "ok"
    except Exception as e:
        results["qdrant"] = f"error: {e}"

    # 3. Config
    import shutil
    try:
        shutil.copy("/app/config/permissions.yaml", f"{backup_dir}/permissions.yaml")
        results["config"] = "ok"
    except Exception as e:
        results["config"] = f"error: {e}"

    print(f"[Task] Backup completado en {backup_dir}: {results}")
    return {"status": "ok", "path": backup_dir, "results": results}


@app.task(name="src.worker.tasks.cleanup_old_backups_task")
def cleanup_old_backups_task(max_age_days: int = 30):
    """Elimina backups con más de max_age_days días."""
    import shutil
    backup_base = "/app/backups"
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for entry in os.scandir(backup_base):
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry.path, ignore_errors=True)
            removed += 1
    print(f"[Task] Limpiados {removed} backups antiguos (>{max_age_days} días)")
    return {"removed": removed}


@app.task(name="src.worker.tasks.health_check_task")
def health_check_task():
    """Comprueba la salud de todos los servicios internos."""
    import httpx
    services = {
        "vllm": f"{os.getenv('VLLM_API_BASE', 'http://vllm:8000/v1')}/models",
        "qdrant": "http://qdrant:6333/readyz",
        "api": "http://api:8080/health",
    }
    results = {}
    with httpx.Client(timeout=5.0) as client:
        for name, url in services.items():
            try:
                r = client.get(url)
                results[name] = "ok" if r.status_code < 400 else f"http_{r.status_code}"
            except Exception as e:
                results[name] = f"error: {str(e)[:50]}"

    print(f"[Task] Health check: {results}")
    return results
