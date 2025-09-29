"""Tests for the recursive folder snapshot API endpoint."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_snapshot_creates_single_file(tmp_path, monkeypatch):
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


def test_snapshot_honors_page_size(tmp_path, monkeypatch):
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


def test_snapshot_auto_batches_when_entries_large(tmp_path, monkeypatch):
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


def test_snapshot_respects_depth_first_order(tmp_path, monkeypatch):
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


def test_snapshot_skips_development_directories(tmp_path, monkeypatch):
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
