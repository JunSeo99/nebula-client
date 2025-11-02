"""Tests for the recursive folder snapshot API endpoint."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


class _StubResponse:
    status_code = 200


@pytest.fixture
def snapshot_delivery_calls(monkeypatch):
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("SERVER_URL", "http://example.com")

    def fake_post(url: str, json: dict, timeout: float):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _StubResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


client = TestClient(app)


def test_snapshot_creates_single_file(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    (target_dir / "alpha.txt").write_text("alpha", encoding="utf-8")
    nested_dir = target_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "beta.txt").write_text("beta", encoding="utf-8")
    hidden_dir = target_dir / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("secret", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir)},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["directory"] == str(target_dir.resolve())
    assert payload["page_count"] == 1
    assert payload["total_entries"] == 3
    assert payload["pages"][0]["entry_count"] == 3
    assert payload["development_directories"] == []

    snapshot_path = Path(payload["pages"][0]["path"])
    assert snapshot_path.exists()

    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    relative_paths = {entry["relative_path"] for entry in data["entries"]}
    assert "alpha.txt" in relative_paths
    assert "nested" in relative_paths
    assert "nested/beta.txt" in relative_paths
    assert not any(path.startswith(".hidden") for path in relative_paths)
    assert any(
        entry["relative_path"] == "nested" and entry["is_development"] is False
        for entry in data["entries"]
    )


def test_snapshot_honors_page_size(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    for index in range(5):
        (target_dir / f"file_{index}.txt").write_text(f"data-{index}", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir), "page_size": 2},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["page_count"] == 3
    assert payload["page_size"] == 2
    assert [page["entry_count"] for page in payload["pages"]] == [2, 2, 1]
    assert payload["development_directories"] == []

    for page in payload["pages"]:
        snapshot_path = Path(page["path"])
        assert snapshot_path.exists()
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert len(data["entries"]) == page["entry_count"]
        assert data["page"] == page["page"]
        assert data["page_size"] == 2
        assert all(entry["is_development"] is False for entry in data["entries"])


def test_snapshot_auto_batches_when_entries_large(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    for index in range(120):
        (target_dir / f"file_{index:03d}.txt").write_text(f"payload-{index}", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir)},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["page_count"] == 3
    assert payload["page_size"] == 50
    assert [page["entry_count"] for page in payload["pages"]] == [50, 50, 20]
    assert payload["development_directories"] == []

    first_page_path = Path(payload["pages"][0]["path"])
    data = json.loads(first_page_path.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 50
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert all(entry["is_development"] is False for entry in data["entries"])


def test_snapshot_respects_depth_first_order(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    deep_dir = target_dir / "outer"
    deep_dir.mkdir()
    deeper_dir = deep_dir / "inner"
    deeper_dir.mkdir()

    (deeper_dir / "leaf.txt").write_text("leaf", encoding="utf-8")
    (deep_dir / "root.txt").write_text("root", encoding="utf-8")
    (target_dir / "top.txt").write_text("top", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir)},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["page_count"] == 1
    assert payload["development_directories"] == []

    snapshot_path = Path(payload["pages"][0]["path"])
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    relative_paths = [entry["relative_path"] for entry in data["entries"]]

    assert relative_paths == [
        "outer/inner/leaf.txt",
        "outer/inner",
        "outer/root.txt",
        "outer",
        "top.txt",
    ]


def test_snapshot_skips_development_directories(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    git_project = target_dir / "git_project"
    git_project.mkdir()
    (git_project / ".git").mkdir()
    (git_project / "src").mkdir()
    (git_project / "src" / "app.py").write_text("print('hello')", encoding="utf-8")

    python_project = target_dir / "python_project"
    python_project.mkdir()
    (python_project / "pyproject.toml").write_text("[tool.poetry]", encoding="utf-8")
    (python_project / "module.py").write_text("value = 1", encoding="utf-8")

    docs_dir = target_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("# Guide", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir)},
    )

    assert response.status_code == 200
    payload = response.json()

    collected_paths: set[str] = set()
    development_flags: dict[str, bool] = {}
    for page in payload["pages"]:
        snapshot_path = Path(page["path"])
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            collected_paths.add(entry["relative_path"])
            development_flags.setdefault(entry["relative_path"], entry["is_development"])

    assert "git_project" in collected_paths
    assert "python_project" in collected_paths
    assert "docs" in collected_paths
    assert "docs/guide.md" in collected_paths
    assert "git_project/src" not in collected_paths
    assert "git_project/src/app.py" not in collected_paths
    assert "python_project/module.py" not in collected_paths
    assert development_flags.get("git_project") is True
    assert development_flags.get("python_project") is True
    assert development_flags.get("docs") is False

    development_relative_paths = {
        entry["relative_path"] for entry in payload["development_directories"]
    }
    assert development_relative_paths == {"git_project", "python_project"}


def test_snapshot_sends_camel_case_payload(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    (target_dir / "alpha_file.txt").write_text("alpha", encoding="utf-8")
    (target_dir / "beta_file.txt").write_text("beta", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir), "page_size": 5},
    )

    assert response.status_code == 200
    assert len(snapshot_delivery_calls) == 1

    call = snapshot_delivery_calls[0]
    assert call["url"] == "http://example.com/generate-filename"
    assert call["timeout"] == 10.0

    payload = call["json"]
    assert payload["directory"] == str(target_dir.resolve())
    assert "generatedAt" in payload
    assert payload["page"] == 1
    assert payload["pageCount"] == 1
    assert payload["pageSize"] == 5
    assert payload["totalEntries"] == 2
    assert len(payload["entries"]) == 2
    assert all("relativePath" in entry for entry in payload["entries"])
    assert all("absolutePath" in entry for entry in payload["entries"])
    assert all("isDirectory" in entry for entry in payload["entries"])


def test_snapshot_includes_pdf_keywords(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    pdf_path = target_dir / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    (target_dir / "notes.txt").write_text("notes", encoding="utf-8")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    keywords = ["Nebula", "Pipeline"]

    def fake_extract(path: str, **_: object) -> list[str]:
        assert path == str(pdf_path)
        return keywords

    monkeypatch.setattr(
        "app.extraction.handlers.pdf.extract_pdf_keywords",
        fake_extract,
    )

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir)},
    )

    assert response.status_code == 200
    assert len(snapshot_delivery_calls) == 1

    pdf_entry = next(
        entry
        for entry in snapshot_delivery_calls[0]["json"]["entries"]
        if entry["relativePath"].endswith("report.pdf")
    )
    assert pdf_entry["keywords"] == keywords
    assert "prompt" in pdf_entry
    assert all(keyword in pdf_entry["prompt"] for keyword in keywords)
    assert "caption" not in pdf_entry


def test_snapshot_includes_image_highlights(tmp_path, monkeypatch, snapshot_delivery_calls):
    target_dir = tmp_path / "source"
    target_dir.mkdir()

    image_path = target_dir / "diagram.png"
    image_path.write_bytes(b"fake")

    snapshot_root = tmp_path / "snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_root))

    from app.extraction.handlers.image import ImageHighlights

    image_lines = ["메인 제목", "보조 문장"]
    caption = "A technical diagram of a rocket"

    def fake_image_highlights(path: str, *, size_ratio: float = 0.8) -> ImageHighlights:
        assert path == str(image_path)
        assert size_ratio == 0.8
        return ImageHighlights(ocr_lines=image_lines, caption=caption)

    monkeypatch.setattr(
        "app.extraction.handlers.image.extract_image_highlights",
        fake_image_highlights,
    )

    response = client.post(
        "/folders/snapshot",
        json={"path": str(target_dir)},
    )

    assert response.status_code == 200
    assert len(snapshot_delivery_calls) == 1

    image_entry = next(
        entry
        for entry in snapshot_delivery_calls[0]["json"]["entries"]
        if entry["relativePath"].endswith("diagram.png")
    )

    assert image_entry["keywords"] == image_lines + [caption]
    assert image_entry["caption"] == caption
    assert "prompt" in image_entry
    assert "[OCR 상위 텍스트]" in image_entry["prompt"]
    assert "[이미지 캡션]" in image_entry["prompt"]
