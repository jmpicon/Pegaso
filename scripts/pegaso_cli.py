#!/usr/bin/env python3
"""
Pegaso CLI — Asistente personal con Perplexity AI.
Uso: pegaso [mensaje]
     pegaso          # modo interactivo
     pegaso "organiza ~/Descargas"
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ──── cargar .env ────────────────────────────
def _load_env():
    """Carga .env desde la raíz del proyecto."""
    candidates = [
        Path(__file__).parent.parent / ".env",
        Path.home() / ".pegaso.env",
        Path("/etc/pegaso.env"),
    ]
    for env_file in candidates:
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        # quitar comillas y comentarios inline
                        val = val.split("#")[0].strip().strip('"').strip("'")
                        os.environ.setdefault(key.strip(), val)
            break

_load_env()

# ──── path del proyecto ──────────────────────
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.services.perplexity_agent import PegasoAgent

# ──────────────────────────────────────────────
# Colores ANSI
# ──────────────────────────────────────────────
_NO_COLOR = not sys.stdout.isatty() or os.getenv("NO_COLOR")

def c(text: str, code: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def blue(t):   return c(t, "94")
def green(t):  return c(t, "92")
def yellow(t): return c(t, "93")
def cyan(t):   return c(t, "96")
def bold(t):   return c(t, "1")
def dim(t):    return c(t, "2")


BANNER = f"""
{bold(cyan('  ██████╗ ███████╗ ██████╗  █████╗ ███████╗ ██████╗'))}
{bold(cyan(' ██╔══██╗██╔════╝██╔════╝ ██╔══██╗██╔════╝██╔═══██╗'))}
{bold(cyan(' ██████╔╝█████╗  ██║  ███╗███████║███████╗██║   ██║'))}
{bold(cyan(' ██╔═══╝ ██╔══╝  ██║   ██║██╔══██║╚════██║██║   ██║'))}
{bold(cyan(' ██║     ███████╗╚██████╔╝██║  ██║███████║╚██████╔╝'))}
{bold(cyan(' ╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝'))}
{dim('  Asistente Personal — Perplexity AI — Linux')}
"""

HELP_TEXT = f"""
{bold('Comandos especiales:')}
  {yellow('/help')}     Mostrar esta ayuda
  {yellow('/reset')}    Borrar historial de conversación
  {yellow('/system')}   Info del sistema (CPU, RAM, disco)
  {yellow('/organiza')} Organizar una carpeta (te pregunta cuál)
  {yellow('/ls')}       Listar directorio actual
  {yellow('/history')}  Ver historial de la sesión
  {yellow('/quit')}     Salir (también: exit, q, Ctrl+C)

{bold('Ejemplos de peticiones:')}
  • organiza mi carpeta de Descargas
  • busca todos los archivos PDF en ~/Documentos
  • cuánto espacio ocupa cada carpeta en el home
  • crea una carpeta llamada Proyectos en ~/
  • mueve todos los .jpg de ~/Descargas a ~/Imagenes
  • ejecuta: git status en ~/Documentos/Pegaso
  • lee el archivo ~/Documentos/notas.txt
"""


def _print_response(text: str):
    """Imprime la respuesta del agente con formato."""
    print(f"\n{bold(green('Pegaso:'))} {text}\n")


def _run_interactive(agent: PegasoAgent):
    """Modo interactivo con historial y comandos especiales."""
    print(BANNER)
    print(f"  {dim('Escribe tu petición o /help para ver los comandos.')}")
    print(f"  {dim('Ctrl+C o /quit para salir.')}\n")

    session_log = []

    while True:
        try:
            user_input = input(f"{bold(blue('Tú:'))} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{dim('Saliendo de Pegaso. ¡Hasta luego!')}")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("/quit", "/exit", "/q", "exit", "quit", "q"):
            print(f"{dim('Saliendo de Pegaso. ¡Hasta luego!')}")
            break

        if cmd == "/help":
            print(HELP_TEXT)
            continue

        if cmd == "/reset":
            agent.reset()
            print(f"{yellow('Historial borrado.')}\n")
            continue

        if cmd == "/history":
            if not agent.history:
                print(f"{dim('Sin historial en esta sesión.')}\n")
            else:
                for i, msg in enumerate(agent.history):
                    role = bold(blue("Tú")) if msg["role"] == "user" else bold(green("Pegaso"))
                    print(f"  {dim(str(i+1)+'.')} {role}: {msg['content'][:120]}")
                print()
            continue

        if cmd == "/system":
            user_input = "Dame información completa del sistema: CPU, memoria RAM, uso de disco y uptime."

        if cmd == "/ls":
            user_input = f"Lista el contenido del directorio actual: {os.getcwd()}"

        if cmd == "/organiza":
            folder = input(f"  {dim('¿Qué carpeta quieres organizar? ')}").strip()
            if not folder:
                print(f"{yellow('Ruta vacía, cancelado.')}\n")
                continue
            user_input = (
                f"Primero muéstrame el plan (dry_run=true) de organizar la carpeta '{folder}', "
                f"luego pregúntame si quiero continuar."
            )

        # Registrar en log
        session_log.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "user": user_input,
        })

        # Llamar al agente
        print(f"{dim('...')}", end="", flush=True)
        response = agent.chat(user_input)
        print("\r", end="")  # limpiar el "..."
        _print_response(response)

        session_log[-1]["response"] = response


def _run_oneshot(agent: PegasoAgent, message: str):
    """Modo un solo mensaje (para scripts o alias)."""
    response = agent.chat(message)
    print(response)


def main():
    parser = argparse.ArgumentParser(
        prog="pegaso",
        description="Pegaso — Asistente personal con Perplexity AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  pegaso
  pegaso "organiza ~/Descargas"
  pegaso "busca todos los PDFs en mi home"
  pegaso "¿cuánto espacio libre hay en disco?"
""",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Mensaje directo (sin esto → modo interactivo)",
    )
    parser.add_argument(
        "--model", "-m",
        default=os.getenv("PERPLEXITY_MODEL", "sonar-pro"),
        help="Modelo Perplexity (default: sonar-pro)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Sin logs de herramientas",
    )

    args = parser.parse_args()

    # Configurar modelo si se especificó
    if args.model:
        os.environ["PERPLEXITY_MODEL"] = args.model

    verbose = not args.quiet
    agent = PegasoAgent(verbose=verbose)

    if args.message:
        _run_oneshot(agent, args.message)
    else:
        _run_interactive(agent)


if __name__ == "__main__":
    main()
