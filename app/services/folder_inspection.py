"""Services to inspect directories and retrieve file metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from app.schemas.folder import FileInfo, FolderContentsResponse
from app.schemas.organized_file import (
    OrganizedFileEntry,
    ParaBucket,
    FileEntryForGeneration,
)

logger = logging.getLogger(__name__)


class DirectoryInspectionError(Exception):
    """Raised when a directory cannot be inspected."""


@dataclass(frozen=True)
class DirectoryEntry:
    """Internal representation of a directory entry."""

    name: str
    path: Path
    is_directory: bool
    size_bytes: int
    modified_at: datetime
    keywords: List[str] = None  # ML 추출된 키워드
    is_development: bool = False  # 개발 관련 파일 여부

    def __post_init__(self):
        if self.keywords is None:
            object.__setattr__(self, 'keywords', [])

    @classmethod
    def from_path(cls, entry_path: Path, keywords: Optional[List[str]] = None, is_development: bool = False) -> "DirectoryEntry":
        stats = entry_path.stat()
        return cls(
            name=entry_path.name,
            path=entry_path,
            is_directory=entry_path.is_dir(),
            size_bytes=0 if entry_path.is_dir() else stats.st_size,
            modified_at=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
            keywords=keywords or [],
            is_development=is_development,
        )


def _normalize_directory(raw_path: str) -> Path:
    try:
        normalized = Path(raw_path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise DirectoryInspectionError("해당 경로가 존재하지 않습니다.") from exc

    if not normalized.is_dir():
        raise DirectoryInspectionError("디렉터리 경로를 선택해주세요.")

    return normalized


def resolve_directory(raw_path: str) -> Path:
    """Return a normalized directory path or raise a descriptive error."""

    return _normalize_directory(raw_path)


def _iter_directory_entries(directory: Path) -> Iterable[DirectoryEntry]:
    try:
        for entry in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith("."):
                continue
            yield DirectoryEntry.from_path(entry)
    except PermissionError as exc:
        raise DirectoryInspectionError("디렉터리에 접근 권한이 없습니다.") from exc


def _get_file_type(path: Path) -> Optional[str]:
    """파일 타입 결정"""
    suffix = path.suffix.lower()

    type_mapping = {
        ".pdf": "pdf",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".webp": "image",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".csv": "csv",
        ".md": "markdown",
        ".txt": "text",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
    }

    return type_mapping.get(suffix)


def _is_development_file(path: Path) -> bool:
    """개발 관련 파일 여부 판단"""
    development_markers = {
        ".git", ".hg", ".svn", ".idea", ".vscode", ".venv",
        "node_modules", "package.json", "pyproject.toml",
        "setup.py", "requirements.txt", "Cargo.toml", "go.mod",
    }

    name_lower = path.name.lower()
    return any(marker in name_lower for marker in development_markers)


async def _extract_file_keywords(file_path: Path) -> List[str]:
    """파일에서 키워드 추출"""
    keywords = []

    try:
        file_type = _get_file_type(file_path)

        if file_type == "pdf":
            from app.extraction.handlers.pdf import extract_pdf_keywords
            try:
                keywords = extract_pdf_keywords(str(file_path), max_pages=1, top_keywords=5)
            except Exception as exc:
                logger.warning(f"PDF 키워드 추출 실패: {file_path}: {exc}")

        elif file_type == "image":
            from app.extraction.handlers.image import extract_image_highlights
            try:
                highlights = extract_image_highlights(str(file_path))
                keywords = highlights.ocr_lines[:5]  # 상위 5개
            except Exception as exc:
                logger.warning(f"이미지 키워드 추출 실패: {file_path}: {exc}")

        elif file_type in ("xlsx", "csv"):
            from app.extraction.handlers.xls import build_summary_text
            try:
                summary, _ = build_summary_text(str(file_path))
                if summary:
                    keywords = [summary]
            except Exception as exc:
                logger.warning(f"스프레드시트 키워드 추출 실패: {file_path}: {exc}")

        elif file_type == "markdown" or file_type == "text":
            # 텍스트 파일: 제목이나 첫 줄 추출
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline().strip()
                    if first_line and not first_line.startswith('#'):
                        keywords = [first_line[:100]]  # 첫 100자
                    elif first_line.startswith('# '):
                        keywords = [first_line[2:].strip()]  # 제목
            except Exception as exc:
                logger.warning(f"텍스트 파일 키워드 추출 실패: {file_path}: {exc}")

    except Exception as exc:
        logger.warning(f"예상치 못한 키워드 추출 에러: {file_path}: {exc}")

    return keywords[:5]  # 상위 5개만 반환


def inspect_directory(raw_path: str) -> FolderContentsResponse:
    """Return metadata for the immediate children of the provided directory."""

    directory = resolve_directory(raw_path)
    entries = [
        FileInfo(
            name=entry.name,
            path=str(entry.path),
            is_directory=entry.is_directory,
            size_bytes=entry.size_bytes,
            modified_at=entry.modified_at,
        )
        for entry in _iter_directory_entries(directory)
    ]

    return FolderContentsResponse(directory=str(directory), entries=entries)


async def inspect_directory_with_keywords(
    raw_path: str,
) -> tuple[FolderContentsResponse, List[DirectoryEntry]]:
    """
    Return metadata with extracted keywords for the immediate children.

    Returns:
        Tuple of (FolderContentsResponse, List of DirectoryEntry with keywords)
    """
    directory = resolve_directory(raw_path)
    entries_with_keywords = []

    for entry in _iter_directory_entries(directory):
        keywords = []

        # 파일인 경우에만 키워드 추출
        if not entry.is_directory:
            keywords = await _extract_file_keywords(entry.path)

        # 개발 여부 판단
        is_development = _is_development_file(entry.path)

        # 키워드가 포함된 DirectoryEntry 생성
        entry_with_keywords = DirectoryEntry.from_path(
            entry.path,
            keywords=keywords,
            is_development=is_development,
        )
        entries_with_keywords.append(entry_with_keywords)

    # 기존 FolderContentsResponse 생성
    file_info_list = [
        FileInfo(
            name=entry.name,
            path=str(entry.path),
            is_directory=entry.is_directory,
            size_bytes=entry.size_bytes,
            modified_at=entry.modified_at,
        )
        for entry in entries_with_keywords
    ]

    response = FolderContentsResponse(directory=str(directory), entries=file_info_list)

    return response, entries_with_keywords


def to_organized_file_entry(
    directory_root: Path,
    entry: DirectoryEntry,
    user_id: str,
) -> OrganizedFileEntry:
    """
    DirectoryEntry를 OrganizedFileEntry로 변환

    Args:
        directory_root: 루트 디렉터리
        entry: DirectoryEntry 객체
        user_id: 사용자 ID

    Returns:
        Spring 서버로 전송할 OrganizedFileEntry
    """
    # 파일명에서 확장자 제거
    name_without_ext = entry.path.stem

    # 간단한 한글/영문 파일명 생성
    korean_file_name = f"{name_without_ext}_{entry.path.suffix}"
    english_file_name = entry.name

    # PARA 버킷 판단 (기본값)
    if entry.is_development:
        para_bucket = ParaBucket.PROJECTS
    elif entry.keywords:
        # 키워드 기반 분류 (향후 개선)
        para_bucket = ParaBucket.RESOURCES
    else:
        para_bucket = ParaBucket.ARCHIVE

    # 상대 경로
    relative_path = str(entry.path.relative_to(directory_root))

    return OrganizedFileEntry(
        original_relative_path=relative_path,
        directory=entry.is_directory,
        development=entry.is_development,
        size_bytes=entry.size_bytes,
        modified_at=entry.modified_at,
        keywords=entry.keywords,
        korean_file_name=korean_file_name,
        english_file_name=english_file_name,
        para_bucket=para_bucket,
        para_folder=None,
        reason=f"Automatically organized by ML extraction. Keywords: {', '.join(entry.keywords) if entry.keywords else 'No keywords'}"
    )


def to_file_entry_for_generation(
    directory_root: Path,
    entry: DirectoryEntry,
) -> FileEntryForGeneration:
    """
    DirectoryEntry를 FileEntryForGeneration으로 변환 (새로운 Generation 포맷)

    Args:
        directory_root: 루트 디렉터리
        entry: DirectoryEntry 객체

    Returns:
        Spring 서버로 전송할 FileEntryForGeneration
    """
    # 상대 경로
    relative_path = str(entry.path.relative_to(directory_root))

    # 절대 경로
    absolute_path = str(entry.path.absolute())

    return FileEntryForGeneration(
        relative_path=relative_path,
        absolute_path=absolute_path,
        is_directory=entry.is_directory,
        size_bytes=entry.size_bytes,
        modified_at=entry.modified_at.isoformat(),  # ISO 8601 형식 문자열로 변환
        is_development=entry.is_development,
        keywords=entry.keywords,
    )
