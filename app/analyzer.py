"""
Clip_ S video analyzer.

Finds candidate moments in long-form videos and scores them for
potential short-form clips.

The analyzer is intentionally separated from the web application so
local AI models can be added later without changing the API layer.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .video import VideoMetadata, probe_video


@dataclass(frozen=True)
class ClipCandidate:
    id: str
    start: float
    end: float
    duration: float
    score: float
    title: str
    reason: str
    hook_score: float
    emotion_score: float
    clarity_score: float
    shareability_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisResult:
    video: dict[str, Any]
    candidates: list[ClipCandidate]
    query: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "video": self.video,
            "query": self.query,
            "candidates": [
                candidate.to_dict()
                for candidate in self.candidates
            ],
        }


def _candidate_id(index: int) -> str:
    return f"moment_{index:03d}"


def _clean_query(query: str | None) -> str:
    if not query:
        return "strong hooks"

    cleaned = re.sub(
        r"\s+",
        " ",
        str(query),
    ).strip()

    return cleaned[:500] or "strong hooks"


def _window_size(duration: float) -> float:
    """
    Choose a useful candidate window based on source duration.
    """
    if duration <= 60:
        return min(20.0, duration)

    if duration <= 300:
        return 30.0

    if duration <= 1800:
        return 35.0

    return 40.0


def _generate_windows(
    duration: float,
    window: float,
) -> list[tuple[float, float]]:
    """
    Generate overlapping candidate windows.

    This is the fallback analysis mechanism. A future local AI model
    can replace or enrich this stage.
    """
    if duration <= 0:
        return []

    if duration <= window:
        return [(0.0, duration)]

    step = max(
        8.0,
        window * 0.55,
    )

    windows: list[tuple[float, float]] = []

    cursor = 0.0

    while cursor < duration:
        end = min(
            cursor + window,
            duration,
        )

        if end - cursor >= 8.0:
            windows.append(
                (
                    round(cursor, 3),
                    round(end, 3),
                )
            )

        if end >= duration:
            break

        cursor += step

    return windows


def _position_score(
    start: float,
    end: float,
    duration: float,
) -> float:
    """
    Give extra weight to natural opening, middle, and closing moments.
    """
    if duration <= 0:
        return 0.0

    center = ((start + end) / 2.0) / duration

    anchors = (
        0.12,
        0.28,
        0.50,
        0.72,
        0.88,
    )

    distance = min(
        abs(center - anchor)
        for anchor in anchors
    )

    return max(
        0.0,
        1.0 - (distance / 0.35),
    )


def _query_bonus(query: str) -> tuple[float, float, float, float]:
    """
    Translate a natural-language request into scoring preferences.

    This does not pretend to understand the video's content yet.
    It provides a deterministic preference layer that a future model
    can replace with semantic analysis.
    """
    text = query.lower()

    hook_words = {
        "hook",
        "hooks",
        "viral",
        "attention",
        "opening",
        "intro",
    }

    emotion_words = {
        "funny",
        "funniest",
        "emotional",
        "emotion",
        "exciting",
        "dramatic",
        "surprising",
        "surprise",
    }

    motivation_words = {
        "motivation",
        "motivational",
        "inspiring",
        "inspiration",
        "lesson",
        "advice",
    }

    share_words = {
        "viral",
        "share",
        "shareable",
        "tiktok",
        "shorts",
        "reels",
    }

    hook = 0.65
    emotion = 0.55
    clarity = 0.65
    shareability = 0.60

    if any(word in text for word in hook_words):
        hook += 0.20

    if any(word in text for word in emotion_words):
        emotion += 0.25

    if any(word in text for word in motivation_words):
        clarity += 0.20

    if any(word in text for word in share_words):
        shareability += 0.25

    return (
        min(hook, 1.0),
        min(emotion, 1.0),
        min(clarity, 1.0),
        min(shareability, 1.0),
    )


def _score_candidate(
    index: int,
    start: float,
    end: float,
    metadata: VideoMetadata,
    query: str,
) -> ClipCandidate:
    """
    Score one candidate.

    The scoring system is intentionally modular. A future local model
    can provide semantic scores while this layer remains responsible
    for normalization and ranking.
    """
    duration = end - start

    position = _position_score(
        start,
        end,
        metadata.duration,
    )

    hook, emotion, clarity, shareability = _query_bonus(
        query
    )

    # Small deterministic variation prevents every candidate from
    # receiving exactly the same score while remaining reproducible.
    variation = (
        math.sin(index * 2.417) + 1.0
    ) / 2.0

    hook_score = min(
        1.0,
        0.55 * hook
        + 0.30 * position
        + 0.15 * variation,
    )

    emotion_score = min(
        1.0,
        0.65 * emotion
        + 0.20 * variation
        + 0.15 * position,
    )

    clarity_score = min(
        1.0,
        0.65 * clarity
        + 0.20 * position
        + 0.15 * variation,
    )

    shareability_score = min(
        1.0,
        0.65 * shareability
        + 0.20 * hook_score
        + 0.15 * emotion_score,
    )

    final_score = (
        hook_score * 0.30
        + emotion_score * 0.20
        + clarity_score * 0.20
        + shareability_score * 0.30
    )

    score = round(
        final_score * 100,
        1,
    )

    title = _build_title(
        query=query,
        score=score,
        index=index,
    )

    reason = _build_reason(
        query=query,
        score=score,
        position=position,
    )

    return ClipCandidate(
        id=_candidate_id(index),
        start=round(start, 3),
        end=round(end, 3),
        duration=round(duration, 3),
        score=score,
        title=title,
        reason=reason,
        hook_score=round(hook_score * 100, 1),
        emotion_score=round(emotion_score * 100, 1),
        clarity_score=round(clarity_score * 100, 1),
        shareability_score=round(
            shareability_score * 100,
            1,
        ),
    )


def _build_title(
    query: str,
    score: float,
    index: int,
) -> str:
    """Create a temporary human-readable candidate title."""
    query_lower = query.lower()

    if "funny" in query_lower:
        prefix = "Funny Moment"

    elif "motivat" in query_lower:
        prefix = "Motivational Moment"

    elif "surpris" in query_lower:
        prefix = "Surprising Moment"

    elif "hook" in query_lower:
        prefix = "Strong Hook"

    else:
        prefix = "Potential Highlight"

    return f"{prefix} #{index} — {score:.0f}% potential"


def _build_reason(
    query: str,
    score: float,
    position: float,
) -> str:
    """Explain why the candidate was selected."""
    if score >= 80:
        confidence = "high-potential"

    elif score >= 65:
        confidence = "promising"

    else:
        confidence = "worth reviewing"

    if position >= 0.75:
        location = "near a strong structural point in the video"

    else:
        location = "within a useful standalone window"

    return (
        f"{confidence.capitalize()} moment matching "
        f"“{query}”, {location}."
    )


def analyze_video(
    video_path: Path,
    query: str | None = None,
    *,
    max_candidates: int = 8,
) -> AnalysisResult:
    """
    Analyze a video and return ranked candidate moments.
    """
    metadata = probe_video(video_path)

    cleaned_query = _clean_query(query)

    window = _window_size(
        metadata.duration
    )

    windows = _generate_windows(
        metadata.duration,
        window,
    )

    candidates = [
        _score_candidate(
            index=index + 1,
            start=start,
            end=end,
            metadata=metadata,
            query=cleaned_query,
        )
        for index, (start, end) in enumerate(windows)
    ]

    candidates.sort(
        key=lambda candidate: (
            candidate.score,
            candidate.shareability_score,
        ),
        reverse=True,
    )

    candidates = candidates[:max_candidates]

    return AnalysisResult(
        video={
            "filename": metadata.filename,
            "duration": round(
                metadata.duration,
                3,
            ),
            "width": metadata.width,
            "height": metadata.height,
            "fps": round(
                metadata.fps,
                3,
            ),
            "size_bytes": metadata.size_bytes,
            "format": metadata.format_name,
            "aspect_ratio": metadata.aspect_ratio,
        },
        candidates=candidates,
        query=cleaned_query,
  )
