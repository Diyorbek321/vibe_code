"""
Speech-to-Text service.

Strategy:
  - WHISPER_BACKEND=local  → faster-whisper runs fully offline (GPU/CPU)
  - WHISPER_BACKEND=openai → audio sent to an OpenAI-compatible Whisper API
                             (works with OpenAI AND Groq whisper-large-v3)

`load_whisper_model()` is called once at startup and the result stored on
app.state.  Individual transcription calls use the already-loaded model.

Groq fix: _transcribe_openai now uses OPENAI_BASE_URL + OPENAI_API_KEY from
settings, so Groq's endpoint is used when configured.
"""
import asyncio
import io
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Model loading ──────────────────────────────────────────────────────────────

async def load_whisper_model() -> Any:
    """
    Returns a model handle (WhisperModel instance or the string "openai").
    Stored on app.state.whisper_model so it's loaded once and reused.
    """
    if settings.WHISPER_BACKEND == "local":
        from faster_whisper import WhisperModel  # type: ignore
        logger.info("Loading faster-whisper model '%s' …", settings.WHISPER_MODEL_SIZE)
        model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device="auto",       # uses CUDA if available, falls back to CPU
            compute_type="int8", # smallest memory footprint
        )
        logger.info("faster-whisper model ready")
        return model
    else:
        provider = "Groq" if (settings.OPENAI_BASE_URL and "groq" in settings.OPENAI_BASE_URL) else "OpenAI"
        logger.info("STT backend: %s Whisper API (model=%s)", provider, settings.WHISPER_MODEL)
        return "openai"


# ── Transcription entry point ──────────────────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, model_handle: Any) -> str:
    """
    Accepts raw audio bytes (OGG from Telegram, or any format Whisper accepts).
    Returns the transcribed text string.
    Raises RuntimeError on failure.
    """
    if model_handle == "openai":
        return await _transcribe_openai(audio_bytes)
    return await _transcribe_local(audio_bytes, model_handle)


# ── Local faster-whisper ───────────────────────────────────────────────────────

async def _transcribe_local(audio_bytes: bytes, model: Any) -> str:
    """Run faster-whisper in a thread to avoid blocking the event loop."""

    def _run() -> str:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            segments, info = model.transcribe(
                tmp_path,
                language=settings.WHISPER_LANGUAGE,
                beam_size=5,
                vad_filter=True,
            )
            text = " ".join(seg.text.strip() for seg in segments)
            logger.debug(
                "faster-whisper: %d chars (lang=%s prob=%.2f)",
                len(text), info.language, info.language_probability,
            )
            return text.strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return await asyncio.to_thread(_run)


# ── OpenAI-compatible Whisper API (OpenAI or Groq) ────────────────────────────

async def _transcribe_openai(audio_bytes: bytes) -> str:
    """
    Send audio to an OpenAI-compatible Whisper endpoint.

    Uses OPENAI_BASE_URL from settings so Groq works automatically:
      OPENAI_BASE_URL=https://api.groq.com/openai/v1
      WHISPER_MODEL=whisper-large-v3   (Groq supports this)
      or
      WHISPER_MODEL=whisper-1          (OpenAI default)
    """
    from openai import AsyncOpenAI

    # Build client with same base_url used for LLM calls
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,  # None → default OpenAI endpoint
    )

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice.ogg"

    try:
        response = await client.audio.transcriptions.create(
            model=settings.WHISPER_MODEL,
            file=audio_file,
            language=settings.WHISPER_LANGUAGE or "uz",
            response_format="text",
        )
        # Some SDK versions return a string directly, others return an object
        text = response if isinstance(response, str) else getattr(response, "text", str(response))
        text = text.strip()
        logger.debug("Whisper API: %d chars", len(text))
        return text

    except Exception as exc:
        err = str(exc).lower()
        logger.error("Whisper API transcription failed: %s", exc)

        if "model_not_found" in err or "not found" in err:
            raise RuntimeError(
                f"Whisper model '{settings.WHISPER_MODEL}' not supported by this provider. "
                "For Groq use WHISPER_MODEL=whisper-large-v3"
            ) from exc
        if "quota" in err or "billing" in err or "rate" in err:
            raise RuntimeError("whisper_quota") from exc
        if "auth" in err or "api key" in err or "unauthorized" in err:
            raise RuntimeError("whisper_auth") from exc

        raise RuntimeError(f"Transcription failed: {exc}") from exc
