"""
Clip_ S video processing.

Provides FFmpeg/FFprobe helpers for reading video metadata,
validating media, and rendering clips.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import settings


class VideoError(RuntimeError):
    """Raised when a video operation fails."""


@dataclass(frozen=True)
class VideoMetadata:
    filename: str
    duration: float
    width: int
    height: int
    fps: float
    size_bytes: int
    format_name: str

    @property
    def aspect_ratio(self) -> str:
        if self.width <= 0 or self.height <= 0:
            return "unknown"

        ratio = self.width / self.height

        if ratio > 1.7:
            return "16:9"

        if 0.9 <= ratio <= 1.1:
            return "1:1"

        if ratio < 0.8:
            return "9:16"

        return "custom"


def _require_tool(tool: str) -> str:
    """Find an executable media tool."""
    executable = shutil.which(tool)

    if executable:
        return executable

    raise VideoError(
        f"Required media tool '{tool}' was not found. "
        "Install FFmpeg and make sure it is available on PATH."
    )


def _run(
    command: list[str],
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess safely."""
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoError("Video operation timed out.") from exc
    except OSError as exc:
        raise VideoError(
            f"Unable to execute media command: {exc}"
        ) from exc


def probe_video(path: Path) -> VideoMetadata:
    """
    Read video metadata using FFprobe.
    """
    if not path.is_file():
        raise VideoError("Video file does not exist.")

    ffprobe = _require_tool(settings.ffprobe_bin)

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name",
        "-show_entries",
        "stream=width,height,r_frame_rate",
        "-select_streams",
        "v:0",
        "-of",
        "json",
        str(path),
    ]

    result = _run(command)

    if result.returncode != 0:
        raise VideoError(
            result.stderr.strip()
            or "Unable to read video metadata."
        )

    try:
        payload = json.loads(result.stdout)

        streams = payload.get("streams") or []
        formats = payload.get("format") or {}

        if not streams:
            raise VideoError("No video stream was found.")

        stream = streams[0]

        duration = float(
            formats.get("duration") or 0
        )

        width = int(
            stream.get("width") or 0
        )

        height = int(
            stream.get("height") or 0
        )

        fps = _parse_fps(
            stream.get("r_frame_rate")
        )

        format_name = str(
            formats.get("format_name") or ""
        )

    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise VideoError(
            "FFprobe returned invalid metadata."
        ) from exc

    if duration <= 0:
        raise VideoError("Video duration could not be determined.")

    if width <= 0 or height <= 0:
        raise VideoError("Video dimensions could not be determined.")

    return VideoMetadata(
        filename=path.name,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        size_bytes=path.stat().st_size,
        format_name=format_name,
    )


def _parse_fps(value: object) -> float:
    """Convert FFprobe's frame-rate fraction to a float."""
    if not value:
        return 0.0

    text = str(value)

    if "/" in text:
        numerator, denominator = text.split("/", 1)

        try:
            numerator_value = float(numerator)
            denominator_value = float(denominator)

            if denominator_value == 0:
                return 0.0

            return numerator_value / denominator_value

        except ValueError:
            return 0.0

    try:
        return float(text)
    except ValueError:
        return 0.0


def validate_clip_range(
    start: float,
    end: float,
    duration: float,
) -> tuple[float, float]:
    """
    Validate and normalize a requested clip range.
    """
    try:
        start_value = float(start)
        end_value = float(end)
        video_duration = float(duration)
    except (TypeError, ValueError) as exc:
        raise VideoError("Invalid clip timing.") from exc

    if video_duration <= 0:
        raise VideoError("Invalid video duration.")

    start_value = max(0.0, start_value)
    end_value = min(video_duration, end_value)

    if end_value <= start_value:
        raise VideoError(
            "Clip end time must be greater than start time."
        )

    clip_duration = end_value - start_value

    if clip_duration > settings.max_clip_duration:
        end_value = start_value + settings.max_clip_duration

        if end_value > video_duration:
            end_value = video_duration
            start_value = max(
                0.0,
                end_value - settings.max_clip_duration,
            )

    return start_value, end_value


def render_clip(
    source: Path,
    destination: Path,
    start: float,
    end: float,
    *,
    aspect_ratio: str = "original",
) -> Path:
    """
    Render a clip from a source video.

    Supported output ratios:
    - original
    - 9:16
    - 1:1
    - 16:9
    """
    metadata = probe_video(source)

    start_value, end_value = validate_clip_range(
        start,
        end,
        metadata.duration,
    )

    ffmpeg = _require_tool(settings.ffmpeg_bin)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    filters: list[str] = []

    if aspect_ratio == "9:16":
        filters.append(
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920"
        )

    elif aspect_ratio == "1:1":
        filters.append(
            "scale=1080:1080:force_original_aspect_ratio=increase,"
            "crop=1080:1080"
        )

    elif aspect_ratio == "16:9":
        filters.append(
            "scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080"
        )

    command = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start_value:.3f}",
        "-i",
        str(source),
        "-t",
        f"{end_value - start_value:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
    ]

    if filters:
        command.extend(
            [
                "-vf",
                ",".join(filters),
            ]
        )

    command.append(str(destination))

    result = _run(
        command,
        timeout=1800,
    )

    if result.returncode != 0:
        raise VideoError(
            result.stderr.strip()
            or "Clip rendering failed."
        )

    if not destination.is_file():
        raise VideoError(
            "FFmpeg completed without creating the output file."
        )

    return destination


def thumbnail(
    source: Path,
    destination: Path,
    timestamp: float = 0.0,
) -> Path:
    """Generate a JPEG thumbnail from a video."""
    if not source.is_file():
        raise VideoError("Source video does not exist.")

    ffmpeg = _require_tool(settings.ffmpeg_bin)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        ffmpeg,
        "-y",
        "-ss",
        str(max(0.0, timestamp)),
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(destination),
    ]

    result = _run(command)

    if result.returncode != 0:
        raise VideoError(
            result.stderr.strip()
            or "Unable to generate thumbnail."
        )

    if not destination.is_file():
        raise VideoError(
            "Thumbnail was not created."
        )

    return destination
