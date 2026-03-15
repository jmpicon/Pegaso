import os
import io
import tempfile
import subprocess
from pathlib import Path

# STT: faster-whisper
try:
    from faster_whisper import WhisperModel
    _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    WHISPER_AVAILABLE = True
except Exception as e:
    print(f"[VOICE] faster-whisper no disponible: {e}")
    _whisper_model = None
    WHISPER_AVAILABLE = False


def transcribe_audio(audio_bytes: bytes, language: str = "es") -> str:
    """Transcribe audio bytes a texto usando faster-whisper."""
    if not WHISPER_AVAILABLE or _whisper_model is None:
        return "[STT no disponible — instala faster-whisper]"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = _whisper_model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip() or "[Audio sin contenido detectado]"
    finally:
        os.unlink(tmp_path)


def text_to_speech(text: str, output_path: str | None = None) -> bytes | None:
    """Convierte texto a audio usando espeak-ng (100% offline)."""
    if output_path is None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

    try:
        result = subprocess.run(
            [
                "espeak-ng",
                "-v", "es",
                "-s", "140",  # velocidad: 140 palabras/min
                "-a", "100",  # amplitud
                "-w", output_path,
                text,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            with open(output_path, "rb") as f:
                audio_data = f.read()
            os.unlink(output_path)
            return audio_data
        else:
            print(f"[TTS] espeak-ng error: {result.stderr.decode()}")
            return None
    except FileNotFoundError:
        print("[TTS] espeak-ng no encontrado. Instala: apt install espeak-ng")
        return None
    except Exception as e:
        print(f"[TTS] Error inesperado: {e}")
        return None
