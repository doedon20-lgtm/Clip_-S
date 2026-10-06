"""
Clip_ S configuration.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv(
        "CLIP_S_APP_NAME",
        "Clip_ S",
    )

    version: str = os.getenv(
        "CLIP_S_VERSION",
        "0.1.0",
    )

    host: str = os.getenv(
        "CLIP_S_HOST",
        "0.0.0.0",
    )

    port: int = int(
        os.getenv(
            "CLIP_S_PORT",
            "8020",
        )
    )

    upload_directory: str = os.getenv(
        "CLIP_S_UPLOAD_DIRECTORY",
        "data/uploads",
    )

    output_directory: str = os.getenv(
        "CLIP_S_OUTPUT_DIRECTORY",
        "data/outputs",
    )

    max_upload_size_mb: int = int(
        os.getenv(
            "CLIP_S_MAX_UPLOAD_SIZE_MB",
            "2048",
        )
    )

    allowed_origins: str = os.getenv(
        "CLIP_S_ALLOWED_ORIGINS",
        "http://localhost:3000",
    )


settings = Settings()
