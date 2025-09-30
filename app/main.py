import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )


