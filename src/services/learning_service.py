"""
Pegaso Learning Service — Aprendizaje adaptativo continuo.

Registra interacciones, feedback y preferencias del usuario para que
Pegaso mejore progresivamente sin necesidad de re-entrenar el modelo.
El aprendizaje se materializa en:
  1. Contexto adaptativo inyectado en cada system prompt
  2. Notas en el vault (indexadas en Qdrant para RAG)
  3. Estadísticas de calidad por persona
"""
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional


LEARNING_DIR = os.getenv("LEARNING_DIR", "/app/data/vault/learning")
STATS_FILE = os.path.join(LEARNING_DIR, "stats.json")
PREFS_FILE = os.path.join(LEARNING_DIR, "preferences.json")
FACTS_FILE = os.path.join(LEARNING_DIR, "learned_facts.md")
PEGASO_USER = os.getenv("PEGASO_USER", "José")


class LearningService:
    """
    Servicio de aprendizaje adaptativo para Pegaso.
    Persiste en /app/data/vault/learning/ y es indexado por RAG.
    """

    def __init__(self):
        Path(LEARNING_DIR).mkdir(parents=True, exist_ok=True)
        self.stats = self._load_json(STATS_FILE, {
            "total_interactions": 0,
            "by_persona": {"work": 0, "friend": 0, "ops": 0},
            "ratings": [],
            "avg_rating": 0.0,
            "sessions": [],
        })
        self.prefs = self._load_json(PREFS_FILE, {
            "user": PEGASO_USER,
            "preferred_persona": "work",
            "language": "es",
            "response_style": "concise",
            "topics_of_interest": [],
            "topics_to_avoid": [],
            "custom_instructions": [],
            "last_updated": None,
        })

    # ──────────────────────────────────────────
    # Carga / guardado
    # ──────────────────────────────────────────

    def _load_json(self, path: str, default: dict) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: str, data: dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Learning] Error guardando {path}: {e}")

    # ──────────────────────────────────────────
    # Registro de interacciones
    # ──────────────────────────────────────────

    def record_interaction(self, persona: str, user_msg: str, assistant_msg: str):
        """Registra una interacción para análisis de patrones."""
        self.stats["total_interactions"] += 1
        self.stats["by_persona"][persona] = self.stats["by_persona"].get(persona, 0) + 1

        # Detectar temas recurrentes (palabras clave frecuentes)
        self._update_topics(user_msg)

        # Actualizar persona preferida
        persona_counts = self.stats["by_persona"]
        self.prefs["preferred_persona"] = max(persona_counts, key=persona_counts.get)

        self._save_json(STATS_FILE, self.stats)
        self._save_json(PREFS_FILE, self.prefs)

        # Guardar interacción notable si es larga (probable respuesta útil)
        if len(assistant_msg) > 300:
            self._save_notable_interaction(persona, user_msg, assistant_msg)

    def _update_topics(self, message: str):
        """Extrae y acumula temas de interés desde los mensajes."""
        # Palabras clave técnicas de interés
        tech_keywords = [
            "docker", "kubernetes", "python", "rust", "linux", "seguridad", "security",
            "git", "api", "database", "redis", "nginx", "ssl", "ssh", "vpn",
            "batería", "battery", "rendimiento", "performance", "optimizar",
            "nvidia", "gpu", "ia", "llm", "machine learning",
        ]
        message_lower = message.lower()
        found_topics = [kw for kw in tech_keywords if kw in message_lower]

        current_topics = set(self.prefs.get("topics_of_interest", []))
        current_topics.update(found_topics)
        # Mantener solo los 20 más relevantes
        self.prefs["topics_of_interest"] = list(current_topics)[:20]
        self.prefs["last_updated"] = datetime.now().isoformat()

    def _save_notable_interaction(self, persona: str, user_msg: str, assistant_msg: str):
        """Guarda interacciones notables en el vault para RAG."""
        interactions_dir = Path(LEARNING_DIR) / "interactions"
        interactions_dir.mkdir(exist_ok=True)

        # Hash para evitar duplicados
        content_hash = hashlib.md5(
            (user_msg + assistant_msg).encode()
        ).hexdigest()[:8]
        file_path = interactions_dir / f"interaction_{content_hash}.md"

        if not file_path.exists():
            content = (
                f"# Interacción útil — {datetime.now().strftime('%Y-%m-%d')}\n"
                f"**Persona:** {persona}\n\n"
                f"**Pregunta:** {user_msg[:500]}\n\n"
                f"**Respuesta:**\n{assistant_msg[:2000]}\n"
            )
            try:
                file_path.write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"[Learning] Error guardando interacción: {e}")

    # ──────────────────────────────────────────
    # Feedback
    # ──────────────────────────────────────────

    def record_feedback(
        self, session_id: str, persona: str, rating: int, comment: Optional[str] = None
    ):
        """Registra feedback explícito del usuario."""
        feedback_entry = {
            "ts": datetime.now().isoformat(),
            "session_id": session_id,
            "persona": persona,
            "rating": rating,
            "comment": comment,
        }
        self.stats.setdefault("ratings", []).append(feedback_entry)

        # Calcular media móvil (últimas 50 valoraciones)
        recent = self.stats["ratings"][-50:]
        if recent:
            self.stats["avg_rating"] = round(sum(r["rating"] for r in recent) / len(recent), 2)

        # Si el rating es alto (4-5), aprender del estilo
        if rating >= 4 and comment:
            self._learn_from_positive_feedback(persona, comment)

        # Si el rating es bajo (1-2), registrar para evitar ese patrón
        if rating <= 2 and comment:
            self._learn_from_negative_feedback(persona, comment)

        self._save_json(STATS_FILE, self.stats)
        print(f"[Learning] Feedback registrado: {rating}/5 para {persona} (media: {self.stats['avg_rating']})")

    def _learn_from_positive_feedback(self, persona: str, comment: str):
        """Aprende qué funciona bien."""
        instruction = f"[{persona}] Lo que gustó al usuario: {comment[:200]}"
        instructions = self.prefs.setdefault("custom_instructions", [])
        if instruction not in instructions:
            instructions.append(instruction)
            self.prefs["custom_instructions"] = instructions[-10:]  # Máx 10

    def _learn_from_negative_feedback(self, persona: str, comment: str):
        """Aprende qué no funciona."""
        instruction = f"[{persona}] Evitar: {comment[:200]}"
        avoid = self.prefs.setdefault("topics_to_avoid", [])
        if instruction not in avoid:
            avoid.append(instruction)
            self.prefs["topics_to_avoid"] = avoid[-5:]  # Máx 5

    # ──────────────────────────────────────────
    # Guardar hechos aprendidos
    # ──────────────────────────────────────────

    def add_fact(self, fact: str, category: str = "general"):
        """Añade un hecho aprendido al vault."""
        Path(FACTS_FILE).parent.mkdir(parents=True, exist_ok=True)
        entry = f"\n## {category} — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{fact}\n"
        try:
            with open(FACTS_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
            print(f"[Learning] Hecho añadido: {fact[:60]}...")
        except Exception as e:
            print(f"[Learning] Error añadiendo hecho: {e}")

    # ──────────────────────────────────────────
    # Contexto adaptativo para system prompt
    # ──────────────────────────────────────────

    def get_adaptive_context(self, persona: str) -> str:
        """
        Genera contexto dinámico para inyectar en el system prompt.
        Basado en preferencias aprendidas y estadísticas de uso.
        """
        lines = []

        # Estadísticas de uso
        total = self.stats.get("total_interactions", 0)
        avg = self.stats.get("avg_rating", 0)
        if total > 0:
            lines.append(f"- Lleváis {total} interacciones juntos. Satisfacción media: {avg:.1f}/5.")

        # Temas de interés
        topics = self.prefs.get("topics_of_interest", [])
        if topics:
            lines.append(f"- Temas frecuentes de {PEGASO_USER}: {', '.join(topics[:8])}.")

        # Instrucciones personalizadas aprendidas
        custom = self.prefs.get("custom_instructions", [])
        if custom:
            lines.append("- Instrucciones aprendidas del usuario:")
            for inst in custom[-3:]:  # Solo las 3 más recientes
                lines.append(f"  • {inst}")

        # Cosas a evitar
        avoid = self.prefs.get("topics_to_avoid", [])
        if avoid:
            lines.append("- Patrones a evitar:")
            for a in avoid[-2:]:
                lines.append(f"  • {a}")

        # Estilo preferido
        style = self.prefs.get("response_style", "concise")
        if style == "detailed":
            lines.append("- El usuario prefiere respuestas detalladas y exhaustivas.")
        elif style == "concise":
            lines.append("- El usuario prefiere respuestas concisas y directas.")

        return "\n".join(lines) if lines else ""

    def update_preference(self, key: str, value):
        """Actualiza una preferencia específica del usuario."""
        self.prefs[key] = value
        self.prefs["last_updated"] = datetime.now().isoformat()
        self._save_json(PREFS_FILE, self.prefs)
        return {"updated": key, "value": value}

    def get_summary(self) -> dict:
        """Devuelve resumen del estado de aprendizaje."""
        return {
            "total_interactions": self.stats.get("total_interactions", 0),
            "avg_rating": self.stats.get("avg_rating", 0),
            "preferred_persona": self.prefs.get("preferred_persona", "work"),
            "topics_of_interest": self.prefs.get("topics_of_interest", [])[:10],
            "custom_instructions_count": len(self.prefs.get("custom_instructions", [])),
            "last_updated": self.prefs.get("last_updated"),
        }


# Singleton global
learning_service = LearningService()
