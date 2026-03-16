"""
Pegaso Computer Tools — herramientas para control del ordenador.
Usadas por el agente Perplexity para gestión de archivos, sistema y comandos.
"""
import os
import re
import shutil
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────
# Configuración de seguridad
# ──────────────────────────────────────────────

# Comandos y patrones bloqueados
_BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=.*of=/dev/",
    r":\(\)\{.*\}",       # fork bomb
    r"chmod\s+777\s+/",
    r">/dev/sda",
    r"shutdown|poweroff|reboot",   # solo si no se confirma
    r"passwd\s+root",
]

# Extensiones por categoría para organizar carpetas
_CATEGORIES = {
    "Imagenes":     {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".heic", ".raw"},
    "Videos":       {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "Audio":        {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Documentos":   {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".rst"},
    "Hojas":        {".xls", ".xlsx", ".ods", ".csv"},
    "Presentaciones":{".ppt", ".pptx", ".odp"},
    "Codigo":       {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sh", ".bash",
                     ".c", ".cpp", ".h", ".java", ".go", ".rs", ".rb", ".php", ".yaml",
                     ".yml", ".json", ".toml", ".ini", ".env", ".sql"},
    "Comprimidos":  {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
    "Ejecutables":  {".exe", ".deb", ".rpm", ".AppImage", ".bin", ".run"},
    "ISO":          {".iso", ".img"},
}


def _is_safe_command(cmd: str) -> tuple[bool, str]:
    """Devuelve (es_seguro, motivo). Bloquea patrones peligrosos."""
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"Comando bloqueado por seguridad: patrón '{pattern}'"
    return True, ""


# ──────────────────────────────────────────────
# Herramientas
# ──────────────────────────────────────────────

def list_directory(path: str = ".", show_hidden: bool = False) -> dict[str, Any]:
    """Lista el contenido de un directorio con detalles."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {"error": f"Ruta no encontrada: {path}"}
    if not target.is_dir():
        return {"error": f"No es un directorio: {path}"}
    entries = []
    try:
        for item in sorted(target.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            stat = item.stat()
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size_kb": round(stat.st_size / 1024, 1) if item.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        return {"path": str(target), "count": len(entries), "entries": entries}
    except PermissionError:
        return {"error": f"Sin permisos para leer: {path}"}


def organize_folder(path: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Organiza una carpeta moviendo archivos a subcarpetas por tipo.
    dry_run=True muestra qué haría sin moverlo.
    """
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {"error": f"Ruta no encontrada: {path}"}
    if not target.is_dir():
        return {"error": f"No es un directorio: {path}"}

    plan = []
    moved = 0
    skipped = 0

    for item in target.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        ext = item.suffix.lower()
        dest_folder = None
        for category, extensions in _CATEGORIES.items():
            if ext in extensions:
                dest_folder = category
                break
        if not dest_folder:
            dest_folder = "Otros"

        dest_path = target / dest_folder / item.name
        plan.append({
            "file": item.name,
            "from": str(item),
            "to": str(dest_path),
            "category": dest_folder,
        })

        if not dry_run:
            dest_dir = target / dest_folder
            dest_dir.mkdir(exist_ok=True)
            try:
                shutil.move(str(item), str(dest_path))
                moved += 1
            except Exception as e:
                plan[-1]["error"] = str(e)
                skipped += 1

    return {
        "path": str(target),
        "dry_run": dry_run,
        "total_files": len(plan),
        "moved": moved if not dry_run else 0,
        "plan": plan[:50],  # máximo 50 entradas en la respuesta
    }


def move_file(source: str, destination: str) -> dict[str, Any]:
    """Mueve o renombra un archivo/carpeta."""
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()
    if not src.exists():
        return {"error": f"Origen no encontrado: {source}"}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"success": True, "from": str(src), "to": str(dst)}
    except Exception as e:
        return {"error": str(e)}


def copy_file(source: str, destination: str) -> dict[str, Any]:
    """Copia un archivo o carpeta."""
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()
    if not src.exists():
        return {"error": f"Origen no encontrado: {source}"}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return {"success": True, "from": str(src), "to": str(dst)}
    except Exception as e:
        return {"error": str(e)}


def delete_file(path: str, force: bool = False) -> dict[str, Any]:
    """Elimina un archivo o carpeta. force=True para carpetas no vacías."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {"error": f"No encontrado: {path}"}
    try:
        if target.is_dir():
            if force:
                shutil.rmtree(str(target))
            else:
                target.rmdir()  # solo si está vacía
        else:
            target.unlink()
        return {"success": True, "deleted": str(target)}
    except Exception as e:
        return {"error": str(e)}


def create_folder(path: str) -> dict[str, Any]:
    """Crea una carpeta (y las padres necesarias)."""
    target = Path(path).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        return {"success": True, "created": str(target)}
    except Exception as e:
        return {"error": str(e)}


def read_file(path: str, max_lines: int = 200) -> dict[str, Any]:
    """Lee el contenido de un archivo de texto."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {"error": f"Archivo no encontrado: {path}"}
    if not target.is_file():
        return {"error": f"No es un archivo: {path}"}
    size = target.stat().st_size
    if size > 2 * 1024 * 1024:  # 2MB
        return {"error": "Archivo demasiado grande (>2MB). Usa un editor."}
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        truncated = len(lines) > max_lines
        return {
            "path": str(target),
            "lines": len(lines),
            "truncated": truncated,
            "content": "\n".join(lines[:max_lines]),
        }
    except Exception as e:
        return {"error": str(e)}


def write_file(path: str, content: str, append: bool = False) -> dict[str, Any]:
    """Escribe contenido en un archivo."""
    target = Path(path).expanduser().resolve()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": str(target), "size_kb": round(target.stat().st_size / 1024, 1)}
    except Exception as e:
        return {"error": str(e)}


def find_files(pattern: str, directory: str = "~", file_type: str = "both") -> dict[str, Any]:
    """
    Busca archivos por nombre/extensión.
    file_type: 'file', 'dir', 'both'
    """
    base = Path(directory).expanduser().resolve()
    results = []
    try:
        for item in base.rglob(pattern):
            if file_type == "file" and not item.is_file():
                continue
            if file_type == "dir" and not item.is_dir():
                continue
            results.append(str(item))
            if len(results) >= 100:
                break
        return {"pattern": pattern, "base": str(base), "found": len(results), "results": results}
    except Exception as e:
        return {"error": str(e)}


def run_shell(command: str, timeout: int = 30, cwd: str = None) -> dict[str, Any]:
    """
    Ejecuta un comando de shell.
    Bloquea patrones peligrosos automáticamente.
    """
    safe, reason = _is_safe_command(command)
    if not safe:
        return {"error": reason, "blocked": True}

    work_dir = Path(cwd).expanduser().resolve() if cwd else Path.home()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(work_dir),
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout tras {timeout}s", "command": command}
    except Exception as e:
        return {"error": str(e), "command": command}


def get_system_info() -> dict[str, Any]:
    """Devuelve info del sistema: CPU, memoria, disco, red."""
    info = {}
    # CPU
    r = subprocess.run(
        ["top", "-bn1"], capture_output=True, text=True, timeout=5
    )
    for line in r.stdout.splitlines():
        if "Cpu(s)" in line or "%Cpu" in line:
            info["cpu"] = line.strip()
            break
    # Memoria
    r2 = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
    info["memory"] = r2.stdout.strip()
    # Disco
    r3 = subprocess.run(["df", "-h", "--output=target,size,used,avail,pcent"],
                        capture_output=True, text=True, timeout=5)
    info["disk"] = r3.stdout.strip()
    # Hostname y uptime
    info["hostname"] = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    info["uptime"] = subprocess.run(["uptime", "-p"], capture_output=True, text=True).stdout.strip()
    return info


def open_application(name: str) -> dict[str, Any]:
    """Abre una aplicación por nombre."""
    try:
        subprocess.Popen(
            [name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"success": True, "launched": name}
    except FileNotFoundError:
        # Intentar con xdg-open o gtk-launch
        r = subprocess.run(["which", name], capture_output=True, text=True)
        if not r.stdout.strip():
            return {"error": f"Aplicación '{name}' no encontrada en PATH"}
        return {"error": f"No se pudo lanzar: {name}"}
    except Exception as e:
        return {"error": str(e)}


def disk_usage(path: str = "~") -> dict[str, Any]:
    """Muestra el uso de disco de un directorio (top 10 subcarpetas más grandes)."""
    target = Path(path).expanduser().resolve()
    r = subprocess.run(
        ["du", "-sh", "--max-depth=1", str(target)],
        capture_output=True, text=True, timeout=30
    )
    lines = sorted(
        [l for l in r.stdout.splitlines() if l],
        key=lambda x: x.split("\t")[0],
        reverse=True
    )
    return {"path": str(target), "sizes": lines[:15]}


# ──────────────────────────────────────────────
# Registry de herramientas para el agente
# ──────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "list_directory":   list_directory,
    "organize_folder":  organize_folder,
    "move_file":        move_file,
    "copy_file":        copy_file,
    "delete_file":      delete_file,
    "create_folder":    create_folder,
    "read_file":        read_file,
    "write_file":       write_file,
    "find_files":       find_files,
    "run_shell":        run_shell,
    "get_system_info":  get_system_info,
    "open_application": open_application,
    "disk_usage":       disk_usage,
}

# Esquemas OpenAI-compatible para tool calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lista el contenido de un directorio con tamaños y fechas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del directorio (ej: ~/Documentos)"},
                    "show_hidden": {"type": "boolean", "description": "Mostrar archivos ocultos", "default": False},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "organize_folder",
            "description": "Organiza automáticamente una carpeta moviendo archivos a subcarpetas por tipo (Imagenes, Videos, Documentos, Codigo, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Carpeta a organizar"},
                    "dry_run": {"type": "boolean", "description": "Si true, solo muestra el plan sin mover nada", "default": False},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Mueve o renombra un archivo o carpeta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Ruta origen"},
                    "destination": {"type": "string", "description": "Ruta destino"},
                },
                "required": ["source", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copia un archivo o carpeta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Ruta origen"},
                    "destination": {"type": "string", "description": "Ruta destino"},
                },
                "required": ["source", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Elimina un archivo o carpeta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta a eliminar"},
                    "force": {"type": "boolean", "description": "Eliminar carpetas no vacías", "default": False},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Crea una carpeta y las carpetas padre necesarias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta de la carpeta a crear"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee el contenido de un archivo de texto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"},
                    "max_lines": {"type": "integer", "description": "Máximo de líneas a leer", "default": 200},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe o crea un archivo de texto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"},
                    "content": {"type": "string", "description": "Contenido a escribir"},
                    "append": {"type": "boolean", "description": "Añadir al final en vez de sobrescribir", "default": False},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Busca archivos por nombre o patrón glob (ej: '*.pdf', '*.py').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Patrón glob (ej: '*.pdf')"},
                    "directory": {"type": "string", "description": "Directorio base de búsqueda", "default": "~"},
                    "file_type": {"type": "string", "enum": ["file", "dir", "both"], "default": "both"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Ejecuta un comando de terminal. Bloqueados automáticamente los comandos destructivos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando a ejecutar"},
                    "timeout": {"type": "integer", "description": "Timeout en segundos", "default": 30},
                    "cwd": {"type": "string", "description": "Directorio de trabajo"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Obtiene información del sistema: CPU, memoria, disco, hostname y uptime.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Abre una aplicación del sistema (ej: 'firefox', 'code', 'nautilus').",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del ejecutable"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disk_usage",
            "description": "Muestra el uso de disco de un directorio y sus subcarpetas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directorio a analizar", "default": "~"},
                },
                "required": [],
            },
        },
    },
]
