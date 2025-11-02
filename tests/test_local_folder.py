"""API tests for the /local/folder endpoint."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_local_folder_defaults_to_project_root():
    response = client.get("/local/folder")

    assert response.status_code == 200
    payload = response.json()

    assert payload["directory"] == str(Path.cwd().resolve())

    entry_names = {entry["name"] for entry in payload["entries"]}
    assert "app" in entry_names


def test_get_local_folder_for_custom_path(tmp_path):
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")

    subdir = tmp_path / "nested"
    subdir.mkdir()

    response = client.get("/local/folder", params={"path": str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()

    assert payload["directory"] == str(tmp_path.resolve())

    entries = {entry["name"]: entry for entry in payload["entries"]}
    assert "note.txt" in entries
    assert entries["note.txt"]["is_directory"] is False
    assert entries["note.txt"]["size_bytes"] == 5
    assert "nested" in entries
    assert entries["nested"]["is_directory"] is True
