"""
Pegaso Computer Tools v2 — Control total del sistema para el asistente IA.
Herramientas: archivos, procesos, red, notificaciones, portapapeles,
              capturas de pantalla, ventanas, servicios del sistema.
"""
import os
import re
import shutil
import subprocess
import json
import signal
from datetime import datetime
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────
# Seguridad
# ──────────────────────────────────────────────
_BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=.*of=/dev/",
    r":\(\)\{.*\}",
    r"chmod\s+777\s+/",
    r">/dev/sda",
    r"passwd\s+root",
    r"curl.*\|\s*bash",
    r"wget.*\|\s*sh",
]

_CATEGORIES = {
    "Imagenes":       {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".heic", ".raw", ".tiff"},
    "Videos":         {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"},
    "Audio":          {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"},
    "Documentos":     {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".rst", ".tex"},
    "Hojas":          {".xls", ".xlsx", ".ods", ".csv"},
    "Presentaciones": {".ppt", ".pptx", ".odp"},
    "Codigo":         {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sh", ".bash",
                       ".c", ".cpp", ".h", ".java", ".go", ".rs", ".rb", ".php", ".yaml",
                       ".yml", ".json", ".toml", ".ini", ".env", ".sql", ".kt", ".swift"},
    "Comprimidos":    {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".zst"},
    "Ejecutables":    {".exe", ".deb", ".rpm", ".AppImage", ".bin", ".run", ".flatpak"},
    "ISO":            {".iso", ".img"},
    "Fuentes":        {".ttf", ".otf", ".woff", ".woff2"},
}


def _is_safe_command(cmd: str) -> tuple[bool, str]:
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"Comando bloqueado: patrón '{pattern}'"
    return True, ""


def _run(cmd: list[str], timeout: int = 10) -> str:
    """Ejecuta un comando y devuelve stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


# ──────────────────────────────────────────────
# Herramientas de archivos
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
    """Organiza carpeta moviendo archivos a subcarpetas por tipo."""
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
        dest_folder = next(
            (cat for cat, exts in _CATEGORIES.items() if ext in exts),
            "Otros"
        )
        dest_path = target / dest_folder / item.name
        plan.append({"file": item.name, "from": str(item), "to": str(dest_path), "category": dest_folder})

        if not dry_run:
            (target / dest_folder).mkdir(exist_ok=True)
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
        "plan": plan[:50],
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
    """Elimina un archivo o carpeta."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {"error": f"No encontrado: {path}"}
    try:
        if target.is_dir():
            shutil.rmtree(str(target)) if force else target.rmdir()
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
    if target.stat().st_size > 2 * 1024 * 1024:
        return {"error": "Archivo demasiado grande (>2MB)."}
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        truncated = len(lines) > max_lines
        return {"path": str(target), "lines": len(lines), "truncated": truncated,
                "content": "\n".join(lines[:max_lines])}
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
    """Busca archivos por nombre/extensión."""
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


def disk_usage(path: str = "~") -> dict[str, Any]:
    """Uso de disco de un directorio (top 15 subcarpetas)."""
    target = Path(path).expanduser().resolve()
    r = subprocess.run(
        ["du", "-sh", "--max-depth=1", str(target)],
        capture_output=True, text=True, timeout=30
    )
    lines = sorted(
        [l for l in r.stdout.splitlines() if l],
        key=lambda x: x.split("\t")[0], reverse=True
    )
    return {"path": str(target), "sizes": lines[:15]}


# ──────────────────────────────────────────────
# Herramientas de shell y sistema
# ──────────────────────────────────────────────

def run_shell(command: str, timeout: int = 30, cwd: str = None) -> dict[str, Any]:
    """Ejecuta un comando de shell con protección de seguridad."""
    safe, reason = _is_safe_command(command)
    if not safe:
        return {"error": reason, "blocked": True}
    work_dir = Path(cwd).expanduser().resolve() if cwd else Path.home()
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(work_dir),
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout tras {timeout}s", "command": command}
    except Exception as e:
        return {"error": str(e), "command": command}


def get_system_info() -> dict[str, Any]:
    """Info del sistema: CPU, memoria, disco, red, hostname."""
    info = {}
    try:
        r = subprocess.run(["top", "-bn1"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "Cpu(s)" in line or "%Cpu" in line:
                info["cpu"] = line.strip()
                break
    except Exception:
        pass

    info["memory"] = _run(["free", "-h"])
    info["disk"] = _run(["df", "-h", "--output=target,size,used,avail,pcent"])
    info["hostname"] = _run(["hostname"])
    info["uptime"] = _run(["uptime", "-p"])
    info["kernel"] = _run(["uname", "-r"])
    info["os"] = _run(["lsb_release", "-ds"])
    return info


def open_application(name: str) -> dict[str, Any]:
    """Abre una aplicación del sistema."""
    try:
        subprocess.Popen(
            [name], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        return {"success": True, "launched": name}
    except FileNotFoundError:
        # Intentar con gtk-launch para apps de escritorio
        r = subprocess.run(["gtk-launch", name], capture_output=True, text=True)
        if r.returncode == 0:
            return {"success": True, "launched": name, "method": "gtk-launch"}
        return {"error": f"Aplicación '{name}' no encontrada en PATH"}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Gestión de procesos
# ──────────────────────────────────────────────

def list_processes(filter_name: str = "", sort_by: str = "cpu", limit: int = 20) -> dict[str, Any]:
    """Lista procesos del sistema con filtrado."""
    sort_flag = {"cpu": "-%cpu", "mem": "-%mem", "pid": "pid"}.get(sort_by, "-%cpu")
    try:
        ps = subprocess.run(
            ["ps", "aux", f"--sort={sort_flag}", "--no-header"],
            capture_output=True, text=True, timeout=10
        )
        procs = []
        for line in ps.stdout.splitlines():
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            cmd = parts[10][:80]
            if filter_name and filter_name.lower() not in cmd.lower():
                continue
            procs.append({
                "user": parts[0], "pid": int(parts[1]),
                "cpu_pct": float(parts[2]), "mem_pct": float(parts[3]),
                "stat": parts[7], "cmd": cmd,
            })
            if len(procs) >= limit:
                break
        return {"processes": procs, "count": len(procs)}
    except Exception as e:
        return {"error": str(e)}


def kill_process(pid: int, force: bool = False) -> dict[str, Any]:
    """
    Envía señal a un proceso.
    force=False → SIGTERM (cierre limpio)
    force=True  → SIGKILL (cierre forzado)
    """
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
        return {
            "success": True,
            "pid": pid,
            "signal": "SIGKILL" if force else "SIGTERM",
        }
    except ProcessLookupError:
        return {"error": f"Proceso {pid} no encontrado"}
    except PermissionError:
        return {"error": f"Sin permisos para señalizar PID {pid}"}
    except Exception as e:
        return {"error": str(e)}


def get_running_services(filter_name: str = "") -> dict[str, Any]:
    """Lista servicios systemd activos."""
    try:
        cmd = ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        services = []
        for line in r.stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            name = parts[0]
            if filter_name and filter_name.lower() not in name.lower():
                continue
            services.append({
                "name": name,
                "load": parts[1],
                "active": parts[2],
                "sub": parts[3],
                "description": parts[4].strip() if len(parts) > 4 else "",
            })
        return {"services": services, "count": len(services)}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Red
# ──────────────────────────────────────────────

def network_info() -> dict[str, Any]:
    """Estado de red: interfaces, IP, WiFi, conectividad."""
    info = {}

    # Interfaces y direcciones IP
    ip_out = _run(["ip", "-j", "addr"])
    if ip_out:
        try:
            ifaces = json.loads(ip_out)
            interfaces = []
            for iface in ifaces:
                addrs = [
                    {"family": a.get("family"), "addr": a.get("local"), "prefix": a.get("prefixlen")}
                    for a in iface.get("addr_info", [])
                ]
                interfaces.append({
                    "name": iface.get("ifname"),
                    "state": iface.get("operstate"),
                    "mac": iface.get("address"),
                    "addresses": addrs,
                })
            info["interfaces"] = interfaces
        except Exception:
            info["ip_raw"] = ip_out[:500]

    # WiFi
    wifi = _run(["nmcli", "-t", "-f", "DEVICE,SSID,SIGNAL,SECURITY", "dev", "wifi"])
    if wifi:
        info["wifi_networks"] = wifi.splitlines()[:10]

    # Conexión activa
    active = _run(["nmcli", "-t", "-f", "NAME,TYPE,STATE,DEVICE", "con", "show", "--active"])
    if active:
        info["active_connections"] = active.splitlines()

    # Latencia a internet
    ping_out = _run(["ping", "-c", "1", "-W", "2", "8.8.8.8"])
    info["internet_reachable"] = "time=" in ping_out
    if "time=" in ping_out:
        for part in ping_out.split():
            if part.startswith("time="):
                info["ping_ms"] = part.replace("time=", "")
                break

    return info


def ping_host(host: str, count: int = 3) -> dict[str, Any]:
    """Hace ping a un host y devuelve latencia."""
    try:
        r = subprocess.run(
            ["ping", "-c", str(count), "-W", "3", host],
            capture_output=True, text=True, timeout=15,
        )
        output = r.stdout + r.stderr
        success = r.returncode == 0
        return {
            "host": host,
            "reachable": success,
            "output": output.strip()[-300:],
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Notificaciones y portapapeles
# ──────────────────────────────────────────────

def send_notification(title: str, message: str, urgency: str = "normal", icon: str = "") -> dict[str, Any]:
    """
    Envía una notificación de escritorio via notify-send.
    urgency: 'low' | 'normal' | 'critical'
    """
    valid_urgencies = {"low", "normal", "critical"}
    if urgency not in valid_urgencies:
        urgency = "normal"
    cmd = ["notify-send", "-u", urgency]
    if icon:
        cmd += ["-i", icon]
    cmd += [title, message]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return {"success": r.returncode == 0, "title": title, "urgency": urgency}
    except FileNotFoundError:
        return {"error": "notify-send no disponible. Instala: sudo apt install libnotify-bin"}
    except Exception as e:
        return {"error": str(e)}


def get_clipboard() -> dict[str, Any]:
    """Lee el contenido del portapapeles (X11/Wayland)."""
    # Probar xclip, xsel, wl-paste en orden
    for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"], ["wl-paste"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return {"content": r.stdout[:5000], "tool": cmd[0]}
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return {"error": "No hay herramienta de portapapeles disponible (instala xclip, xsel o wl-clipboard)"}


def set_clipboard(content: str) -> dict[str, Any]:
    """Escribe contenido en el portapapeles (X11/Wayland)."""
    for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["wl-copy"]]:
        try:
            r = subprocess.run(cmd, input=content, capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return {"success": True, "tool": cmd[0], "chars": len(content)}
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return {"error": "No hay herramienta de portapapeles disponible"}


# ──────────────────────────────────────────────
# Pantalla y ventanas
# ──────────────────────────────────────────────

def take_screenshot(path: str = "", full_screen: bool = True) -> dict[str, Any]:
    """
    Captura de pantalla.
    Requiere: scrot, gnome-screenshot, o spectacle.
    """
    if not path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(Path.home() / f"Escritorio/screenshot_{ts}.png")
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    # Intentar varias herramientas
    tools = [
        ["scrot", path],
        ["gnome-screenshot", "-f", path],
        ["spectacle", "-b", "-o", path],
        ["import", "-window", "root", path],  # ImageMagick
    ]
    for cmd in tools:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and Path(path).exists():
                size = Path(path).stat().st_size
                return {"success": True, "path": path, "size_kb": round(size / 1024, 1), "tool": cmd[0]}
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return {"error": "No se encontró herramienta de captura (instala scrot: sudo apt install scrot)"}


def list_windows() -> dict[str, Any]:
    """Lista ventanas abiertas del escritorio (requiere wmctrl)."""
    try:
        r = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return {"error": "wmctrl falló — instala: sudo apt install wmctrl"}
        windows = []
        for line in r.stdout.splitlines():
            parts = line.split(None, 3)
            if len(parts) >= 4:
                windows.append({
                    "wid": parts[0],
                    "desktop": parts[1],
                    "host": parts[2],
                    "title": parts[3],
                })
        return {"windows": windows, "count": len(windows)}
    except FileNotFoundError:
        return {"error": "wmctrl no disponible — instala: sudo apt install wmctrl"}
    except Exception as e:
        return {"error": str(e)}


def focus_window(title_pattern: str) -> dict[str, Any]:
    """Enfoca una ventana por patrón de título (wmctrl)."""
    try:
        r = subprocess.run(
            ["wmctrl", "-a", title_pattern],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return {"success": True, "focused": title_pattern}
        return {"error": f"No se encontró ventana con título '{title_pattern}'"}
    except FileNotFoundError:
        return {"error": "wmctrl no disponible — instala: sudo apt install wmctrl"}
    except Exception as e:
        return {"error": str(e)}


def set_volume(level: int) -> dict[str, Any]:
    """Establece el volumen del sistema (0-100) via pactl/amixer."""
    level = max(0, min(100, level))
    try:
        r = subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return {"success": True, "volume": level}
    except FileNotFoundError:
        pass
    # Fallback a amixer
    try:
        r = subprocess.run(
            ["amixer", "sset", "Master", f"{level}%"],
            capture_output=True, text=True, timeout=5,
        )
        return {"success": r.returncode == 0, "volume": level}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Registry de herramientas
# ──────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "list_directory":       list_directory,
    "organize_folder":      organize_folder,
    "move_file":            move_file,
    "copy_file":            copy_file,
    "delete_file":          delete_file,
    "create_folder":        create_folder,
    "read_file":            read_file,
    "write_file":           write_file,
    "find_files":           find_files,
    "run_shell":            run_shell,
    "get_system_info":      get_system_info,
    "open_application":     open_application,
    "disk_usage":           disk_usage,
    # Nuevas v2
    "list_processes":       list_processes,
    "kill_process":         kill_process,
    "get_running_services": get_running_services,
    "network_info":         network_info,
    "ping_host":            ping_host,
    "send_notification":    send_notification,
    "get_clipboard":        get_clipboard,
    "set_clipboard":        set_clipboard,
    "take_screenshot":      take_screenshot,
    "list_windows":         list_windows,
    "focus_window":         focus_window,
    "set_volume":           set_volume,
}

# Schemas OpenAI-compatible
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
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
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
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
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
                    "path": {"type": "string"},
                    "force": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Crea una carpeta y sus padres necesarios.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
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
                    "path": {"type": "string"},
                    "max_lines": {"type": "integer", "default": 200},
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
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean", "default": False},
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
                    "pattern": {"type": "string"},
                    "directory": {"type": "string", "default": "~"},
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
            "description": "Ejecuta un comando de terminal (comandos destructivos bloqueados automáticamente).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 30},
                    "cwd": {"type": "string"},
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
            "description": "Abre una aplicación del sistema (ej: 'firefox', 'code', 'nautilus', 'thunderbird').",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
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
                "properties": {"path": {"type": "string", "default": "~"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Lista procesos del sistema con uso de CPU y memoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_name": {"type": "string", "description": "Filtrar por nombre de proceso", "default": ""},
                    "sort_by": {"type": "string", "enum": ["cpu", "mem", "pid"], "default": "cpu"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "Envía señal de cierre a un proceso por PID. force=False cierre limpio, force=True cierre forzado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer"},
                    "force": {"type": "boolean", "default": False},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_running_services",
            "description": "Lista servicios systemd activos en el sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_name": {"type": "string", "default": ""},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "network_info",
            "description": "Estado de red: interfaces, direcciones IP, WiFi activo, conectividad a internet.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ping_host",
            "description": "Hace ping a un host y mide latencia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "count": {"type": "integer", "default": 3},
                },
                "required": ["host"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Envía una notificación de escritorio al usuario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["low", "normal", "critical"], "default": "normal"},
                    "icon": {"type": "string", "default": ""},
                },
                "required": ["title", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clipboard",
            "description": "Lee el contenido actual del portapapeles del sistema.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_clipboard",
            "description": "Escribe texto en el portapapeles del sistema.",
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Captura la pantalla completa y guarda en archivo PNG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta donde guardar (default: Escritorio)"},
                    "full_screen": {"type": "boolean", "default": True},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "Lista todas las ventanas abiertas del escritorio con sus títulos.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "Lleva al frente una ventana por su título o parte del título.",
            "parameters": {
                "type": "object",
                "properties": {"title_pattern": {"type": "string"}},
                "required": ["title_pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Establece el volumen del sistema (0-100).",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "Nivel de volumen 0-100"}},
                "required": ["level"],
            },
        },
    },
]
