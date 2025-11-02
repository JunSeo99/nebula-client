import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status

from app.schemas.folder import (
    DevelopmentDirectoryInfo,
    FolderContentsResponse,
    FolderSelectionRequest,
    FolderSnapshotRequest,
    FolderSnapshotResponse,
    SnapshotPageInfo,
)
from app.services.folder_inspection import DirectoryInspectionError, inspect_directory
from app.services.folder_snapshot import snapshot_directory


load_dotenv()

app = FastAPI(title="Nebula Client API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"message": "Nebula Client API"}


@app.post("/folders/inspect", response_model=FolderContentsResponse)
def inspect_folder(payload: FolderSelectionRequest) -> FolderContentsResponse:
    try:
        return inspect_directory(payload.path)
    except DirectoryInspectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.post("/folders/snapshot", response_model=FolderSnapshotResponse)
def snapshot_folder(payload: FolderSnapshotRequest) -> FolderSnapshotResponse:
    try:
        result = snapshot_directory(payload.path, payload.page_size)
    except DirectoryInspectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return FolderSnapshotResponse(
        directory=result.directory,
        generated_at=result.generated_at,
        total_entries=result.total_entries,
        page_size=result.page_size,
        page_count=result.page_count,
        pages=[
            SnapshotPageInfo(
                page=page.page,
                path=str(page.path),
                entry_count=page.entry_count,
            )
            for page in result.pages
        ],
        development_directories=[
            DevelopmentDirectoryInfo(
                relative_path=entry.relative_path,
                absolute_path=entry.absolute_path,
            )
            for entry in result.development_directories
        ],
    )


def _resolve_local_root() -> Path:
    root_override = os.getenv("LOCAL_ROOT")
    base = Path(root_override).expanduser() if root_override else Path.cwd()

    try:
        resolved = base.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LOCAL_ROOT 경로가 존재하지 않습니다.",
        ) from exc

    if not resolved.is_dir():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LOCAL_ROOT 경로는 디렉터리여야 합니다.",
        )

    return resolved


def _resolve_target_path(path: Optional[str]) -> str:
    root = _resolve_local_root()

    if path is None or path.strip() == "":
        return str(root)

    candidate = Path(path).expanduser()

    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LOCAL_ROOT 경로 내부만 조회할 수 있습니다.",
            ) from exc
    else:
        candidate = candidate.resolve()

    return str(candidate)


@app.get("/local/folder", response_model=FolderContentsResponse)
def get_local_folder(path: Optional[str] = Query(None, description="조회할 로컬 디렉터리 경로.")) -> FolderContentsResponse:
    try:
        target_path = _resolve_target_path(path)
        return inspect_directory(target_path)
    except DirectoryInspectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
