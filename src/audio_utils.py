import base64
import binascii
from pathlib import Path
from typing import Any


OUTPUT_WAV_NAME = "voz_clonada.wav"
REFERENCE_AUDIO_BASENAME = "referencia_usuario"
DEFAULT_OUTPUT_DIR = Path("outputs")

MIME_EXTENSION_MAP = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
}


def validate_text(text: str | None) -> str:
    """Return stripped text or raise a clear UI-facing validation error."""
    normalized_text = (text or "").strip()
    if not normalized_text:
        raise ValueError("Digite um texto para gerar a voz clonada.")
    return normalized_text


def _coerce_audio_path(audio_path: Any) -> str | Path | None:
    if isinstance(audio_path, dict):
        return audio_path.get("path")

    if hasattr(audio_path, "path"):
        return audio_path.path

    return audio_path


def validate_audio_path(audio_path: str | Path | dict[str, Any] | Any | None) -> Path:
    """Return an existing reference audio path or raise a clear validation error."""
    audio_path = _coerce_audio_path(audio_path)

    if audio_path is None or not str(audio_path).strip():
        raise ValueError("Grave um audio pelo microfone ou envie um arquivo de referencia.")

    reference_path = Path(audio_path)
    if not reference_path.exists() or not reference_path.is_file():
        raise ValueError(f"Arquivo de audio nao encontrado: {reference_path}")

    if reference_path.stat().st_size == 0:
        raise ValueError("O audio gravado parece vazio. Grave novamente ou envie outro arquivo.")

    return reference_path


def get_output_wav_path(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path / OUTPUT_WAV_NAME


def save_reference_audio_from_data_url(data_url: str | None, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    if not data_url or not data_url.strip():
        raise ValueError("Grave um audio pelo microfone ou envie um arquivo de referencia.")

    try:
        metadata, encoded_audio = data_url.split(",", maxsplit=1)
        mime_type = metadata.removeprefix("data:").split(";", maxsplit=1)[0].lower()
        audio_bytes = base64.b64decode(encoded_audio, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Nao foi possivel ler o audio gravado. Grave novamente.") from exc

    if not audio_bytes:
        raise ValueError("O audio gravado parece vazio. Grave novamente ou envie outro arquivo.")

    extension = MIME_EXTENSION_MAP.get(mime_type, ".wav")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    reference_path = output_path / f"{REFERENCE_AUDIO_BASENAME}{extension}"
    reference_path.write_bytes(audio_bytes)

    return validate_audio_path(reference_path)
