"""
Pegaso Core API — FastAPI
Endpoints: chat (streaming), RAG, voz STT/TTS, daily digest, health
Compatible con API OpenAI en /v1/chat/completions
"""
import os
import uuid
import json
import asyncio
from datetime import datetime
from typing import List, Optional, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.core.permissions import permissions
from src.services.rag_service import rag_service
from src.db.models import init_db, SessionLocal, Conversation

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────
app = FastAPI(
    title="Pegaso OS Core API",
    description="IA personal local — Work · Friend · Ops",
    version="2.0.0",
)


@app.on_event("startup")
async def startup():
    """Inicializar base de datos en arranque."""
    try:
        init_db()
        print("[API] Base de datos inicializada.")
    except Exception as e:
        print(f"[API] Warning DB init: {e}")


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
PERSONAS = {
    "work": (
        "Eres Pegaso Work, experto en DevOps, Ciberseguridad y Desarrollo. "
        "Respuestas concisas, técnicas y accionables. Usa Markdown cuando sea útil."
    ),
    "friend": (
        "Eres Pegaso Friend, el compañero personal de José. "
        "Tono cercano, empático y motivador. Responde en español natural."
    ),
    "ops": (
        "Eres Pegaso Ops, guardián del sistema. "
        "Monitorea, diagnostica y ejecuta tareas de mantenimiento con precisión."
    ),
}


class ChatRequest(BaseModel):
    message: str
    persona: str = "work"
    session_id: Optional[str] = None
    stream: bool = True
    history_limit: int = 10


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: str = "pegaso"
    messages: List[OpenAIMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 1024


# ─────────────────────────────────────────────
# LLM helpers
# ─────────────────────────────────────────────
def _build_messages(system_prompt: str, history: list, user_message: str, context: str) -> list:
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    if context:
        messages.append({
            "role": "system",
            "content": f"Contexto relevante del vault de José:\n{context}"
        })
    messages.append({"role": "user", "content": user_message})
    return messages


async def _llm_stream(messages: list) -> AsyncIterator[str]:
    """
    Generador de streaming desde vLLM.
    Siempre termina limpiamente — nunca propaga excepciones al caller.
    """
    vllm_url = f"{os.getenv('VLLM_API_BASE', 'http://vllm:8000/v1')}/chat/completions"
    payload = {
        "model": os.getenv("LLM_MODEL"),
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", vllm_url, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass
    except httpx.ConnectError:
        yield (
            "\n\n⚠️ **Fox no disponible.** El motor LLM no está corriendo.\n\n"
            "Verifica que hay un modelo GGUF en `./models/` y que `FOX_MODEL_PATH` en `.env` "
            "apunta al fichero correcto, luego ejecuta `make start`."
        )
    except Exception as e:
        yield f"\n\n⚠️ Error de conexión con el LLM: `{type(e).__name__}`."


async def _llm_complete(messages: list) -> str:
    """Llamada al LLM sin streaming. Devuelve texto completo."""
    vllm_url = f"{os.getenv('VLLM_API_BASE', 'http://vllm:8000/v1')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(vllm_url, json={
                "model": os.getenv("LLM_MODEL"),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            })
            return resp.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return (
            "⚠️ **Fox no está corriendo.** Verifica el modelo GGUF en `./models/` "
            "y ejecuta `make start`."
        )
    except Exception as e:
        return f"⚠️ Error conectando con el LLM: `{type(e).__name__}: {e}`"


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "alive", "version": "2.0.0", "engine": "Pegaso"}


@app.get("/health/full")
async def health_full():
    """Estado detallado de todos los servicios."""
    checks = {}
    async with httpx.AsyncClient(timeout=4.0) as client:
        # Fox
        try:
            r = await client.get(f"{os.getenv('VLLM_API_BASE', 'http://fox:8080/v1')}/models")
            checks["fox"] = {"status": "ok", "models": len(r.json().get("data", []))}
        except Exception as e:
            checks["fox"] = {"status": "error", "detail": str(e)[:80]}

        # Qdrant
        try:
            r = await client.get("http://qdrant:6333/readyz")
            checks["qdrant"] = {"status": "ok" if r.status_code == 200 else "warn"}
        except Exception as e:
            checks["qdrant"] = {"status": "error", "detail": str(e)[:80]}

        # SearXNG
        try:
            r = await client.get("http://searxng:8080/stats")
            checks["searxng"] = {"status": "ok"}
        except Exception as e:
            checks["searxng"] = {"status": "error", "detail": str(e)[:80]}

    # DB
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)[:80]}

    all_ok = all(v.get("status") == "ok" for v in checks.values())
    return {"overall": "ok" if all_ok else "degraded", "services": checks, "ts": datetime.utcnow().isoformat()}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat con Pegaso — soporta streaming SSE y memoria de conversación."""
    session_id = req.session_id or str(uuid.uuid4())
    persona = req.persona if req.persona in PERSONAS else "work"
    system_prompt = PERSONAS[persona]

    # Contexto RAG
    context_docs = rag_service.search(req.message, limit=4)
    context_text = "\n\n".join([doc.get("content", "") for doc in context_docs])

    # Historial de conversación desde PostgreSQL
    history = []
    try:
        db = SessionLocal()
        history = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.created_at.desc())
            .limit(req.history_limit)
            .all()[::-1]
        )
        db.close()
    except Exception:
        pass

    messages = _build_messages(system_prompt, history, req.message, context_text)

    if req.stream:
        async def event_generator():
            full_response = []
            try:
                async for chunk in _llm_stream(messages):
                    full_response.append(chunk)
                    yield {"data": json.dumps({"chunk": chunk, "session_id": session_id})}
            finally:
                # Guardar en historial
                try:
                    db = SessionLocal()
                    db.add(Conversation(session_id=session_id, role="user", content=req.message, persona=persona))
                    db.add(Conversation(session_id=session_id, role="assistant", content="".join(full_response), persona=persona))
                    db.commit()
                    db.close()
                except Exception:
                    pass
            yield {"data": json.dumps({"done": True, "session_id": session_id})}

        return EventSourceResponse(event_generator())
    else:
        response_text = await _llm_complete(messages)
        try:
            db = SessionLocal()
            db.add(Conversation(session_id=session_id, role="user", content=req.message, persona=persona))
            db.add(Conversation(session_id=session_id, role="assistant", content=response_text, persona=persona))
            db.commit()
            db.close()
        except Exception:
            pass
        return {"response": response_text, "session_id": session_id, "persona": persona}


@app.get("/chat/history/{session_id}")
async def get_history(session_id: str, limit: int = 50):
    """Obtiene el historial de una sesión de chat."""
    try:
        db = SessionLocal()
        messages = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.created_at)
            .limit(limit)
            .all()
        )
        db.close()
        return [
            {"role": m.role, "content": m.content, "ts": m.created_at.isoformat(), "persona": m.persona}
            for m in messages
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── OpenAI-compatible endpoint (para Open-WebUI) ───
@app.post("/v1/chat/completions")
async def openai_chat(req: OpenAIChatRequest):
    """Endpoint compatible con API OpenAI — usado por Open-WebUI."""
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Inyectar contexto RAG si el último mensaje es del usuario
    user_msgs = [m for m in req.messages if m.role == "user"]
    if user_msgs:
        last_user = user_msgs[-1].content
        context_docs = rag_service.search(last_user, limit=3)
        context = "\n".join([doc.get("content", "") for doc in context_docs])
        if context:
            messages.insert(0, {"role": "system", "content": f"Contexto del vault:\n{context}"})

    if req.stream:
        cid = f"chatcmpl-{uuid.uuid4().hex[:8]}"

        async def stream_openai():
            try:
                async for chunk in _llm_stream(messages):
                    data = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                # Señal de fin correcta
                stop_data = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(stop_data)}\n\n"
            except Exception as e:
                err_data = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": f"\n⚠️ Error: {e}"}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(err_data)}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_openai(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )
    else:
        response_text = await _llm_complete(messages)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
            "model": req.model,
        }


@app.get("/v1/models")
async def list_models():
    """Modelos disponibles (OpenAI-compat para Open-WebUI)."""
    return {
        "data": [
            {"id": "pegaso", "object": "model"},
            {"id": os.getenv("LLM_MODEL", "llama-3-8b"), "object": "model"},
        ]
    }


@app.post("/index/vault")
async def index_vault(background_tasks: BackgroundTasks):
    """Fuerza re-indexación completa del vault."""
    vault_path = os.getenv("ALLOWLIST_PATH", "/app/data/vault")
    background_tasks.add_task(rag_service.index_folder, vault_path)
    return {"status": "Indexación en segundo plano iniciada", "vault": vault_path}


@app.post("/index/file")
async def index_file(path: str, background_tasks: BackgroundTasks):
    """Indexa un archivo específico del vault."""
    if not permissions.is_path_allowed(os.path.dirname(path)):
        raise HTTPException(status_code=403, detail="Ruta no permitida")
    background_tasks.add_task(rag_service.index_file, path)
    return {"status": "ok", "file": path}


@app.get("/daily_digest")
async def trigger_daily_digest():
    """Genera el Daily Digest bajo demanda."""
    context_docs = rag_service.search("tareas pendientes objetivos proyectos", limit=5)
    context_text = "\n".join([doc.get("content", "") for doc in context_docs])

    messages = [
        {"role": "system", "content": PERSONAS["friend"]},
        {"role": "user", "content": (
            f"Genera el Daily Digest de hoy ({datetime.now().strftime('%A %d de %B')}) con:\n"
            "1. Saludo motivador\n2. Resumen de notas del vault\n3. Consejo técnico del día\n\n"
            f"Notas recientes:\n{context_text or 'Sin notas en el vault todavía.'}"
        )},
    ]
    response = await _llm_complete(messages)

    digest_path = f"/app/data/digests/digest_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    os.makedirs("/app/data/digests", exist_ok=True)
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(response)

    return {"digest": response, "saved_to": digest_path}


@app.get("/search")
async def search_internet(q: str):
    """Búsqueda web privada via SearXNG."""
    searxng_url = os.getenv("SEARXNG_URL", "http://searxng:8080")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{searxng_url}/search", params={"q": q, "format": "json"})
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"SearXNG no disponible: {e}")


@app.post("/voice/stt")
async def stt(file: UploadFile = File(...)):
    """Transcripción de voz a texto — faster-whisper."""
    from src.services.voice import transcribe_audio, WHISPER_AVAILABLE
    if not WHISPER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Faster-Whisper no disponible")
    audio_bytes = await file.read()
    text = transcribe_audio(audio_bytes)
    return {"text": text, "language": "es"}


@app.get("/voice/tts")
async def tts(text: str):
    """Síntesis de voz — espeak-ng (offline)."""
    from src.services.voice import text_to_speech
    audio = text_to_speech(text)
    if audio is None:
        raise HTTPException(status_code=503, detail="TTS no disponible — instala espeak-ng")
    return Response(content=audio, media_type="audio/wav")


# ─────────────────────────────────────────────────────────────
# OPS — Batería y gestión de energía
# ─────────────────────────────────────────────────────────────

def _read_sysfs(path: str, cast=str):
    try:
        return cast(open(path).read().strip())
    except Exception:
        return None


@app.get("/ops/battery")
async def battery_status():
    """Estado completo de batería, CPU, GPU y estimación de autonomía."""
    import subprocess
    result = {}

    # ── Batería ──────────────────────────────────────────────
    for bat in ["BAT0", "BAT1"]:
        base = f"/sys/class/power_supply/{bat}"
        if not os.path.exists(base):
            continue
        capacity = _read_sysfs(f"{base}/capacity", int)
        status   = _read_sysfs(f"{base}/status")
        e_full   = _read_sysfs(f"{base}/energy_full", int)
        e_now    = _read_sysfs(f"{base}/energy_now", int)
        p_now    = _read_sysfs(f"{base}/power_now", int)

        bat_info = {
            "name": bat,
            "status": status,
            "capacity_percent": capacity,
        }
        if e_full:
            bat_info["energy_full_wh"] = round(e_full / 1e6, 1)
        if e_now:
            bat_info["energy_now_wh"] = round(e_now / 1e6, 1)
        if p_now and p_now > 0:
            power_w = p_now / 1e6
            bat_info["power_consumption_w"] = round(power_w, 2)
            if e_now:
                hours = (e_now / 1e6) / power_w
                bat_info["estimated_hours_remaining"] = round(hours, 1)
        result["battery"] = bat_info
        break

    # ── CPU ──────────────────────────────────────────────────
    governor = _read_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    freq_khz = _read_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", int)
    result["cpu"] = {
        "model": "Intel i7-13700H",
        "governor": governor,
        "current_freq_mhz": round(freq_khz / 1000) if freq_khz else None,
    }

    # ── Platform Profile ─────────────────────────────────────
    profile = _read_sysfs("/sys/firmware/acpi/platform_profile")
    result["platform_profile"] = profile

    # ── GPU NVIDIA ───────────────────────────────────────────
    try:
        gpu_out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,power.draw,power.limit,temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if gpu_out.returncode == 0:
            parts = [p.strip() for p in gpu_out.stdout.strip().split(",")]
            result["gpu"] = {
                "name": parts[0],
                "power_draw_w": float(parts[1]),
                "power_limit_w": float(parts[2]),
                "temperature_c": int(parts[3]),
                "utilization_pct": int(parts[4]),
            }
    except Exception:
        result["gpu"] = {"status": "unavailable"}

    # ── Recomendaciones inteligentes ─────────────────────────
    recs = []
    bat = result.get("battery", {})
    hours = bat.get("estimated_hours_remaining")
    power = bat.get("power_consumption_w", 0)

    if hours is not None and hours < 7 and bat.get("status") == "Discharging":
        recs.append(f"Autonomía estimada: {hours:.1f}h (objetivo: 7h). "
                    f"Consumo actual: {power:.1f}W.")
    if governor == "powersave":
        recs.append("Governor 'powersave' activo — usa 'make power-balanced' para "
                    "más rendimiento con eficiencia similar (schedutil).")
    if profile == "low-power":
        recs.append("Platform profile 'low-power' reduce rendimiento. "
                    "Ejecuta 'make battery-setup' para config óptima.")
    gpu_power = result.get("gpu", {}).get("power_draw_w", 0)
    if gpu_power > 60 and bat.get("status") == "Discharging":
        recs.append(f"GPU consumiendo {gpu_power:.0f}W en batería. "
                    f"Si no necesitas Fox, para con 'make stop' para ahorrar ~{gpu_power:.0f}W.")
    if not recs:
        recs.append("Sistema bien optimizado para batería.")

    result["recommendations"] = recs
    result["ts"] = datetime.utcnow().isoformat()
    return result


@app.post("/ops/power-profile")
async def set_power_profile(profile: str):
    """
    Cambia el perfil de energía del sistema.
    Perfiles: performance | balanced | powersave
    Nota: requiere permisos. Configura sudo NOPASSWD para uso completo.
    """
    import subprocess
    valid = {"performance", "balanced", "powersave", "low-power"}
    if profile not in valid:
        raise HTTPException(status_code=400, detail=f"Perfil inválido. Válidos: {valid}")

    results = {}

    # CPU governor
    governor_map = {
        "performance": "performance",
        "balanced": "schedutil",
        "powersave": "powersave",
        "low-power": "powersave",
    }
    target_gov = governor_map[profile]
    gov_ok = 0
    for i in range(20):  # hasta 20 cores
        path = f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor"
        if not os.path.exists(path):
            break
        try:
            with open(path, "w") as f:
                f.write(target_gov)
            gov_ok += 1
        except PermissionError:
            results["governor"] = f"error: permisos insuficientes — ejecuta 'make battery-setup' como sudo"
            break
    else:
        results["governor"] = f"ok: {target_gov} en {gov_ok} cores"

    if "governor" not in results:
        results["governor"] = f"ok: {target_gov} en {gov_ok} cores"

    # Platform profile
    platform_map = {
        "performance": "performance",
        "balanced": "balanced",
        "powersave": "low-power",
        "low-power": "low-power",
    }
    plat_path = "/sys/firmware/acpi/platform_profile"
    try:
        with open(plat_path, "w") as f:
            f.write(platform_map[profile])
        results["platform_profile"] = f"ok: {platform_map[profile]}"
    except Exception as e:
        results["platform_profile"] = f"error: {e}"

    # NVIDIA power limit
    if profile == "powersave":
        nvidia_limit = 40
    elif profile == "balanced":
        nvidia_limit = 55
    else:
        nvidia_limit = 80

    try:
        r = subprocess.run(
            ["nvidia-smi", "-pl", str(nvidia_limit)],
            capture_output=True, text=True, timeout=5,
        )
        results["nvidia_power_limit_w"] = nvidia_limit if r.returncode == 0 else "error (necesita root)"
    except Exception:
        results["nvidia_power_limit_w"] = "unavailable"

    return {
        "profile": profile,
        "applied": results,
        "note": "Para cambios permanentes ejecuta: make battery-setup (requiere sudo)",
    }
