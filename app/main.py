import os
import shutil
import subprocess
import platform
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from app.schemas.folder import (
    DevelopmentDirectoryInfo,
    FileOpenRequest,
    FileOpenResponse,
    FolderContentsResponse,
    FolderSelectionRequest,
    FolderSnapshotRequest,
    FolderSnapshotResponse,
    SnapshotPageInfo,
    SortBy,
    SortOrder,
    StorageInfoResponse,
)
from app.services.folder_inspection import DirectoryInspectionError, inspect_directory
from app.services.folder_snapshot import snapshot_directory
from app.routers import organized_files


load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="Nebula Client API")

# CORS 미들웨어 설정 - 모든 오리진, 메서드, 헤더 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(organized_files.router)

logger.info("=" * 80)
logger.info("Nebula Client API 시작됨")
logger.info("=" * 80)


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
def get_local_folder(
    path: Optional[str] = Query(None, description="조회할 로컬 디렉터리 경로."),
    sort_by: SortBy = Query(SortBy.NAME, description="정렬 기준: name, modified_at, file_type"),
    sort_order: SortOrder = Query(SortOrder.ASC, description="정렬 순서: asc, desc"),
) -> FolderContentsResponse:
    try:
        target_path = _resolve_target_path(path)
        response = inspect_directory(target_path)

        # 정렬 로직
        def get_sort_key(entry):
            if sort_by == SortBy.NAME:
                return entry.name.lower()
            elif sort_by == SortBy.MODIFIED_AT:
                return entry.modified_at
            elif sort_by == SortBy.FILE_TYPE:
                # 파일 타입별 정렬: 디렉터리 먼저, 그 다음 확장자
                if entry.is_directory:
                    return (0, entry.name.lower())
                else:
                    # 확장자 기준 정렬
                    ext = Path(entry.name).suffix.lower() or ""
                    return (1, ext, entry.name.lower())
            return entry.name.lower()

        reverse = sort_order == SortOrder.DESC
        response.entries.sort(key=get_sort_key, reverse=reverse)

        return response
    except DirectoryInspectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.get("/storage/info", response_model=StorageInfoResponse)
def get_storage_info(path: Optional[str] = Query(None, description="조회할 디렉터리 경로 (기본값: LOCAL_ROOT).")) -> StorageInfoResponse:
    """현재 스토리지 용량 정보를 반환합니다."""
    try:
        target_path = _resolve_target_path(path)
        stat = shutil.disk_usage(target_path)

        total_bytes = stat.total
        used_bytes = stat.used
        free_bytes = stat.free

        total_gb = total_bytes / (1024 ** 3)
        used_gb = used_bytes / (1024 ** 3)
        free_gb = free_bytes / (1024 ** 3)

        used_percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0.0

        return StorageInfoResponse(
            total_bytes=total_bytes,
            used_bytes=used_bytes,
            free_bytes=free_bytes,
            total_gb=round(total_gb, 2),
            used_gb=round(used_gb, 2),
            free_gb=round(free_gb, 2),
            used_percent=round(used_percent, 2),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"스토리지 정보 조회 실패: {str(exc)}",
        ) from exc


@app.post("/file/open", response_model=FileOpenResponse)
def open_file(payload: FileOpenRequest) -> FileOpenResponse:
    """운영체제의 기본 애플리케이션으로 파일을 엽니다."""
    import sys
    sys.stderr.flush()
    sys.stdout.flush()
    try:
        logger.info(f"[FILE_OPEN] 요청 경로: {payload.path}")

        # 1단계: 경로 전처리
        raw_path = payload.path.strip()
        logger.info(f"[FILE_OPEN] 전처리 경로: {raw_path}")

        # 2단계: expanduser만 수행 (resolve 제거)
        file_path = Path(raw_path).expanduser()
        logger.info(f"[FILE_OPEN] Expanduser 경로: {file_path}")

        # 3단계: 다양한 방식으로 존재 여부 확인
        exists_check = file_path.exists()
        logger.info(f"[FILE_OPEN] Path.exists(): {exists_check}")

        # os.path로도 확인
        import os as os_module
        os_exists = os_module.path.exists(str(file_path))
        logger.info(f"[FILE_OPEN] os.path.exists(): {os_exists}")

        # stat으로 직접 확인
        stat_exists = False
        stat_result = None
        try:
            stat_result = file_path.stat()
            stat_exists = True
            logger.info(f"[FILE_OPEN] stat() 성공: {stat_result}")
        except FileNotFoundError:
            logger.error(f"[FILE_OPEN] stat() FileNotFoundError")
        except OSError as e:
            logger.error(f"[FILE_OPEN] stat() OSError: {e}")

        # 4단계: 어느 방식이든 존재하면 열기
        if not (exists_check or os_exists or stat_exists):
            logger.error(f"[FILE_OPEN] 모든 확인 방식에서 파일 없음: {file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파일을 찾을 수 없습니다: {file_path}",
            )

        # 5단계: 파일인지 확인
        is_file_check = file_path.is_file()
        logger.info(f"[FILE_OPEN] is_file(): {is_file_check}")

        if not is_file_check and stat_exists and stat_result:
            # stat은 성공했는데 is_file이 False면 특별 처리
            logger.warning(f"[FILE_OPEN] stat은 성공했지만 is_file()은 False")
            # 그래도 진행하자
        elif not is_file_check:
            logger.error(f"[FILE_OPEN] 파일이 아님: {file_path}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"파일이 아닙니다: {file_path}",
            )

        # 운영체제별 파일 열기
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                subprocess.Popen(["open", str(file_path)])
            elif system == "Windows":
                os.startfile(file_path)
            elif system == "Linux":
                subprocess.Popen(["xdg-open", str(file_path)])
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"지원하지 않는 운영체제입니다: {system}",
                )

            return FileOpenResponse(
                success=True,
                message=f"파일을 열었습니다: {file_path.name}",
                path=str(file_path),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"파일을 열 수 없습니다: {str(exc)}",
            ) from exc

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파일 열기 실패: {str(exc)}",
        ) from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
