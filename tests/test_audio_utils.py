from pathlib import Path
import base64
import shutil
import sys
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.audio_utils import (
    OUTPUT_WAV_NAME,
    REFERENCE_AUDIO_BASENAME,
    get_output_wav_path,
    save_reference_audio_from_data_url,
    validate_audio_path,
    validate_text,
)


def make_test_dir() -> Path:
    test_dir = PROJECT_ROOT / "outputs" / f"test-{uuid4().hex}"
    test_dir.mkdir(parents=True, exist_ok=False)
    return test_dir


def test_validate_text_returns_stripped_text():
    assert validate_text("  Ola, esta e uma demonstracao.  ") == "Ola, esta e uma demonstracao."


def test_validate_text_rejects_empty_text():
    with pytest.raises(ValueError, match="Digite um texto"):
        validate_text("   ")


def test_validate_audio_path_accepts_existing_file():
    test_dir = make_test_dir()
    try:
        audio_file = test_dir / "referencia.wav"
        audio_file.write_bytes(b"RIFF")

        assert validate_audio_path(str(audio_file)) == audio_file
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_validate_audio_path_accepts_gradio_filedata_dict():
    test_dir = make_test_dir()
    try:
        audio_file = test_dir / "referencia.wav"
        audio_file.write_bytes(b"RIFF")

        assert validate_audio_path({"path": str(audio_file)}) == audio_file
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_validate_audio_path_rejects_missing_input():
    with pytest.raises(ValueError, match="Grave um audio"):
        validate_audio_path(None)


def test_validate_audio_path_rejects_nonexistent_file():
    test_dir = make_test_dir()
    missing_file = test_dir / "nao-existe.wav"

    try:
        with pytest.raises(ValueError, match="Arquivo de audio nao encontrado"):
            validate_audio_path(missing_file)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_validate_audio_path_rejects_empty_file():
    test_dir = make_test_dir()
    try:
        audio_file = test_dir / "vazio.wav"
        audio_file.write_bytes(b"")

        with pytest.raises(ValueError, match="parece vazio"):
            validate_audio_path(audio_file)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_save_reference_audio_from_data_url_writes_wav_file():
    test_dir = make_test_dir()
    payload = base64.b64encode(b"RIFF-valid-test").decode("ascii")

    try:
        audio_path = save_reference_audio_from_data_url(f"data:audio/wav;base64,{payload}", test_dir)

        assert audio_path == test_dir / f"{REFERENCE_AUDIO_BASENAME}.wav"
        assert audio_path.read_bytes() == b"RIFF-valid-test"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_save_reference_audio_from_data_url_rejects_invalid_payload():
    test_dir = make_test_dir()

    try:
        with pytest.raises(ValueError, match="Nao foi possivel ler"):
            save_reference_audio_from_data_url("isso-nao-e-data-url", test_dir)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_get_output_wav_path_uses_expected_filename_and_creates_dir():
    test_dir = make_test_dir()

    try:
        output_path = get_output_wav_path(test_dir / "nested-outputs")

        assert output_path == test_dir / "nested-outputs" / OUTPUT_WAV_NAME
        assert output_path.parent.exists()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
