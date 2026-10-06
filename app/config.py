"""
Clip_ S configuration.

Central application settings for storage, uploads, processing,
security, CORS, and media tools.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    app_name: str = os.getenv(
        "CLIP_S_APP_NAME",
        "Clip_ S",
    )

    version: str = os.getenv(
        "CLIP_S_VERSION",
        "0.2.0",
    )

    environment: str = os.getenv(
        "CLIP_S_ENVIRONMENT",
        "development",
    )

    debug: bool = _env_bool(
        "CLIP_S_DEBUG",
        False,
    )

    host: str = os.getenv(
        "CLIP_S_HOST",
        "0.0.0.0",
    )

    port: int = _env_int(
        "CLIP_S_PORT",
        8020,
    )

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    data_dir: Path = Path(
        os.getenv(
            "CLIP_S_DATA_DIR",
            "data",
        )
    )

    upload_dir: Path = Path(
        os.getenv(
            "CLIP_S_UPLOAD_DIR",
            "data/uploads",
        )
    )

    output_dir: Path = Path(
        os.getenv(
            "CLIP_S_OUTPUT_DIR",
            "data/outputs",
        )
    )

    project_dir: Path = Path(
        os.getenv(
            "CLIP_S_PROJECT_DIR",
            "data/projects",
        )
    )

    # ------------------------------------------------------------------
    # Upload limits
    # ------------------------------------------------------------------

    max_upload_size_mb: int = _env_int(
        "CLIP_S_MAX_UPLOAD_SIZE_MB",
        2048,
    )

    max_upload_size_bytes: int = (
        max_upload_size_mb * 1024 * 1024
    )

    # ------------------------------------------------------------------
    # Video formats
    # ------------------------------------------------------------------

    allowed_video_extensions: tuple[str, ...] = (
        ".mp4",
        ".mov",
        ".m4v",
        ".webm",
        ".mkv",
        ".avi",
    )

    # ------------------------------------------------------------------
    # Media tools
    # ------------------------------------------------------------------

    ffmpeg_bin: str = os.getenv(
        "CLIP_S_FFMPEG_BIN",
        "ffmpeg",
    )

    ffprobe_bin: str = os.getenv(
        "CLIP_S_FFPROBE_BIN",
        "ffprobe",
    )

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    max_workers: int = _env_int(
        "CLIP_S_MAX_WORKERS",
        2,
    )

    default_clip_duration: int = _env_int(
        "CLIP_S_DEFAULT_CLIP_DURATION",
        30,
    )

    max_clip_duration: int = _env_int(
        "CLIP_S_MAX_CLIP_DURATION",
        180,
    )

    # ------------------------------------------------------------------
    # AI analysis
    # ------------------------------------------------------------------

    ai_enabled: bool = _env_bool(
        "CLIP_S_AI_ENABLED",
        True,
    )

    ai_provider: str = os.getenv(
        "CLIP_S_AI_PROVIDER",
        "local",
    )

    ai_model: str = os.getenv(
        "CLIP_S_AI_MODEL",
        "clip-s-local",
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------

    allowed_origins: str = os.getenv(
        "CLIP_S_ALLOWED_ORIGINS",
        "http://localhost:8020,http://127.0.0.1:8020",
    )

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    secret_key: str = os.getenv(
        "CLIP_S_SECRET_KEY",
        "change-this-development-secret",
    )

    max_request_body_mb: int = _env_int(
        "CLIP_S_MAX_REQUEST_BODY_MB",
        10,
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def origins(self) -> list[str]:
        """Return configured CORS origins as a clean list."""
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

    def ensure_directories(self) -> None:
        """Create required application directories."""
        self.data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.project_dir.mkdir(
            parents=True,
            exist_ok=True,
        )


settings = Settings()

# Make sure required folders exist when the application starts.
settings.ensure_directories()
