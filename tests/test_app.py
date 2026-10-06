"""
Clip_ S application tests.

Basic tests for the application health endpoint, configuration,
storage utilities, and core API structure.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.storage import (
    generate_id,
    is_allowed_video,
    safe_filename,
)


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["service"] == "Clip_ S"
    assert data["status"] == "online"


def test_homepage() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Clip_ S" in response.text


def test_generate_id() -> None:
    first = generate_id("test")
    second = generate_id("test")

    assert first.startswith("test_")
    assert second.startswith("test_")
    assert first != second


def test_safe_filename() -> None:
    result = safe_filename(
        "../../My Dangerous Video!.mp4"
    )

    assert "/" not in result
    assert "\\" not in result
    assert result.endswith(".mp4")


def test_allowed_video_extensions() -> None:
    assert is_allowed_video("video.mp4")
    assert is_allowed_video("video.MOV")
    assert is_allowed_video("video.webm")

    assert not is_allowed_video("document.pdf")
    assert not is_allowed_video("image.png")


def test_unknown_job() -> None:
    response = client.get(
        "/api/jobs/nonexistent-job"
    )

    assert response.status_code == 404


def test_unknown_project() -> None:
    response = client.get(
        "/api/projects/nonexistent-project"
    )

    assert response.status_code == 404
