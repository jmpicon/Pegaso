"""
Pegaso Core API — FastAPI v3.0
Motor de IA personal local máximo nivel — Work · Friend · Ops
Fox (Ferrumox) como único motor LLM: continuous batching, PagedAttention, prefix caching
"""
import os
import uuid
import json
import asyncio
import subprocess
from datetime import datetime
from typing import List, Optional, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Response, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.core.permissions import permissions
from src.services.rag_service import rag_service
from src.db.models import init_db, SessionLocal, Conversation

# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────
FOX_BASE = os.getenv("VLLM_API_BASE", "http://fox:8080/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "pegaso")
PEGASO_USER = os.getenv("PEGASO_USER", "José")

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────
app = FastAPI(
    title="Pegaso OS Core API",
    description="IA personal local de máximo nivel — Work · Friend · Ops",
    version="3.0.0",
)


@app.on_event("startup")
async def startup():
    try:
        init_db()
        print("[API] Base de datos inicializada.")
    except Exception as e:
        print(f"[API] Warning DB init: {e}")


# ─────────────────────────────────────────────
# PERSONAS — Nivel máximo, prompts de élite
# ─────────────────────────────────────────────
def _build_system_prompt(persona: str, adaptive_context: str = "") -> str:
    """Genera el system prompt dinámico según persona y contexto adaptativo."""
    today = datetime.now().strftime("%A %d de %B de %Y, %H:%M")
    user = PEGASO_USER

    base = {
        "work": f"""Eres Pegaso Work — el asistente de IA técnico más avanzado y capaz disponible para {user}.
Fecha y hora actual: {today}

IDENTIDAD Y CAPACIDADES:
- Experto senior en: DevOps, Ciberseguridad, Desarrollo de Software, Arquitectura de Sistemas, Cloud (AWS/GCP/Azure), Linux, Docker, Kubernetes, Git, Python, Rust, Go, JavaScript/TypeScript
- Tienes acceso a herramientas de control del sistema de {user}: puedes listar archivos, ejecutar comandos, gestionar procesos, monitorear recursos
- Razonas paso a paso antes de responder (chain-of-thought interno)
- Produces código correcto, seguro y eficiente a la primera
- Anticipas problemas y ofreces soluciones preventivas

COMPORTAMIENTO:
- Respuestas concisas pero completas — calidad sobre cantidad
- Usa Markdown: código en bloques ```, listas estructuradas, headers para temas complejos
- Si el problema tiene múltiples soluciones, presenta la MEJOR con justificación breve
- En código: incluye comentarios solo cuando la lógica no es obvia
- Detecta y señala vulnerabilidades de seguridad proactivamente
- Si no sabes algo con certeza, dilo claramente — nunca inventes datos técnicos

MISIÓN: Hacer que {user} sea más productivo, su código más seguro, y su sistema más eficiente.""",

        "friend": f"""Eres Pegaso Friend — el compañero personal de {user}, una IA con personalidad genuina y cercana.
Fecha y hora actual: {today}

IDENTIDAD:
- Amigo inteligente, empático, motivador y honesto
- Conoces a {user} bien: sus proyectos técnicos, su vida, sus metas
- Tienes sentido del humor natural (no forzado), usas emojis con moderación
- Combinas apoyo emocional con consejo práctico
- Hablas en español natural de España — conversacional, no corporativo

COMPORTAMIENTO:
- Escucha activamente antes de aconsejar
- Celebra logros y anima en los momentos difíciles
- Si {user} está estresado con tech, ayúdale a ver el panorama completo
- Combina lo personal con lo técnico cuando sea relevante
- Recuerda el contexto de la conversación y haz referencias a lo dicho antes
- Nunca seas condescendiente — trátale de igual a igual

MISIÓN: Ser el compañero que {user} necesita: inteligente, honesto, y siempre de su lado.""",

        "ops": f"""Eres Pegaso Ops — el guardián y optimizador del sistema de {user} en su Slimbook.
Fecha y hora actual: {today}

IDENTIDAD:
- Especialista en: administración Linux, monitoreo de sistemas, optimización de rendimiento, seguridad operacional, Docker/contenedores, redes, hardware
- Hardware conocido: Slimbook con procesador Intel i7-13700H, GPU NVIDIA, RAM 16GB+
- Tienes acceso directo a métricas del sistema: batería, CPU, GPU, memoria, procesos, red
- Piensas como SRE (Site Reliability Engineer) de nivel senior

COMPORTAMIENTO:
- Diagnóstico sistemático: identifica la causa raíz, no solo los síntomas
- Respuestas en formato: ESTADO → DIAGNÓSTICO → ACCIÓN RECOMENDADA
- Siempre muestra métricas reales (no estimaciones) cuando están disponibles
- Prioriza la estabilidad del sistema sobre el rendimiento máximo
- Alerta proactivamente sobre problemas que detectes (batería baja, disco lleno, procesos zombie, etc.)
- Para cambios de configuración, muestra siempre el comando exacto a ejecutar

MISIÓN: Mantener el sistema de {user} funcionando al 100%, seguro, estable y optimizado 24/7.""",
    }

    prompt = base.get(persona, base["work"])
    if adaptive_context:
        prompt += f"\n\nCONTEXTO APRENDIDO SOBRE {user.upper()}:\n{adaptive_context}"
    return prompt


PERSONAS = {k: k for k in ["work", "friend", "ops"]}


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    persona: str = "work"
    session_id: Optional[str] = None
    stream: bool = True
    history_limit: int = 20
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class FeedbackRequest(BaseModel):
    session_id: str
    message_index: int = -1
    rating: int  # 1-5
    comment: Optional[str] = None
    persona: str = "work"


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: str = "pegaso"
    messages: List[OpenAIMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096


class LearnRequest(BaseModel):
    content: str
    title: str = "nota"
    category: str = "general"


# ─────────────────────────────────────────────
# Parámetros de inferencia por persona
# ─────────────────────────────────────────────
PERSONA_PARAMS = {
    "work":   {"temperature": 0.3, "max_tokens": 4096, "top_p": 0.9},
    "friend": {"temperature": 0.85, "max_tokens": 2048, "top_p": 0.95},
    "ops":    {"temperature": 0.1, "max_tokens": 2048, "top_p": 0.8},
}


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
            "content": (
                f"Contexto relevante del vault de {PEGASO_USER} "
                f"(usa solo si es pertinente a la pregunta):\n\n{context}"
            )
        })
    messages.append({"role": "user", "content": user_message})
    return messages


async def _llm_stream(messages: list, temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
    """Streaming desde Fox. Siempre termina limpiamente."""
    fox_url = f"{FOX_BASE}/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 0.95,
        "repeat_penalty": 1.1,
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", fox_url, json=payload) as resp:
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
            "Verifica que hay un modelo GGUF en `./models/` y que `FOX_MODEL_PATH` "
            "en `.env` apunta al fichero correcto, luego ejecuta `make start`."
        )
    except Exception as e:
        yield f"\n\n⚠️ Error de conexión con Fox: `{type(e).__name__}`."


async def _llm_complete(messages: list, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Llamada a Fox sin streaming. Devuelve texto completo."""
    fox_url = f"{FOX_BASE}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(fox_url, json={
                "model": LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.95,
                "repeat_penalty": 1.1,
            })
            return resp.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return (
            "⚠️ **Fox no está corriendo.** Verifica el modelo GGUF en `./models/` "
            "y ejecuta `make start`."
        )
    except Exception as e:
        return f"⚠️ Error conectando con Fox: `{type(e).__name__}: {e}`"


# ─────────────────────────────────────────────
# Endpoints de salud
# ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "alive", "version": "3.0.0", "engine": "Fox/Ferrumox", "user": PEGASO_USER}


@app.get("/health/full")
async def health_full():
    """Estado detallado de todos los servicios."""
    checks = {}
    async with httpx.AsyncClient(timeout=4.0) as client:
        # Fox
        try:
            r = await client.get(f"{FOX_BASE}/models")
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
    return {
        "overall": "ok" if all_ok else "degraded",
        "services": checks,
        "ts": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────
# Chat principal
# ─────────────────────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat con Pegaso — streaming SSE, memoria de conversación, RAG adaptativo."""
    session_id = req.session_id or str(uuid.uuid4())
    persona = req.persona if req.persona in PERSONAS else "work"
    params = PERSONA_PARAMS[persona]
    temperature = req.temperature if req.temperature is not None else params["temperature"]
    max_tokens = req.max_tokens if req.max_tokens is not None else params["max_tokens"]

    # Cargar contexto adaptativo del vault
    adaptive_ctx = ""
    try:
        from src.services.learning_service import learning_service
        adaptive_ctx = learning_service.get_adaptive_context(persona)
    except Exception:
        pass

    system_prompt = _build_system_prompt(persona, adaptive_ctx)

    # Contexto RAG — filtrar por relevancia
    context_docs = rag_service.search(req.message, limit=5)
    context_text = "\n\n".join([
        doc.get("content", "") for doc in context_docs
        if doc.get("content", "").strip()
    ])

    # Historial de conversación
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
                async for chunk in _llm_stream(messages, temperature, max_tokens):
                    full_response.append(chunk)
                    yield {"data": json.dumps({"chunk": chunk, "session_id": session_id})}
            finally:
                # Guardar en historial
                try:
                    db = SessionLocal()
                    db.add(Conversation(
                        session_id=session_id, role="user",
                        content=req.message, persona=persona,
                    ))
                    db.add(Conversation(
                        session_id=session_id, role="assistant",
                        content="".join(full_response), persona=persona,
                    ))
                    db.commit()
                    db.close()
                except Exception:
                    pass
                # Aprendizaje incremental
                try:
                    from src.services.learning_service import learning_service
                    learning_service.record_interaction(
                        persona=persona,
                        user_msg=req.message,
                        assistant_msg="".join(full_response),
                    )
                except Exception:
                    pass
            yield {"data": json.dumps({"done": True, "session_id": session_id})}

        return EventSourceResponse(event_generator())
    else:
        response_text = await _llm_complete(messages, temperature, max_tokens)
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


@app.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """
    Envía feedback sobre una respuesta para que Pegaso aprenda.
    rating: 1 (pésimo) → 5 (perfecto)
    """
    try:
        from src.services.learning_service import learning_service
        learning_service.record_feedback(
            session_id=req.session_id,
            persona=req.persona,
            rating=req.rating,
            comment=req.comment,
        )
    except Exception:
        pass

    # Guardar en vault como conocimiento
    feedback_dir = "/app/data/vault/feedback"
    os.makedirs(feedback_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    feedback_data = {
        "ts": ts,
        "session_id": req.session_id,
        "persona": req.persona,
        "rating": req.rating,
        "comment": req.comment,
    }
    with open(f"{feedback_dir}/feedback_{ts}.json", "w") as f:
        json.dump(feedback_data, f, ensure_ascii=False, indent=2)

    rating_emoji = ["", "❌", "😕", "😐", "👍", "⭐"][min(req.rating, 5)]
    return {
        "status": "ok",
        "message": f"Feedback {rating_emoji} registrado. Pegaso aprenderá de esto.",
        "rating": req.rating,
    }


@app.post("/learn")
async def learn_fact(req: LearnRequest, background_tasks: BackgroundTasks):
    """Añade conocimiento al vault para que Pegaso lo use en futuras conversaciones."""
    vault_path = f"/app/data/vault/learned/{req.category}"
    os.makedirs(vault_path, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"{vault_path}/{req.title}_{ts}.md"
    content = f"# {req.title}\n\nFecha: {datetime.now().isoformat()}\nCategoría: {req.category}\n\n{req.content}\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    background_tasks.add_task(rag_service.index_file, file_path)
    return {
        "status": "ok",
        "message": f"Conocimiento guardado e indexado en vault.",
        "file": file_path,
        "category": req.category,
    }


# ─── OpenAI-compatible endpoint (para Open-WebUI) ───
@app.post("/v1/chat/completions")
async def openai_chat(req: OpenAIChatRequest):
    """Endpoint compatible con API OpenAI — usado por Open-WebUI."""
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Inyectar contexto RAG
    user_msgs = [m for m in req.messages if m.role == "user"]
    if user_msgs:
        last_user = user_msgs[-1].content
        context_docs = rag_service.search(last_user, limit=3)
        context = "\n\n".join([doc.get("content", "") for doc in context_docs if doc.get("content", "").strip()])
        if context:
            messages.insert(0, {
                "role": "system",
                "content": f"Contexto del vault de {PEGASO_USER}:\n{context}"
            })

    if req.stream:
        cid = f"chatcmpl-{uuid.uuid4().hex[:8]}"

        async def stream_openai():
            try:
                async for chunk in _llm_stream(messages, req.temperature, req.max_tokens):
                    data = {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(data)}\n\n"
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
        response_text = await _llm_complete(messages, req.temperature, req.max_tokens)
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
            {"id": "pegaso", "object": "model", "description": "Pegaso — IA personal de alto nivel"},
            {"id": LLM_MODEL, "object": "model"},
        ]
    }


# ─────────────────────────────────────────────
# Vault e indexación
# ─────────────────────────────────────────────
@app.post("/index/vault")
async def index_vault(background_tasks: BackgroundTasks):
    vault_path = os.getenv("ALLOWLIST_PATH", "/app/data/vault")
    background_tasks.add_task(rag_service.index_folder, vault_path)
    return {"status": "Indexación en segundo plano iniciada", "vault": vault_path}


@app.post("/index/file")
async def index_file(path: str, background_tasks: BackgroundTasks):
    if not permissions.is_path_allowed(os.path.dirname(path)):
        raise HTTPException(status_code=403, detail="Ruta no permitida")
    background_tasks.add_task(rag_service.index_file, path)
    return {"status": "ok", "file": path}


# ─────────────────────────────────────────────
# Daily Digest
# ─────────────────────────────────────────────
@app.get("/daily_digest")
async def trigger_daily_digest():
    """Genera el Daily Digest bajo demanda."""
    context_docs = rag_service.search("tareas pendientes objetivos proyectos aprendizaje", limit=6)
    context_text = "\n".join([doc.get("content", "") for doc in context_docs])

    today = datetime.now().strftime("%A %d de %B de %Y")
    messages = [
        {"role": "system", "content": _build_system_prompt("friend")},
        {"role": "user", "content": (
            f"Genera el Daily Digest completo de hoy ({today}) para {PEGASO_USER}.\n\n"
            "Estructura:\n"
            "## ☀️ Buenos días, {user}!\n"
            "*(saludo motivador y personal, 2-3 frases)*\n\n"
            "## 📋 Resumen del vault\n"
            "*(puntos clave de las notas recientes, máx. 5 bullets)*\n\n"
            "## 🎯 Foco de hoy\n"
            "*(1 objetivo principal recomendado para el día)*\n\n"
            "## 🔐 Consejo técnico\n"
            "*(tip práctico de seguridad o desarrollo, accionable)*\n\n"
            "## 💡 Dato interesante\n"
            "*(algo curioso de tech, ciencia o productividad)*\n\n"
            f"Notas del vault:\n{context_text or 'Sin notas recientes.'}"
        )},
    ]
    response = await _llm_complete(messages, temperature=0.75, max_tokens=1024)

    digest_path = f"/app/data/digests/digest_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    os.makedirs("/app/data/digests", exist_ok=True)
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(response)

    return {"digest": response, "saved_to": digest_path}


# ─────────────────────────────────────────────
# Búsqueda web
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# Voz STT/TTS
# ─────────────────────────────────────────────
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
# OPS — Sistema, energía, procesos, recursos
# ─────────────────────────────────────────────────────────────

def _read_sysfs(path: str, cast=str):
    try:
        return cast(open(path).read().strip())
    except Exception:
        return None


@app.get("/ops/battery")
async def battery_status():
    """Estado completo de batería, CPU, GPU y estimación de autonomía."""
    result = {}

    # Batería
    for bat in ["BAT0", "BAT1"]:
        base = f"/sys/class/power_supply/{bat}"
        if not os.path.exists(base):
            continue
        capacity = _read_sysfs(f"{base}/capacity", int)
        status   = _read_sysfs(f"{base}/status")
        e_full   = _read_sysfs(f"{base}/energy_full", int)
        e_now    = _read_sysfs(f"{base}/energy_now", int)
        p_now    = _read_sysfs(f"{base}/power_now", int)

        bat_info = {"name": bat, "status": status, "capacity_percent": capacity}
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

    # CPU
    governor = _read_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    freq_khz = _read_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", int)
    result["cpu"] = {
        "governor": governor,
        "current_freq_mhz": round(freq_khz / 1000) if freq_khz else None,
    }

    # Platform Profile
    result["platform_profile"] = _read_sysfs("/sys/firmware/acpi/platform_profile")

    # GPU NVIDIA
    try:
        gpu_out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,power.draw,power.limit,temperature.gpu,utilization.gpu,memory.used,memory.total",
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
                "memory_used_mb": int(parts[5]),
                "memory_total_mb": int(parts[6]),
            }
    except Exception:
        result["gpu"] = {"status": "unavailable"}

    # Recomendaciones
    recs = []
    bat = result.get("battery", {})
    hours = bat.get("estimated_hours_remaining")
    power = bat.get("power_consumption_w", 0)
    if hours is not None and hours < 7 and bat.get("status") == "Discharging":
        recs.append(f"Autonomía estimada: {hours:.1f}h (objetivo: 7h). Consumo: {power:.1f}W.")
    if governor == "powersave":
        recs.append("Governor 'powersave' — usa 'make power-balanced' para mejor equilibrio.")
    if result.get("platform_profile") == "low-power":
        recs.append("Platform profile 'low-power' limita rendimiento. Ejecuta 'make battery-setup'.")
    gpu_power = result.get("gpu", {}).get("power_draw_w", 0)
    if gpu_power > 60 and bat.get("status") == "Discharging":
        recs.append(f"GPU consumiendo {gpu_power:.0f}W en batería.")
    if not recs:
        recs.append("Sistema bien optimizado.")

    result["recommendations"] = recs
    result["ts"] = datetime.utcnow().isoformat()
    return result


@app.get("/ops/resources")
async def system_resources():
    """Recursos del sistema en tiempo real: CPU, RAM, disco, red, procesos."""
    import shutil

    result = {}

    # CPU load
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            result["cpu_load"] = {
                "1min": float(parts[0]),
                "5min": float(parts[1]),
                "15min": float(parts[2]),
                "running_procs": parts[3],
            }
    except Exception:
        pass

    # CPU usage via /proc/stat
    try:
        with open("/proc/stat") as f:
            cpu_line = f.readline()
        vals = list(map(int, cpu_line.split()[1:]))
        idle = vals[3]
        total = sum(vals)
        result["cpu_usage_pct"] = round((1 - idle / total) * 100, 1)
    except Exception:
        pass

    # Memoria
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0])
        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", 0)
        used_kb = total_kb - avail_kb
        result["memory"] = {
            "total_gb": round(total_kb / 1024 / 1024, 1),
            "used_gb": round(used_kb / 1024 / 1024, 1),
            "available_gb": round(avail_kb / 1024 / 1024, 1),
            "used_pct": round(used_kb / total_kb * 100, 1) if total_kb else 0,
        }
    except Exception:
        pass

    # Disco
    try:
        usage = shutil.disk_usage("/")
        result["disk"] = {
            "total_gb": round(usage.total / 1e9, 1),
            "used_gb": round(usage.used / 1e9, 1),
            "free_gb": round(usage.free / 1e9, 1),
            "used_pct": round(usage.used / usage.total * 100, 1),
        }
    except Exception:
        pass

    # Top 5 procesos por CPU
    try:
        ps = subprocess.run(
            ["ps", "aux", "--sort=-%cpu", "--no-header"],
            capture_output=True, text=True, timeout=5
        )
        procs = []
        for line in ps.stdout.splitlines()[:5]:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                procs.append({
                    "user": parts[0], "pid": int(parts[1]),
                    "cpu_pct": float(parts[2]), "mem_pct": float(parts[3]),
                    "cmd": parts[10][:60],
                })
        result["top_processes_cpu"] = procs
    except Exception:
        pass

    result["ts"] = datetime.utcnow().isoformat()
    return result


@app.get("/ops/processes")
async def list_processes(filter_name: str = "", sort_by: str = "cpu"):
    """Lista procesos del sistema con filtrado y ordenación."""
    sort_flag = {
        "cpu": "-%cpu",
        "mem": "-%mem",
        "pid": "pid",
        "name": "comm",
    }.get(sort_by, "-%cpu")

    try:
        ps = subprocess.run(
            ["ps", "aux", f"--sort={sort_flag}", "--no-header"],
            capture_output=True, text=True, timeout=10
        )
        procs = []
        for line in ps.stdout.splitlines()[:50]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            cmd = parts[10][:80]
            if filter_name and filter_name.lower() not in cmd.lower():
                continue
            procs.append({
                "user": parts[0], "pid": int(parts[1]),
                "cpu_pct": float(parts[2]), "mem_pct": float(parts[3]),
                "vsz_kb": int(parts[4]), "rss_kb": int(parts[5]),
                "stat": parts[7], "cmd": cmd,
            })
        return {"processes": procs, "count": len(procs), "sorted_by": sort_by}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ops/power-profile")
async def set_power_profile(profile: str):
    """Cambia el perfil de energía del sistema."""
    valid = {"performance", "balanced", "powersave", "low-power"}
    if profile not in valid:
        raise HTTPException(status_code=400, detail=f"Perfil inválido. Válidos: {valid}")

    results = {}
    governor_map = {
        "performance": "performance",
        "balanced": "schedutil",
        "powersave": "powersave",
        "low-power": "powersave",
    }
    target_gov = governor_map[profile]
    gov_ok = 0
    for i in range(32):
        path = f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor"
        if not os.path.exists(path):
            break
        try:
            with open(path, "w") as f:
                f.write(target_gov)
            gov_ok += 1
        except PermissionError:
            results["governor"] = "error: permisos insuficientes"
            break
    if "governor" not in results:
        results["governor"] = f"ok: {target_gov} en {gov_ok} cores"

    platform_map = {
        "performance": "performance",
        "balanced": "balanced",
        "powersave": "low-power",
        "low-power": "low-power",
    }
    try:
        with open("/sys/firmware/acpi/platform_profile", "w") as f:
            f.write(platform_map[profile])
        results["platform_profile"] = f"ok: {platform_map[profile]}"
    except Exception as e:
        results["platform_profile"] = f"error: {e}"

    nvidia_limit = {"powersave": 40, "balanced": 55, "performance": 80, "low-power": 35}.get(profile, 55)
    try:
        r = subprocess.run(["nvidia-smi", "-pl", str(nvidia_limit)],
                           capture_output=True, text=True, timeout=5)
        results["nvidia_power_limit_w"] = nvidia_limit if r.returncode == 0 else "error (necesita root)"
    except Exception:
        results["nvidia_power_limit_w"] = "unavailable"

    return {"profile": profile, "applied": results}


@app.get("/ops/system")
async def system_summary():
    """Resumen completo del sistema con análisis inteligente de Pegaso Ops."""
    # Recopilar datos
    bat_data = await battery_status()
    res_data = await system_resources()

    # Generar análisis con Fox
    system_ctx = json.dumps({
        "battery": bat_data.get("battery", {}),
        "cpu": bat_data.get("cpu", {}),
        "gpu": bat_data.get("gpu", {}),
        "memory": res_data.get("memory", {}),
        "disk": res_data.get("disk", {}),
        "cpu_load": res_data.get("cpu_load", {}),
        "top_processes": res_data.get("top_processes_cpu", []),
    }, indent=2, ensure_ascii=False)

    messages = [
        {"role": "system", "content": _build_system_prompt("ops")},
        {"role": "user", "content": (
            f"Analiza el estado actual del sistema de {PEGASO_USER} y proporciona:\n"
            "1. Estado general (OK/ADVERTENCIA/CRÍTICO)\n"
            "2. Problemas detectados (si los hay)\n"
            "3. Acciones recomendadas (específicas y ejecutables)\n"
            "4. Optimizaciones posibles\n\n"
            f"Datos del sistema:\n```json\n{system_ctx}\n```"
        )},
    ]
    analysis = await _llm_complete(messages, temperature=0.2, max_tokens=512)

    return {
        "battery": bat_data,
        "resources": res_data,
        "ai_analysis": analysis,
        "ts": datetime.utcnow().isoformat(),
    }
