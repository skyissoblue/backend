"""Lazy process-wide faster-whisper transcription."""
from __future__ import annotations
import os
from threading import Lock

_model = None
_lock = Lock()

def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from faster_whisper import WhisperModel
                _model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"), download_root=os.getenv("WHISPER_MODEL_DIR", "/models"))
    return _model

def transcribe(path: str) -> str:
    segments, _ = _get_model().transcribe(path, language="zh", vad_filter=True, beam_size=5)
    return "".join(segment.text for segment in segments).strip()
