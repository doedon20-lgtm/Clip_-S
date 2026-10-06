"""
Clip_ S background job system.

Runs video analysis and clip rendering in background workers so the
web application remains responsive while long-running media tasks
are processed.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .analyzer import analyze_video
from .config import settings
from .storage import output_path
from .video import render_clip


@dataclass
class Job:
    """Represents one background processing job."""

    id: str
    status: str = "queued"
    progress: int = 0
    message: str = "Waiting to start."
    result: dict[str, Any] | None = None
    error: str | None = None
    project_id: str | None = None

    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
    )

    def update(
        self,
        *,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Thread-safe job update."""
        with self._lock:
            if status is not None:
                self.status = status

            if progress is not None:
                self.progress = max(
                    0,
                    min(100, int(progress)),
                )

            if message is not None:
                self.message = message

            if result is not None:
                self.result = result

            if error is not None:
                self.error = error

    def snapshot(self) -> dict[str, Any]:
        """Return a thread-safe public representation."""
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "progress": self.progress,
                "message": self.message,
                "result": self.result,
                "error": self.error,
                "project_id": self.project_id,
            }


class JobManager:
    """Manages Clip_ S background processing."""

    def __init__(
        self,
        max_workers: int | None = None,
    ) -> None:
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers
            or settings.max_workers,
            thread_name_prefix="clip-s-worker",
        )

        self.jobs: dict[str, Job] = {}
        self.futures: dict[str, Future[Any]] = {}
        self.lock = threading.RLock()

    def create(
        self,
        job_id: str,
        *,
        project_id: str | None = None,
    ) -> Job:
        """Create and register a new job."""
        job = Job(
            id=job_id,
            project_id=project_id,
        )

        with self.lock:
            self.jobs[job_id] = job

        return job

    def get(
        self,
        job_id: str,
    ) -> Job | None:
        """Retrieve a job."""
        with self.lock:
            return self.jobs.get(job_id)

    def submit(
        self,
        job_id: str,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future[Any]:
        """Submit work to the background executor."""
        job = self.get(job_id)

        if job is None:
            raise ValueError(
                f"Unknown job: {job_id}"
            )

        future = self.executor.submit(
            self._run_job,
            job,
            function,
            args,
            kwargs,
        )

        with self.lock:
            self.futures[job_id] = future

        return future

    @staticmethod
    def _run_job(
        job: Job,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """Execute a job and update its state."""
        job.update(
            status="processing",
            progress=5,
            message="Processing started.",
        )

        try:
            result = function(
                job,
                *args,
                **kwargs,
            )

            job.update(
                status="completed",
                progress=100,
                message="Processing completed.",
                result=result,
            )

            return result

        except Exception as exc:
            job.update(
                status="failed",
                progress=100,
                message="Processing failed.",
                error=str(exc),
            )

            return None

    def shutdown(self) -> None:
        """Stop background workers."""
        self.executor.shutdown(
            wait=False,
            cancel_futures=True,
        )


def process_video_job(
    job: Job,
    video_path: Path,
    project_id: str,
) -> dict[str, Any]:
    """
    Analyze an uploaded video.

    This is the first stage of the Clip_ S processing pipeline.
    """
    job.update(
        progress=15,
        message="Reading video information...",
    )

    analysis = analyze_video(
        video_path,
        query="strong hooks",
    )

    job.update(
        progress=90,
        message="Ranking potential moments...",
    )

    return {
        "project_id": project_id,
        "video": analysis.video,
        "query": analysis.query,
        "candidates": [
            candidate.to_dict()
            for candidate in analysis.candidates
        ],
    }


def analyze_video_job(
    job: Job,
    video_path: Path,
    project_id: str,
    query: str,
) -> dict[str, Any]:
    """
    Run a user-requested AI moment analysis.
    """
    job.update(
        progress=10,
        message="Understanding your request...",
    )

    analysis = analyze_video(
        video_path,
        query=query,
    )

    job.update(
        progress=90,
        message="Ranking the best moments...",
    )

    return {
        "project_id": project_id,
        "video": analysis.video,
        "query": analysis.query,
        "candidates": [
            candidate.to_dict()
            for candidate in analysis.candidates
        ],
    }


def render_clips_job(
    job: Job,
    video_path: Path,
    project_id: str,
    candidates: list[dict[str, Any]],
    aspect_ratio: str = "original",
) -> dict[str, Any]:
    """
    Render selected candidate moments into actual video files.
    """
    if not candidates:
        raise ValueError(
            "No clip candidates were provided."
        )

    outputs: list[dict[str, Any]] = []

    total = len(candidates)

    for index, candidate in enumerate(candidates, start=1):
        start = float(candidate["start"])
        end = float(candidate["end"])

        filename = (
            f"clip_{index:03d}_{project_id}.mp4"
        )

        destination = output_path(
            project_id,
            filename,
        )

        progress = int(
            ((index - 1) / total) * 85
        ) + 10

        job.update(
            progress=progress,
            message=(
                f"Rendering clip {index} of {total}..."
            ),
        )

        render_clip(
            video_path,
            destination,
            start,
            end,
            aspect_ratio=aspect_ratio,
        )

        outputs.append(
            {
                "id": candidate.get(
                    "id",
                    f"clip_{index:03d}",
                ),
                "filename": destination.name,
                "url": (
                    f"/media/outputs/"
                    f"{project_id}/"
                    f"{destination.name}"
                ),
                "start": start,
                "end": end,
                "duration": round(
                    end - start,
                    3,
                ),
                "score": candidate.get(
                    "score",
                    0,
                ),
                "title": candidate.get(
                    "title",
                    f"Clip {index}",
                ),
            }
        )

    job.update(
        progress=95,
        message="Finalizing generated clips...",
    )

    return {
        "project_id": project_id,
        "outputs": outputs,
    }


job_manager = JobManager()
