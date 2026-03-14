"""
HistoriClip - Configuration (v3.0)
====================================
Single source of truth for all settings. Every other module reads from here.

  LocationEngineConfig (master)
    ├── MapillaryConfig     — data collection
    ├── DINOv2Config        — model + FAISS + LightGlue
    ├── VisualModuleConfig  — SDXL image generation
    ├── InformationConfig   — Wikidata + Gemini scripts
    ├── AudioConfig         — edge-tts narration
    └── EditorConfig        — FFmpeg video assembly

All paths derive from BASE_DIR. Environment variables override defaults.

Author: HistoriClip Team (Final Year Project)
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

BASE_DIR = Path(__file__).parent.parent          # python-ai-service/
DATA_DIR = BASE_DIR / "data"
BACKEND_UPLOADS = BASE_DIR.parent / "backend" / "uploads"


# ─────────────────────────────────────────────────────────────
# Sub-Configs
# ─────────────────────────────────────────────────────────────

@dataclass
class MapillaryConfig:
    """Road-graph sampling via OSMnx + Mapillary API + Nominatim reverse geocoding."""
    client_token: str = ""
    city_name: str = "Pune"
    bbox: List[float] = field(default_factory=lambda: [73.83, 18.49, 73.91, 18.56])
    sample_spacing_meters: float = 50.0
    total_limit: int = 1000
    download_delay: float = 0.3
    output_dir: Path = DATA_DIR / "reference_images"
    images_subdir: str = "images"
    csv_filename: str = "locations.csv"


@dataclass
class DINOv2Config:
    """DINOv2 model, GeM pooling, FAISS index, and LightGlue verification."""
    # Model
    model_name: str = "facebook/dinov2-base"
    device: str = "auto"
    batch_size: int = 8

    # GeM pooling (AnyLoc method)
    pooling_method: str = "gem"
    gem_power: float = 3.0

    # FAISS search
    top_k: int = 10
    min_confidence: float = 0.75

    # LightGlue verification
    use_lightglue: bool = True
    rerank_top_k: int = 1
    lightglue_max_size: int = 512
    min_matches_verified: int = 10
    max_viz_matches: int = 50

    # Index paths
    index_dir: Path = DATA_DIR / "location_index"
    index_filename: str = "faiss.index"
    metadata_filename: str = "metadata.json"


@dataclass
class VisualModuleConfig:
    """SDXL Lightning image generation settings."""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    default_steps: int = 8
    default_guidance: float = 0.0
    resolution_laptop: tuple = (1344, 768)       # 16:9 landscape
    resolution_mobile: tuple = (768, 1344)        # 9:16 portrait


@dataclass
class InformationConfig:
    """Wikidata UNESCO verification + Gemini script generation."""
    wikidata_endpoint: str = "https://query.wikidata.org/sparql"
    wikidata_timeout: int = 30
    wikidata_user_agent: str = "HistoriClip/2.1"
    default_duration_seconds: int = 60
    words_per_minute: int = 150


@dataclass
class AudioConfig:
    """Edge-tts narration (Microsoft Neural TTS)."""
    voice: str = "en-GB-RyanNeural"
    rate: str = "-5%"
    volume: str = "+0%"
    pitch: str = "-2Hz"
    output_format: str = "mp3"
    generate_subtitles: bool = True
    output_dir: Path = BACKEND_UPLOADS / "generated_audio"


@dataclass
class EditorConfig:
    """FFmpeg video assembly with Ken Burns effect."""
    output_dir: Path = BACKEND_UPLOADS / "generated_videos"
    fps: int = 30
    video_codec: str = "auto"               # auto → h264_nvenc, fallback libx264
    video_bitrate: str = "5M"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    pixel_format: str = "yuv420p"
    ken_burns_enabled: bool = True
    ken_burns_zoom_rate: float = 0.0015
    transition_type: str = "fade"
    transition_duration: float = 0.5


# ─────────────────────────────────────────────────────────────
# Master Config
# ─────────────────────────────────────────────────────────────

@dataclass
class LocationEngineConfig:
    """Master config combining all sub-configs. Provides derived path properties."""
    mapillary: MapillaryConfig = field(default_factory=MapillaryConfig)
    dinov2: DINOv2Config = field(default_factory=DINOv2Config)
    visual: VisualModuleConfig = field(default_factory=VisualModuleConfig)
    information: InformationConfig = field(default_factory=InformationConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)

    @property
    def images_dir(self) -> Path:
        return self.mapillary.output_dir / self.mapillary.images_subdir

    @property
    def locations_csv(self) -> Path:
        return self.mapillary.output_dir / self.mapillary.csv_filename

    @property
    def index_file(self) -> Path:
        return self.dinov2.index_dir / self.dinov2.index_filename

    @property
    def metadata_file(self) -> Path:
        return self.dinov2.index_dir / self.dinov2.metadata_filename

    def __post_init__(self):
        """Create all output directories on init."""
        self.mapillary.output_dir.mkdir(parents=True, exist_ok=True)
        (self.mapillary.output_dir / self.mapillary.images_subdir).mkdir(exist_ok=True)
        self.dinov2.index_dir.mkdir(parents=True, exist_ok=True)
        self.editor.output_dir.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Environment Loader
# ─────────────────────────────────────────────────────────────

def load_config_from_env() -> LocationEngineConfig:
    """Load config with environment variable overrides. Reads .env from project root."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

    config = LocationEngineConfig()

    # Mapillary
    config.mapillary.client_token = os.getenv("MAPILLARY_CLIENT_TOKEN", "")
    if os.getenv("CITY_NAME"):
        config.mapillary.city_name = os.getenv("CITY_NAME")

    # DINOv2
    if os.getenv("DINOV2_DEVICE"):
        config.dinov2.device = os.getenv("DINOV2_DEVICE")
    if os.getenv("DINOV2_BATCH_SIZE"):
        config.dinov2.batch_size = int(os.getenv("DINOV2_BATCH_SIZE"))
    if os.getenv("DINOV2_POOLING"):
        config.dinov2.pooling_method = os.getenv("DINOV2_POOLING")

    # Visual
    config.visual.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if os.getenv("GEMINI_MODEL"):
        config.visual.gemini_model = os.getenv("GEMINI_MODEL")
    if os.getenv("VISUAL_STEPS"):
        config.visual.default_steps = int(os.getenv("VISUAL_STEPS"))
    if os.getenv("VISUAL_GUIDANCE"):
        config.visual.default_guidance = float(os.getenv("VISUAL_GUIDANCE"))
    if os.getenv("RESOLUTION_LAPTOP"):
        parts = os.getenv("RESOLUTION_LAPTOP").split(",")
        if len(parts) == 2:
            config.visual.resolution_laptop = (int(parts[0]), int(parts[1]))
    if os.getenv("RESOLUTION_MOBILE"):
        parts = os.getenv("RESOLUTION_MOBILE").split(",")
        if len(parts) == 2:
            config.visual.resolution_mobile = (int(parts[0]), int(parts[1]))

    # Information
    if os.getenv("WIKIDATA_TIMEOUT"):
        config.information.wikidata_timeout = int(os.getenv("WIKIDATA_TIMEOUT"))
    if os.getenv("DEFAULT_DURATION_SECONDS"):
        config.information.default_duration_seconds = int(os.getenv("DEFAULT_DURATION_SECONDS"))
    if os.getenv("WORDS_PER_MINUTE"):
        config.information.words_per_minute = int(os.getenv("WORDS_PER_MINUTE"))

    # Audio
    if os.getenv("TTS_VOICE"):
        config.audio.voice = os.getenv("TTS_VOICE")
    if os.getenv("TTS_RATE"):
        config.audio.rate = os.getenv("TTS_RATE")
    if os.getenv("TTS_VOLUME"):
        config.audio.volume = os.getenv("TTS_VOLUME")
    if os.getenv("TTS_PITCH"):
        config.audio.pitch = os.getenv("TTS_PITCH")
    if os.getenv("TTS_SUBTITLES"):
        config.audio.generate_subtitles = os.getenv("TTS_SUBTITLES", "true").lower() == "true"

    # Editor
    if os.getenv("VIDEO_FPS"):
        config.editor.fps = int(os.getenv("VIDEO_FPS"))
    if os.getenv("VIDEO_CODEC"):
        config.editor.video_codec = os.getenv("VIDEO_CODEC")
    if os.getenv("KEN_BURNS_ENABLED"):
        config.editor.ken_burns_enabled = os.getenv("KEN_BURNS_ENABLED", "true").lower() == "true"

    return config


DEFAULT_CONFIG = LocationEngineConfig()
