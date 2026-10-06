"""
Clip_ S application server.

FastAPI application connecting the frontend to video uploads,
background processing, AI analysis, clip rendering, projects,
and generated media.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analyzer import analyze_video
from .config import settings
from .jobs import (
    analyze_video_job,
    job_manager,
    process_video_job,
    render_clips_job,
)
from .storage import (
    generate_id,
    is_allowed_video,
    load_project,
    output_path,
    project_path,
    save_project,
    upload_path,
)
from .video import VideoError, probe_video


settings.ensure_directories()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "AI-assisted video clipping, editing, "
        "and creator marketplace platform."
    ),
)


# ----------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Frontend
# ----------------------------------------------------------------------

FRONTEND_DIR = (
    Path(__file__).resolve().parent / "frontend"
)

ASSETS_DIR = FRONTEND_DIR / "assets"


if ASSETS_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(ASSETS_DIR)),
        name="assets",
    )


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    project_id: str = Field(
        min_length=1,
        max_length=100,
    )

    job_id: str | None = Field(
        default=None,
        max_length=100,
    )

    prompt: str = Field(
        default="strong hooks",
        min_length=1,
        max_length=500,
    )


class RenderRequest(BaseModel):
    project_id: str = Field(
        min_length=1,
        max_length=100,
    )

    candidates: list[dict[str, Any]]

    aspect_ratio: str = Field(
        default="original",
        max_length=20,
    )


# ----------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "success": True,
        "service": settings.app_name,
        "status": "online",
        "version": settings.version,
        "environment": settings.environment,
    }


# ----------------------------------------------------------------------
# Frontend route
# ----------------------------------------------------------------------


@app.get("/")
async def index() -> FileResponse:
    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend index.html not found.",
        )

    return FileResponse(
        index_file,
        media_type="text/html",
    )


# ----------------------------------------------------------------------
# Upload
# ----------------------------------------------------------------------


@app.post("/api/upload")
async def upload_video(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Upload a video and create its processing job.
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename was provided.",
        )

    if not is_allowed_video(file.filename):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported video format. "
                "Supported formats: MP4, MOV, M4V, WEBM, MKV, AVI."
            ),
        )

    project_id = generate_id("project")

    destination = upload_path(
        project_id,
        file.filename,
    )

    total_bytes = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if (
                    total_bytes
                    > settings.max_upload_size_bytes
                ):
                    output.close()

                    if destination.exists():
                        destination.unlink()

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "The uploaded video exceeds the "
                            f"{settings.max_upload_size_mb} MB limit."
                        ),
                    )

                output.write(chunk)

    except HTTPException:
        raise

    except Exception as exc:
        if destination.exists():
            destination.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {exc}",
        ) from exc

    finally:
        await file.close()

    try:
        metadata = probe_video(destination)

    except VideoError as exc:
        if destination.exists():
            destination.unlink()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    project = {
        "id": project_id,
        "name": Path(file.filename).stem,
        "status": "processing",
        "source": {
            "filename": destination.name,
            "path": str(destination),
            "size_bytes": metadata.size_bytes,
            "duration": metadata.duration,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
            "format": metadata.format_name,
            "aspect_ratio": metadata.aspect_ratio,
        },
        "analysis": None,
        "outputs": [],
    }

    save_project(
        project_id,
        project,
    )

    job_id = generate_id("job")

    job = job_manager.create(
        job_id,
        project_id=project_id,
    )

    job_manager.submit(
        job_id,
        process_video_job,
        destination,
        project_id,
    )

    return {
        "success": True,
        "project_id": project_id,
        "job_id": job_id,
        "filename": file.filename,
        "metadata": project["source"],
    }


# ----------------------------------------------------------------------
# Job status
# ----------------------------------------------------------------------


@app.get("/api/jobs/{job_id}")
async def get_job(
    job_id: str,
) -> dict[str, Any]:
    job = job_manager.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    return {
        "success": True,
        "job": job.snapshot(),
    }


# ----------------------------------------------------------------------
# AI analysis
# ----------------------------------------------------------------------


@app.post("/api/analyze")
async def analyze(
    request: AnalyzeRequest,
) -> dict[str, Any]:
    """
    Analyze an uploaded video according to the user's request.
    """
    project = load_project(
        request.project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    source = project.get("source") or {}
    source_path = source.get("path")

    if not source_path:
        raise HTTPException(
            status_code=400,
            detail="Project does not contain a source video.",
        )

    video_path = Path(source_path)

    if not video_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Source video is no longer available.",
        )

    job_id = generate_id("analysis")

    job_manager.create(
        job_id,
        project_id=request.project_id,
    )

    job_manager.submit(
        job_id,
        analyze_video_job,
        video_path,
        request.project_id,
        request.prompt,
    )

    return {
        "success": True,
        "job_id": job_id,
        "project_id": request.project_id,
        "prompt": request.prompt,
    }


# ----------------------------------------------------------------------
# Direct analysis endpoint
# ----------------------------------------------------------------------


@app.post("/api/analyze/sync")
async def analyze_sync(
    request: AnalyzeRequest,
) -> dict[str, Any]:
    """
    Run analysis immediately.

    Useful for development and future model integrations.
    """
    project = load_project(
        request.project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    source = project.get("source") or {}
    source_path = source.get("path")

    if not source_path:
        raise HTTPException(
            status_code=400,
            detail="Project does not contain a source video.",
        )

    video_path = Path(source_path)

    if not video_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Source video is no longer available.",
        )

    try:
        result = analyze_video(
            video_path,
            request.prompt,
        )

    except VideoError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    project["analysis"] = result.to_dict()
    project["status"] = "analyzed"

    save_project(
        request.project_id,
        project,
    )

    return {
        "success": True,
        **result.to_dict(),
    }


# ----------------------------------------------------------------------
# Render clips
# ----------------------------------------------------------------------


@app.post("/api/render")
async def render(
    request: RenderRequest,
) -> dict[str, Any]:
    """
    Queue rendering of selected candidate moments.
    """
    project = load_project(
        request.project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    source = project.get("source") or {}
    source_path = source.get("path")

    if not source_path:
        raise HTTPException(
            status_code=400,
            detail="Project does not contain a source video.",
        )

    video_path = Path(source_path)

    if not video_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Source video is no longer available.",
        )

    allowed_ratios = {
        "original",
        "9:16",
        "1:1",
        "16:9",
    }

    if request.aspect_ratio not in allowed_ratios:
        raise HTTPException(
            status_code=400,
            detail="Unsupported aspect ratio.",
        )

    if not request.candidates:
        raise HTTPException(
            status_code=400,
            detail="No clip candidates were selected.",
        )

    job_id = generate_id("render")

    job_manager.create(
        job_id,
        project_id=request.project_id,
    )

    job_manager.submit(
        job_id,
        render_clips_job,
        video_path,
        request.project_id,
        request.candidates,
        request.aspect_ratio,
    )

    project["status"] = "rendering"

    save_project(
        request.project_id,
        project,
    )

    return {
        "success": True,
        "job_id": job_id,
        "project_id": request.project_id,
    }


# ----------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------


@app.get("/api/projects/{project_id}")
async def get_project(
    project_id: str,
) -> dict[str, Any]:
    project = load_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    return {
        "success": True,
        "project": project,
    }


# ----------------------------------------------------------------------
# Media
# ----------------------------------------------------------------------


@app.get(
    "/media/outputs/{project_id}/{filename}"
)
async def output_media(
    project_id: str,
    filename: str,
) -> FileResponse:
    path = output_path(
        project_id,
        filename,
    )

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Output media not found.",
        )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


@app.get(
    "/media/uploads/{project_id}/{filename}"
)
async def upload_media(
    project_id: str,
    filename: str,
) -> FileResponse:
    path = settings.upload_dir / project_id / filename

    try:
        path = path.resolve()
        base = settings.upload_dir.resolve()
        path.relative_to(base)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid media path.",
        ) from exc

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Source media not found.",
        )

    return FileResponse(
        path,
        media_type="video/mp4",
    )


# ----------------------------------------------------------------------
# Application shutdown
# ----------------------------------------------------------------------


@app.on_event("shutdown")
def shutdown_event() -> None:
    job_manager.shutdown()
