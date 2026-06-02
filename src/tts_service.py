import os
import tempfile
from pathlib import Path
from typing import Any

from src.audio_utils import get_output_wav_path, validate_audio_path, validate_text


DEFAULT_LANGUAGE_ID = "pt"
DEFAULT_EXAGGERATION = 0.5
DEFAULT_CFG_WEIGHT = 0.5
DEFAULT_TEMPERATURE = 0.8

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CACHE_DIR = PROJECT_ROOT / ".cache"
HF_HOME = CACHE_DIR / "huggingface"
TORCH_HOME = CACHE_DIR / "torch"
PKUSEG_HOME = CACHE_DIR / "pkuseg"
TEMP_DIR = CACHE_DIR / "tmp"
MODEL_DIR = PROJECT_ROOT / ".models" / "chatterbox"
CHATTERBOX_REPO_ID = "ResembleAI/chatterbox"
CHATTERBOX_MODEL_FILES = [
    "ve.pt",
    "t3_mtl23ls_v2.safetensors",
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
    "Cangjie5_TC.json",
]

HF_HOME.mkdir(parents=True, exist_ok=True)
TORCH_HOME.mkdir(parents=True, exist_ok=True)
PKUSEG_HOME.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_HOME / "hub"))
os.environ.setdefault("TORCH_HOME", str(TORCH_HOME))
os.environ.setdefault("PKUSEG_HOME", str(PKUSEG_HOME))
os.environ.setdefault("TEMP", str(TEMP_DIR))
os.environ.setdefault("TMP", str(TEMP_DIR))
tempfile.tempdir = str(TEMP_DIR)


def _clear_broken_local_proxy() -> None:
    if os.getenv("VOICE_CLONE_KEEP_PROXY") == "1":
        return

    proxy_keys = [
        "ALL_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "GIT_HTTP_PROXY",
        "GIT_HTTPS_PROXY",
        "all_proxy",
        "http_proxy",
        "https_proxy",
        "git_http_proxy",
        "git_https_proxy",
    ]
    broken_proxy_markers = ("127.0.0.1:9", "localhost:9", "[::1]:9")

    for key in proxy_keys:
        value = os.environ.get(key, "")
        if any(marker in value for marker in broken_proxy_markers):
            os.environ.pop(key, None)


_clear_broken_local_proxy()


class ChatterboxTTSService:
    """Lazy wrapper around Chatterbox Multilingual TTS."""

    def __init__(self, language_id: str = DEFAULT_LANGUAGE_ID, device: str | None = None) -> None:
        self.language_id = language_id
        self.device = device
        self._model: Any | None = None

    def generate_voice_clone(
        self,
        text: str | None,
        reference_audio_path: str | Path | None,
        output_path: str | Path | None = None,
    ) -> Path:
        clean_text = validate_text(text)
        clean_audio_path = validate_audio_path(reference_audio_path)
        destination = Path(output_path) if output_path else get_output_wav_path(OUTPUT_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)

        model = self._get_model()
        wav = model.generate(
            clean_text,
            language_id=self.language_id,
            audio_prompt_path=str(clean_audio_path),
            exaggeration=DEFAULT_EXAGGERATION,
            cfg_weight=DEFAULT_CFG_WEIGHT,
            temperature=DEFAULT_TEMPERATURE,
        )

        self._save_wav(wav, model.sr, destination)
        return destination

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> Any:
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        except ImportError as exc:
            raise RuntimeError(
                "Chatterbox Multilingual TTS nao esta instalado. "
                "Rode: pip install -r requirements.txt"
            ) from exc

        device = self.device or _select_device()
        model_dir = _ensure_chatterbox_model_files()
        _patch_chatterbox_local_downloads()
        return ChatterboxMultilingualTTS.from_local(model_dir, device=device)

    @staticmethod
    def _save_wav(wav: Any, sample_rate: int, destination: Path) -> None:
        try:
            import torch
            import torchaudio
        except ImportError as exc:
            raise RuntimeError(
                "PyTorch/torchaudio nao estao instalados. Rode: pip install -r requirements.txt"
            ) from exc

        if hasattr(wav, "detach"):
            audio_tensor = wav.detach().cpu()
        else:
            audio_tensor = torch.as_tensor(wav).cpu()

        if audio_tensor.ndim == 1:
            audio_tensor = audio_tensor.unsqueeze(0)

        torchaudio.save(str(destination), audio_tensor, sample_rate)


def _select_device() -> str:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch nao esta instalado. Rode: pip install -r requirements.txt") from exc

    if torch.cuda.is_available():
        return "cuda"

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"

    return "cpu"


def _ensure_chatterbox_model_files() -> Path:
    missing_files = [file_name for file_name in CHATTERBOX_MODEL_FILES if not (MODEL_DIR / file_name).exists()]
    if not missing_files:
        return MODEL_DIR

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub nao esta instalado. Rode: .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        ) from exc

    try:
        snapshot_download(
            repo_id=CHATTERBOX_REPO_ID,
            repo_type="model",
            revision="main",
            allow_patterns=CHATTERBOX_MODEL_FILES,
            local_dir=MODEL_DIR,
            max_workers=1,
            token=os.getenv("HF_TOKEN"),
        )
    except Exception as exc:
        raise RuntimeError(
            "Nao foi possivel baixar os pesos do Chatterbox no Hugging Face. "
            "Confira a internet e tente novamente. Se voce usa proxy, remova o proxy quebrado "
            "ou rode com VOICE_CLONE_KEEP_PROXY=1 usando um proxy valido."
        ) from exc

    missing_files = [file_name for file_name in CHATTERBOX_MODEL_FILES if not (MODEL_DIR / file_name).exists()]
    if missing_files:
        raise RuntimeError(
            "Download do Chatterbox incompleto. Arquivos ausentes: " + ", ".join(missing_files)
        )

    return MODEL_DIR


def _patch_chatterbox_local_downloads() -> None:
    try:
        from chatterbox.models.tokenizers import tokenizer as tokenizer_module
    except ImportError:
        return

    original_download = tokenizer_module.hf_hub_download

    def local_hub_download(*args: Any, **kwargs: Any) -> str:
        filename = kwargs.get("filename")
        if filename is None and len(args) >= 2:
            filename = args[1]

        if filename == "Cangjie5_TC.json":
            return str(MODEL_DIR / "Cangjie5_TC.json")

        return original_download(*args, **kwargs)

    tokenizer_module.hf_hub_download = local_hub_download


_SERVICE: ChatterboxTTSService | None = None


def get_tts_service() -> ChatterboxTTSService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ChatterboxTTSService(language_id=DEFAULT_LANGUAGE_ID)
    return _SERVICE


def generate_cloned_voice(text: str | None, reference_audio_path: str | Path | None) -> str:
    output_path = get_tts_service().generate_voice_clone(text, reference_audio_path)
    return str(output_path)
