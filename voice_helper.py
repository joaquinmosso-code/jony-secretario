"""
Transcripción de notas de voz para Jony, usando faster-whisper (Whisper
corriendo local en el propio servidor — sin cuenta, sin costo por uso,
sin mandar el audio a ningún servicio externo).

El modelo se descarga una sola vez (la primera vez que se usa) y después
queda cacheado en el servidor.
"""

import os

_modelo = None


def _get_modelo():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        tamano = os.getenv("WHISPER_MODEL_SIZE", "base")
        # compute_type int8: mucho más liviano en CPU, ideal para un servidor chico.
        _modelo = WhisperModel(tamano, device="cpu", compute_type="int8")
    return _modelo


def transcribir(ruta_audio: str) -> str:
    """Transcribe un archivo de audio (cualquier formato común: ogg, mp3, wav, etc.) a texto en español."""
    modelo = _get_modelo()
    segmentos, _info = modelo.transcribe(ruta_audio, language="es", vad_filter=True)
    return " ".join(seg.text.strip() for seg in segmentos).strip()
