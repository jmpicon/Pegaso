#!/usr/bin/env python3
"""
Pegaso Tux — Asistente IA personal con mascota Pingüino Linux.

El pingüino Tux actúa como interfaz visual del asistente Pegaso/Fox,
respondiendo preguntas, controlando el sistema, organizando archivos
y optimizando el Slimbook.

Uso:
    python scripts/tux.py                    # Modo interactivo
    python scripts/tux.py "organiza Descargas"  # Comando directo
    python scripts/tux.py --persona ops     # Modo ops (sistema)
    python scripts/tux.py --status          # Estado del sistema

Requiere que la API de Pegaso esté corriendo (make start)
"""

import sys
import os
import json
import time
import shutil
import argparse
import textwrap
import subprocess
from datetime import datetime

# ─── Dependencias opcionales ───────────────────────────────────────────
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import readline  # historial de comandos en terminal
except ImportError:
    pass

# ─── Configuración ─────────────────────────────────────────────────────
API_BASE = os.getenv("PEGASO_API_URL", "http://localhost:8080")
PEGASO_USER = os.getenv("PEGASO_USER", "José")

# ─── Colores ANSI ──────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    BLACK  = "\033[30m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    MAGENTA= "\033[35m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"
    BG_BLUE= "\033[44m"
    BG_BLACK="\033[40m"
    ORANGE = "\033[38;5;208m"

def _no_color() -> bool:
    return not sys.stdout.isatty() or os.getenv("NO_COLOR")

def c(color: str, text: str) -> str:
    if _no_color():
        return text
    return f"{color}{text}{C.RESET}"


# ─── Arte ASCII del Pingüino Tux ───────────────────────────────────────
TUX_IDLE = r"""
       .88888888:.
      88888888.88888.
    .8888888888888888.
    888888888888888888
    88' _`88'_  `88888
    88 88 88 88  88888
    88_88_::_88_:88888
    88:::,::,:::::8888
    88`:::::::::'`8888
   .88  `:::::'    8:88.
  8888            `8:888.
.8888'             `888888.
.8888:..  .::.  ...:'8888888:.
8888.'     :'     `'::`88:88888
`8888'   .8888888:   `888:88888
.8888:  888888888    :88:'88888
:8888.:  888888888   :88:'88888
:8888::  .88888888  .:88  88888
 88888:   888888   .888  888888
 `888888  .888  .888888'  `8888
  `888888 `88  888888'     `888
   `8888   `8  8888'        888
    888:       888:         `88
    888:       888:
     88         88
     88         88
     88         88
     `8.       .8'
      `8:.   .:8'
        `888888'
"""

TUX_TALK = r"""
       .88888888:.
      88888888.88888.
    .8888888888888888.
    888888888888888888
    88' _`88'_  `88888
    88 88 88 88  88888
    88_88_::_88_:88888
    88:::,::,:::::8888
    88`:::::::::'`8888
   .88  `:::::'    8:88.
  8888            `8:888.
.8888'             `888888.
.8888:..  .::.  ...:'8888888:.
"""

TUX_THINK = r"""
       .·°°·.
      (  ??? )
       `·..·'
       .88888888:.
      88888888.88888.
    .8888888888888888.
    88' _`88'_  `88888
    88 88 88 88  88888
    88_88_::_88_:88888
"""

TUX_HAPPY = r"""
       \(^o^)/
       .88888888:.
      88888888.88888.
    .8888888888888888.
    88' _`88'_  `88888
    88 88 88 88  88888
    88_88_::_88_:88888
"""

TUX_ERROR = r"""
       .88888888:.    ×_×
      88888888.88888.
    .8888888888888888.
    88' _`88'_  `88888
    88 88 88 88  88888
"""

# ─── Burbuja de diálogo ────────────────────────────────────────────────
def _speech_bubble(text: str, width: int = 60, speaker: str = "Tux") -> str:
    """Genera una burbuja de diálogo estilo cómic."""
    term_width = shutil.get_terminal_size((80, 24)).columns
    width = min(width, term_width - 4)
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
        else:
            wrapped = textwrap.wrap(paragraph, width - 4) or [""]
            lines.extend(wrapped)

    max_len = max(len(l) for l in lines) if lines else 0
    box_width = max(max_len, len(speaker) + 2)

    top    = f"╭─ {c(C.CYAN + C.BOLD, speaker)} {'─' * (box_width - len(speaker) - 1)}╮"
    bottom = f"╰{'─' * (box_width + 2)}╯"
    padded = [f"│ {l:<{box_width}} │" for l in lines]
    return "\n".join([top] + padded + [bottom])


def _tux_art(mood: str = "idle") -> str:
    arts = {
        "idle": TUX_IDLE,
        "talk": TUX_TALK,
        "think": TUX_THINK,
        "happy": TUX_HAPPY,
        "error": TUX_ERROR,
    }
    art = arts.get(mood, TUX_IDLE)
    if _no_color():
        return art
    # Colorear el arte de Tux
    colored = []
    for line in art.splitlines():
        line = line.replace("88", c(C.BLACK + C.BOLD, "██"))
        line = line.replace(".", c(C.WHITE, "."))
        line = line.replace("'", c(C.WHITE, "'"))
        colored.append(line)
    return "\n".join(colored)


def _header(persona: str = "work"):
    """Imprime el header de Pegaso Tux."""
    persona_labels = {
        "work":   ("Work", C.BLUE),
        "friend": ("Friend", C.MAGENTA),
        "ops":    ("Ops", C.GREEN),
    }
    label, color = persona_labels.get(persona, ("Pegaso", C.CYAN))
    term_w = shutil.get_terminal_size((80, 24)).columns
    title = f"  PEGASO TUX — {label}  "
    padding = "═" * ((term_w - len(title)) // 2)
    print(c(color + C.BOLD, f"\n{padding}{title}{padding}"))
    print(c(C.DIM, f"  Asistente IA personal de {PEGASO_USER} · Fox/Ferrumox · {datetime.now().strftime('%H:%M')}"))
    print(c(color, "─" * term_w))


def _spinner_frames():
    return ["◐", "◓", "◑", "◒"]


# ─── Cliente API ───────────────────────────────────────────────────────

class PegasoClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def health(self) -> dict:
        if not HAS_HTTPX:
            return {"status": "unknown", "error": "httpx no disponible"}
        try:
            with httpx.Client(timeout=5.0) as c:
                r = c.get(f"{self.base}/health")
                return r.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def health_full(self) -> dict:
        if not HAS_HTTPX:
            return {}
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.get(f"{self.base}/health/full")
                return r.json()
        except Exception as e:
            return {"error": str(e)}

    def chat(self, message: str, persona: str = "work", session_id: str = None) -> str:
        if not HAS_HTTPX:
            return self._offline_response(message)
        try:
            with httpx.Client(timeout=120.0) as c:
                r = c.post(f"{self.base}/chat", json={
                    "message": message,
                    "persona": persona,
                    "stream": False,
                    "session_id": session_id,
                })
                if r.status_code == 200:
                    return r.json().get("response", "Sin respuesta")
                return f"Error HTTP {r.status_code}: {r.text[:200]}"
        except httpx.ConnectError:
            return (
                "No puedo conectar con la API de Pegaso.\n"
                f"¿Está corriendo el stack? Ejecuta: make start\n"
                f"URL: {self.base}"
            )
        except Exception as e:
            return f"Error: {e}"

    def _offline_response(self, message: str) -> str:
        return (
            "Modo offline — httpx no disponible.\n"
            "Instala dependencias: pip install httpx\n"
            f"Tu pregunta era: {message}"
        )

    def battery(self) -> dict:
        if not HAS_HTTPX:
            return {}
        try:
            with httpx.Client(timeout=8.0) as c:
                r = c.get(f"{self.base}/ops/battery")
                return r.json()
        except Exception:
            return {}

    def resources(self) -> dict:
        if not HAS_HTTPX:
            return {}
        try:
            with httpx.Client(timeout=8.0) as c:
                r = c.get(f"{self.base}/ops/resources")
                return r.json()
        except Exception:
            return {}

    def system_summary(self) -> dict:
        if not HAS_HTTPX:
            return {}
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.get(f"{self.base}/ops/system")
                return r.json()
        except Exception as e:
            return {"error": str(e)}

    def set_power_profile(self, profile: str) -> dict:
        if not HAS_HTTPX:
            return {}
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.post(f"{self.base}/ops/power-profile", params={"profile": profile})
                return r.json()
        except Exception as e:
            return {"error": str(e)}

    def organize_folder(self, path: str, dry_run: bool = False) -> str:
        """Organiza una carpeta via API Pegaso."""
        message = f"Organiza la carpeta {path}" + (" (simular, no mover)" if dry_run else "")
        return self.chat(message, persona="ops")

    def learn(self, content: str, title: str = "nota", category: str = "general") -> dict:
        if not HAS_HTTPX:
            return {}
        try:
            with httpx.Client(timeout=15.0) as c:
                r = c.post(f"{self.base}/learn", json={
                    "content": content, "title": title, "category": category
                })
                return r.json()
        except Exception as e:
            return {"error": str(e)}


# ─── Visualización de estado del sistema ──────────────────────────────

def _bar(value: float, max_val: float = 100, width: int = 20, color: str = C.GREEN) -> str:
    """Barra de progreso ASCII coloreada."""
    pct = min(value / max_val, 1.0) if max_val else 0
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    bar_color = C.GREEN if pct < 0.6 else (C.YELLOW if pct < 0.85 else C.RED)
    return f"[{c(bar_color, bar)}] {pct * 100:.0f}%"


def _show_status(client: PegasoClient):
    """Muestra el estado completo del sistema."""
    _header("ops")
    print(c(C.CYAN, "\n🐧 Consultando estado del sistema...\n"))

    bat_data = client.battery()
    res_data = client.resources()

    # Batería
    bat = bat_data.get("battery", {})
    if bat:
        status = bat.get("status", "?")
        cap = bat.get("capacity_percent", 0)
        hours = bat.get("estimated_hours_remaining", None)
        power = bat.get("power_consumption_w", 0)

        status_icon = "🔌" if status == "Charging" else ("🔋" if cap > 20 else "⚠️")
        print(f"  {status_icon} Batería:  {_bar(cap)}  {cap}% · {status}")
        if hours:
            print(f"             Autonomía estimada: {c(C.CYAN, f'{hours:.1f}h')} · Consumo: {power:.1f}W")

    # CPU
    cpu_pct = res_data.get("cpu_usage_pct", 0)
    cpu_load = res_data.get("cpu_load", {})
    if cpu_pct is not None:
        print(f"\n  🖥️  CPU:      {_bar(cpu_pct)}  Load: {cpu_load.get('1min', '?')}/{cpu_load.get('5min', '?')}/{cpu_load.get('15min', '?')}")

    # RAM
    mem = res_data.get("memory", {})
    if mem:
        used = mem.get("used_gb", 0)
        total = mem.get("total_gb", 0)
        pct = mem.get("used_pct", 0)
        print(f"  🧠 RAM:      {_bar(pct)}  {used:.1f}/{total:.1f} GB")

    # Disco
    disk = res_data.get("disk", {})
    if disk:
        used = disk.get("used_gb", 0)
        total = disk.get("total_gb", 0)
        pct = disk.get("used_pct", 0)
        print(f"  💾 Disco:    {_bar(pct)}  {used:.1f}/{total:.1f} GB")

    # GPU
    gpu = bat_data.get("gpu", {})
    if gpu and gpu.get("name"):
        gpu_util = gpu.get("utilization_pct", 0)
        gpu_temp = gpu.get("temperature_c", 0)
        gpu_mem_used = gpu.get("memory_used_mb", 0)
        gpu_mem_total = gpu.get("memory_total_mb", 1)
        gpu_power = gpu.get("power_draw_w", 0)
        print(f"  🎮 GPU:      {_bar(gpu_util)}  {gpu_temp}°C · {gpu_power:.0f}W · VRAM: {gpu_mem_used}/{gpu_mem_total}MB")
        print(f"             {gpu.get('name', '')}")

    # Recomendaciones
    recs = bat_data.get("recommendations", [])
    if recs:
        print(f"\n  {c(C.YELLOW + C.BOLD, '💡 Recomendaciones:')}")
        for rec in recs:
            print(f"     • {rec}")

    # Top procesos
    procs = res_data.get("top_processes_cpu", [])
    if procs:
        print(f"\n  {c(C.DIM, 'Top procesos por CPU:')}")
        for p in procs[:3]:
            print(f"     {p['cpu_pct']:5.1f}%  {p['cmd'][:50]}")

    print()


def _show_help():
    """Muestra ayuda del asistente."""
    help_text = f"""
{c(C.CYAN + C.BOLD, '🐧 PEGASO TUX — Comandos especiales')}
{c(C.DIM, '─' * 50)}

Conversación:
  Escribe cualquier pregunta o instrucción directamente

Comandos del sistema:
  {c(C.GREEN, '/status')}        Estado del sistema (batería, CPU, RAM, GPU)
  {c(C.GREEN, '/performance')}   Modo rendimiento máximo
  {c(C.GREEN, '/balanced')}      Modo equilibrado (recomendado)
  {c(C.GREEN, '/powersave')}     Modo ahorro de batería (7h+)
  {c(C.GREEN, '/battery')}       Info detallada de batería

Organización de archivos:
  {c(C.GREEN, '/org [ruta]')}    Organiza una carpeta (Descargas, Documentos, etc.)
  {c(C.GREEN, '/org-dry [ruta]')} Previsualiza organización sin mover nada

Aprendizaje:
  {c(C.GREEN, '/learn [texto]')} Enseña algo a Pegaso (va al vault)
  {c(C.GREEN, '/digest')}        Genera el Daily Digest de hoy

Personas:
  {c(C.BLUE, '/work')}           Modo Work (DevOps, desarrollo, seguridad)
  {c(C.MAGENTA, '/friend')}         Modo Friend (personal, motivación)
  {c(C.GREEN + C.BOLD, '/ops')}            Modo Ops (sistema, hardware, rendimiento)

Navegación:
  {c(C.GREEN, '/clear')}         Limpiar pantalla
  {c(C.GREEN, '/help')}          Esta ayuda
  {c(C.GREEN, '/exit')} o Ctrl+C  Salir

{c(C.DIM, 'También puedes escribir instrucciones naturales como:')}
{c(C.DIM, '  "organiza mi carpeta Descargas"')}
{c(C.DIM, '  "¿cómo optimizo la batería?"')}
{c(C.DIM, '  "qué procesos consumen más CPU"')}
"""
    print(help_text)


# ─── Bucle principal ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pegaso Tux — Asistente IA personal con pingüino Linux"
    )
    parser.add_argument("command", nargs="?", help="Comando directo (no interactivo)")
    parser.add_argument("--persona", "-p", choices=["work", "friend", "ops"], default="work",
                        help="Persona de Pegaso (default: work)")
    parser.add_argument("--status", "-s", action="store_true", help="Mostrar estado del sistema y salir")
    parser.add_argument("--url", default=API_BASE, help=f"URL de la API (default: {API_BASE})")
    args = parser.parse_args()

    client = PegasoClient(args.url)
    current_persona = args.persona
    session_id = f"tux-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ── Modo estado ─────────────────────────────────────────────
    if args.status:
        _show_status(client)
        return

    # ── Modo comando directo ─────────────────────────────────────
    if args.command:
        print(c(C.DIM, f"\n🐧 Preguntando a Pegaso..."))
        response = client.chat(args.command, current_persona, session_id)
        bubble = _speech_bubble(response, speaker=f"Tux ({current_persona})")
        print(c(C.CYAN, bubble))
        return

    # ── Modo interactivo ─────────────────────────────────────────
    os.system("clear" if os.name != "nt" else "cls")
    _header(current_persona)

    # Verificar API
    health = client.health()
    if health.get("status") == "alive":
        engine = health.get("engine", "Fox")
        version = health.get("version", "?")
        print(c(C.GREEN, f"  ✅ Pegaso API online · {engine} v{version}"))
    else:
        print(c(C.YELLOW, f"  ⚠️  API no disponible en {args.url}"))
        print(c(C.DIM, "     Ejecuta 'make start' para iniciar Pegaso"))
        print(c(C.DIM, "     Continuando en modo limitado..."))

    # Pintar Tux
    print(c(C.DIM, TUX_TALK.splitlines()[0]))

    # Mensaje de bienvenida
    welcome = f"¡Hola, {PEGASO_USER}! Soy Tux, tu asistente Pegaso.\nEscribe /help para ver qué puedo hacer, o pregúntame directamente."
    print(_speech_bubble(welcome, speaker=f"Tux ({current_persona})"))
    print(c(C.DIM, "  Escribe /help para ver todos los comandos\n"))

    # Bucle de conversación
    while True:
        try:
            persona_color = {"work": C.BLUE, "friend": C.MAGENTA, "ops": C.GREEN}.get(current_persona, C.CYAN)
            prompt = c(persona_color + C.BOLD, f"\n[{current_persona}] {PEGASO_USER}") + c(C.DIM, " > ") + C.RESET
            user_input = input(prompt).strip()

            if not user_input:
                continue

            # ── Comandos especiales ───────────────────────────────
            if user_input.lower() in ("/exit", "/quit", "/salir", "exit", "quit"):
                print(_speech_bubble(f"¡Hasta pronto, {PEGASO_USER}! 🐧", speaker="Tux"))
                break

            elif user_input.lower() in ("/clear", "/cls"):
                os.system("clear" if os.name != "nt" else "cls")
                _header(current_persona)
                continue

            elif user_input.lower() in ("/help", "/ayuda"):
                _show_help()
                continue

            elif user_input.lower() in ("/status", "/estado"):
                _show_status(client)
                continue

            elif user_input.lower() in ("/performance", "/rendimiento", "/max"):
                print(c(C.YELLOW, "  ⚡ Activando modo rendimiento máximo..."))
                result = client.set_power_profile("performance")
                msg = f"Modo rendimiento activado.\n{json.dumps(result.get('applied', {}), indent=2, ensure_ascii=False)}"
                print(_speech_bubble(msg, speaker="Tux (ops)"))
                continue

            elif user_input.lower() in ("/balanced", "/equilibrado"):
                print(c(C.CYAN, "  ⚖️  Activando modo equilibrado..."))
                result = client.set_power_profile("balanced")
                msg = f"Modo equilibrado activado.\n{json.dumps(result.get('applied', {}), indent=2, ensure_ascii=False)}"
                print(_speech_bubble(msg, speaker="Tux (ops)"))
                continue

            elif user_input.lower() in ("/powersave", "/ahorro", "/bateria"):
                print(c(C.GREEN, "  🔋 Activando modo ahorro de batería..."))
                result = client.set_power_profile("powersave")
                msg = f"Modo ahorro de batería activado.\nBatería optimizada para 7h+\n{json.dumps(result.get('applied', {}), indent=2, ensure_ascii=False)}"
                print(_speech_bubble(msg, speaker="Tux (ops)"))
                continue

            elif user_input.lower() in ("/battery", "/bat"):
                _show_status(client)
                continue

            elif user_input.lower() in ("/work", "/worker"):
                current_persona = "work"
                print(_speech_bubble("Modo Work activado. Listo para DevOps, desarrollo y seguridad.", speaker="Tux (work)"))
                continue

            elif user_input.lower() in ("/friend", "/amigo"):
                current_persona = "friend"
                print(_speech_bubble(f"¡Hola! Modo Friend activado. ¿Cómo estás, {PEGASO_USER}? 😊", speaker="Tux (friend)"))
                continue

            elif user_input.lower() in ("/ops", "/sistema"):
                current_persona = "ops"
                print(_speech_bubble("Modo Ops activado. Monitoreando el sistema.", speaker="Tux (ops)"))
                continue

            elif user_input.lower().startswith("/org-dry "):
                path = user_input[9:].strip() or "~/Descargas"
                path = os.path.expanduser(path)
                print(c(C.YELLOW, f"  📁 Analizando {path}..."))
                # Llamar directamente a computer_tools para preview
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                try:
                    from src.tools.computer_tools import organize_folder
                    result = organize_folder(path, dry_run=True)
                    plan = result.get("plan", [])
                    if plan:
                        lines = [f"Plan para organizar {path} ({result['total_files']} archivos):"]
                        for item in plan[:20]:
                            lines.append(f"  {item['file']:<30} → {item['category']}/")
                        if len(plan) > 20:
                            lines.append(f"  ... y {len(plan)-20} archivos más")
                        print(_speech_bubble("\n".join(lines), speaker="Tux (análisis)"))
                    else:
                        print(_speech_bubble(f"La carpeta {path} está vacía o ya organizada.", speaker="Tux"))
                except Exception as e:
                    print(_speech_bubble(f"Error analizando carpeta: {e}", speaker="Tux"))
                continue

            elif user_input.lower().startswith("/org "):
                path = user_input[5:].strip() or "~/Descargas"
                path = os.path.expanduser(path)
                print(c(C.YELLOW, f"  📁 Organizando {path}..."))
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                try:
                    from src.tools.computer_tools import organize_folder
                    result = organize_folder(path, dry_run=False)
                    moved = result.get("moved", 0)
                    total = result.get("total_files", 0)
                    msg = (
                        f"✅ Carpeta {path} organizada.\n"
                        f"Movidos: {moved}/{total} archivos\n\n"
                        f"Estructura:\n"
                    )
                    categories = {}
                    for item in result.get("plan", []):
                        cat = item["category"]
                        categories[cat] = categories.get(cat, 0) + 1
                    for cat, count in sorted(categories.items()):
                        msg += f"  📂 {cat}/  ({count} archivos)\n"
                    print(_speech_bubble(msg, speaker="Tux (archivos)"))
                except Exception as e:
                    print(_speech_bubble(f"Error organizando: {e}", speaker="Tux"))
                continue

            elif user_input.lower().startswith("/learn "):
                content = user_input[7:].strip()
                if content:
                    result = client.learn(content, title="aprendido", category="usuario")
                    print(_speech_bubble(
                        f"✅ Aprendido y guardado en el vault.\n{result.get('file', '')}",
                        speaker="Tux"
                    ))
                continue

            elif user_input.lower() in ("/digest", "/resumen"):
                print(c(C.YELLOW, "  📋 Generando Daily Digest..."))
                try:
                    if HAS_HTTPX:
                        with httpx.Client(timeout=60.0) as hc:
                            r = hc.get(f"{args.url}/daily_digest")
                            digest = r.json().get("digest", "Error generando digest")
                            print(_speech_bubble(digest[:1500], speaker=f"Tux (friend)"))
                except Exception as e:
                    print(_speech_bubble(f"Error: {e}", speaker="Tux"))
                continue

            # ── Conversación normal con Fox ───────────────────────
            # Animación de "pensando"
            frames = _spinner_frames()
            i = 0
            print(c(C.DIM, "  🐧 Tux está pensando"), end="", flush=True)

            # Llamada a la API (síncrona con animación)
            response = None

            def _get_response():
                nonlocal response
                response = client.chat(user_input, current_persona, session_id)

            import threading
            t = threading.Thread(target=_get_response)
            t.start()
            while t.is_alive():
                print(f"\r  🐧 Tux está pensando {frames[i % len(frames)]}", end="", flush=True)
                i += 1
                time.sleep(0.2)
            print("\r" + " " * 40 + "\r", end="", flush=True)

            if response:
                # Determinar mood de Tux
                mood = "talk"
                if any(w in response.lower() for w in ["error", "fallo", "no puedo", "no disponible"]):
                    mood = "error"
                elif any(w in response.lower() for w in ["perfecto", "excelente", "genial", "bien"]):
                    mood = "happy"

                bubble = _speech_bubble(response, speaker=f"Tux ({current_persona})")
                print(c(C.CYAN if current_persona == "work" else C.MAGENTA if current_persona == "friend" else C.GREEN, bubble))

        except KeyboardInterrupt:
            print(f"\n\n{_speech_bubble(f'¡Hasta pronto, {PEGASO_USER}! Que tengas un gran día 🐧', speaker='Tux')}\n")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
