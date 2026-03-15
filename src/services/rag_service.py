import os
import hashlib
from pathlib import Path
from typing import List, Dict

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from src.core.permissions import permissions

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_file(path: str) -> str:
    """Carga texto de cualquier formato soportado."""
    ext = Path(path).suffix.lower()
    try:
        if ext == ".txt" or ext == ".md":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        elif ext == ".docx":
            import docx
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        print(f"[RAG] Error leyendo {path}: {e}")
    return ""


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Divide texto en chunks con overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


class RAGService:
    def __init__(self):
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.collection_name = "vault_memory"
        self._init_collection()

    def _init_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            try:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
            except Exception as e:
                # 409 Conflict = la colección ya existe, ignorar
                if "already exists" not in str(e).lower() and "409" not in str(e):
                    raise

    def index_file(self, file_path: str) -> Dict:
        """Indexa un único archivo de forma incremental."""
        if not permissions.is_path_allowed(os.path.dirname(file_path)):
            return {"error": f"Ruta no permitida: {file_path}"}

        ext = Path(file_path).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return {"skipped": f"Extensión no soportada: {ext}"}

        try:
            file_hash = _hash_file(file_path)
        except Exception as e:
            return {"error": f"No se puede leer {file_path}: {e}"}

        # Comprobar si ya está indexado con el mismo hash (desde Qdrant payload)
        text = _load_file(file_path)
        if not text.strip():
            return {"skipped": f"Archivo vacío: {file_path}"}

        chunks = _split_text(text)
        points = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            vector = self.model.encode(chunk).tolist()
            point_id = abs(hash(file_path + str(i) + file_hash)) % (10**15)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "content": chunk,
                        "source": file_path,
                        "file_hash": file_hash,
                        "chunk_index": i,
                    },
                )
            )

        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

        print(f"[RAG] Indexados {len(points)} chunks de {Path(file_path).name}")
        return {"status": "ok", "file": file_path, "chunks": len(points)}

    def index_folder(self, folder_path: str) -> Dict:
        """Indexa todos los archivos soportados en una carpeta."""
        if not permissions.is_path_allowed(folder_path):
            return {"error": f"Ruta no permitida: {folder_path}"}

        results = {"indexed": 0, "skipped": 0, "errors": 0}
        for p in Path(folder_path).rglob("*"):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                result = self.index_file(str(p))
                if "error" in result:
                    results["errors"] += 1
                elif "skipped" in result:
                    results["skipped"] += 1
                else:
                    results["indexed"] += 1
        return results

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Busca chunks relevantes en el vault."""
        vector = self.model.encode(query).tolist()
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
            )
            return [res.payload for res in results]
        except Exception as e:
            print(f"[RAG] Error en búsqueda: {e}")
            return []


rag_service = RAGService()
