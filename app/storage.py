"""
Clip_ S storage utilities.

Handles safe filenames, project files, upload paths, output paths,
and secure filesystem operations.
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any

from .config import settings


SAFE_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


def generate_id(prefix: str = "item") -> str:
    """Generate a secure unique identifier."""
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def safe_filename(filename: str) -> str:
    """
    Convert an uploaded filename into a safe filesystem filename.
    """
    if not filename:
        return "upload"

    name = Path(filename).name

    stem = Path(name).stem
    suffix = Path(name).suffix.lower()

    stem = SAFE_NAME_PATTERN.sub("_", stem)
    stem = stem.strip("._-")

    if not stem:
        stem = "upload"

    return f"{stem[:120]}{suffix}"


def is_allowed_video(filename: str) -> bool:
    """Check whether a filename has an allowed video extension."""
    suffix = Path(filename).suffix.lower()

    return suffix in settings.allowed_video_extensions


def ensure_safe_child(
    base_dir: Path,
    filename: str,
) -> Path:
    """
    Return a path guaranteed to remain inside base_dir.

    This protects filesystem operations from path traversal.
    """
    base = base_dir.resolve()
    target = (base / filename).resolve()

    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Unsafe filesystem path") from exc

    return target


def upload_path(
    project_id: str,
    filename: str,
) -> Path:
    """Create the filesystem path for an uploaded video."""
    project_dir = settings.upload_dir / project_id
    project_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = safe_filename(filename)

    return ensure_safe_child(
        project_dir,
        safe_name,
    )


def output_path(
    project_id: str,
    filename: str,
) -> Path:
    """Create the filesystem path for a generated clip."""
    project_dir = settings.output_dir / project_id
    project_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = safe_filename(filename)

    return ensure_safe_child(
        project_dir,
        safe_name,
    )


def project_path(project_id: str) -> Path:
    """Return the JSON project file path."""
    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        project_id,
    ):
        raise ValueError("Invalid project ID")

    return settings.project_dir / f"{project_id}.json"


def save_project(
    project_id: str,
    project: dict[str, Any],
) -> Path:
    """Persist a project as JSON."""
    path = project_path(project_id)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(".tmp")

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            project,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary.replace(path)

    return path


def load_project(
    project_id: str,
) -> dict[str, Any] | None:
    """Load a saved project."""
    path = project_path(project_id)

    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        return None


def delete_project(
    project_id: str,
) -> bool:
    """Delete a project's JSON record."""
    path = project_path(project_id)

    if not path.exists():
        return False

    path.unlink()

    return True


def file_size_bytes(path: Path) -> int:
    """Return a file's size in bytes."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def file_exists(path: Path) -> bool:
    """Safely check whether a file exists."""
    return path.is_file()
