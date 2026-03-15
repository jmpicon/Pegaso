"""
Watcher incremental del Vault de Pegaso.
Detecta cambios en archivos y los indexa automáticamente,
con debouncing para evitar re-indexaciones repetitivas.
"""
import os
import sys
import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.services.rag_service import rag_service, SUPPORTED_EXTENSIONS
from src.core.permissions import permissions

DEBOUNCE_SECONDS = 2.0  # Espera 2 segundos antes de indexar


class DebouncedVaultWatcher(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._pending: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, path: str):
        with self._lock:
            # Cancelar timer previo para este archivo (debounce)
            if path in self._pending:
                self._pending[path].cancel()
            timer = threading.Timer(DEBOUNCE_SECONDS, self._index, args=[path])
            self._pending[path] = timer
            timer.start()

    def _index(self, path: str):
        with self._lock:
            self._pending.pop(path, None)

        if not os.path.exists(path):
            return
        if Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        if not permissions.is_path_allowed(os.path.dirname(path)):
            print(f"[Watcher] Ruta no permitida, ignorando: {path}")
            return

        print(f"[Watcher] Indexando: {Path(path).name}")
        result = rag_service.index_file(path)
        print(f"[Watcher] Resultado: {result}")

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._schedule(event.dest_path)


if __name__ == "__main__":
    vault_path = os.getenv("ALLOWLIST_PATH", "/app/data/vault")
    os.makedirs(vault_path, exist_ok=True)

    print(f"[Watcher] Iniciando indexación completa de {vault_path}...")
    rag_service.index_folder(vault_path)
    print("[Watcher] Indexación inicial completada. Observando cambios...")

    event_handler = DebouncedVaultWatcher()
    observer = Observer()
    observer.schedule(event_handler, vault_path, recursive=True)
    observer.start()

    print(f"[Watcher] Vigilando {vault_path} — soporta: {SUPPORTED_EXTENSIONS}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
