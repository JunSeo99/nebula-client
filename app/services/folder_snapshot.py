"""Generate JSON snapshots for directory contents via recursive traversal."""

from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from app.extraction.handlers.image import (
    ImageExtractionError,
    ImageHighlights,
    extract_image_highlights,
)
from app.extraction.handlers.pdf import PdfExtractionError, extract_pdf_keywords
from app.extraction.handlers.xls import (
    SpreadsheetExtractionError,
    build_summary_text,
)
from app.services.folder_inspection import DirectoryInspectionError, resolve_directory
from app.services.snapshot_delivery import send_snapshot_payload


logger = logging.getLogger(__name__)

_SNAPSHOT_ENV_VAR = "SNAPSHOT_DIR"
_DEFAULT_SNAPSHOT_DIR = "snapshots"
_AUTO_BATCH_SIZE = 50

_DEVELOPMENT_DIRECTORY_MARKERS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "node_modules",
}

_DEVELOPMENT_FILE_MARKERS = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
}


_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")


@dataclass(frozen=True)
class FileInsights:
    """Aggregated metadata used when prompting downstream GPT APIs."""

    highlights: List[str]
    caption: Optional[str] = None

@dataclass(frozen=True)
class SnapshotEntry:
    """Structured metadata describing a filesystem entry."""

    relative_path: str
    absolute_path: str
    is_directory: bool
    size_bytes: int
    modified_at: datetime
    is_development: bool = False

    @classmethod
    def from_path(cls, root: Path, path: Path, *, is_development: bool = False) -> "SnapshotEntry":
        try:
            stats = path.stat()
        except FileNotFoundError as exc:
            raise DirectoryInspectionError("스냅샷 대상 파일을 찾을 수 없습니다.") from exc
        except PermissionError as exc:
            raise DirectoryInspectionError("파일에 접근 권한이 없습니다.") from exc

        is_directory = path.is_dir()
        return cls(
            relative_path=str(path.relative_to(root)),
            absolute_path=str(path),
            is_directory=is_directory,
            size_bytes=0 if is_directory else stats.st_size,
            modified_at=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
            is_development=is_development,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "absolute_path": self.absolute_path,
            "is_directory": self.is_directory,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at.isoformat(),
            "is_development": self.is_development,
        }


@dataclass(frozen=True)
class SnapshotPage:
    """Represents a single JSON snapshot file for a directory."""

    page: int
    path: Path
    entry_count: int


@dataclass(frozen=True)
class FolderSnapshotResult:
    """Outcome details for a directory snapshot request."""

    directory: str
    generated_at: datetime
    total_entries: int
    page_size: Optional[int]
    pages: List[SnapshotPage]
    development_directories: List[SnapshotEntry] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


def snapshot_directory(raw_path: str, page_size: Optional[int] = None) -> FolderSnapshotResult:
    """Traverse a directory recursively and persist metadata snapshots to disk."""

    directory = resolve_directory(raw_path)
    logger.info('디렉터리 스냅샷 시작: path=%s, page_size=%s', directory, page_size)
    entries = list(_iter_snapshot_entries(directory))
    logger.info('항목 수집 완료: path=%s, entries=%d', directory, len(entries))
    generated_at = datetime.now(timezone.utc)

    effective_page_size = _determine_page_size(entries, page_size)

    chunks = _chunk_entries(entries, effective_page_size)
    if not chunks:
        chunks = [entries]

    snapshot_root = _ensure_snapshot_root()
    pages: List[SnapshotPage] = []

    for index, chunk in enumerate(chunks, start=1):
        output_path = _build_snapshot_path(snapshot_root, directory, generated_at, index, len(chunks))
        logger.info(
            '스냅샷 파일 생성: path=%s, page=%d/%d, entries=%d',
            output_path,
            index,
            len(chunks),
            len(chunk),
        )
        page_payload = _serialize_snapshot_page(

            directory=directory,
            generated_at=generated_at,
            total_entries=len(entries),
            page_index=index,
            page_count=len(chunks),
            page_size=effective_page_size,
            entries=chunk,
        )
        send_snapshot_payload(page_payload)
        _write_snapshot_file(
            output_path=output_path,
            directory=directory,
            generated_at=generated_at,
            total_entries=len(entries),
            page_index=index,
            page_count=len(chunks),
            page_size=effective_page_size,
            entries=chunk,
        )
        pages.append(SnapshotPage(page=index, path=output_path, entry_count=len(chunk)))

    return FolderSnapshotResult(
        directory=str(directory),
        generated_at=generated_at,
        total_entries=len(entries),
        page_size=effective_page_size,
        pages=pages,
        development_directories=[entry for entry in entries if entry.is_development],
    )


def _ensure_snapshot_root() -> Path:
    configured = os.getenv(_SNAPSHOT_ENV_VAR, _DEFAULT_SNAPSHOT_DIR)
    root = Path(configured).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DirectoryInspectionError("스냅샷 디렉터리를 생성할 수 없습니다.") from exc
    return root


def _iter_snapshot_entries(root: Path) -> Iterable[SnapshotEntry]:
    def walk(current: Path) -> Iterable[SnapshotEntry]:
        try:
            children = [child for child in current.iterdir() if not child.name.startswith(".")]
        except PermissionError as exc:
            raise DirectoryInspectionError("디렉터리에 접근 권한이 없습니다.") from exc

        directories: list[Path] = []
        files: list[Path] = []

        for child in children:
            if child.is_dir():
                directories.append(child)
            else:
                files.append(child)

        directories.sort(key=lambda path: path.name.lower())
        files.sort(key=lambda path: path.name.lower())

        for directory_path in directories:
            is_development = _is_development_directory(directory_path)
            if is_development:
                yield SnapshotEntry.from_path(
                    root,
                    directory_path,
                    is_development=True,
                )
                continue
            # 가장 깊은 경로부터 순차적으로 처리하기 위해 먼저 하위 항목을 순회한다.
            yield from walk(directory_path)
            yield SnapshotEntry.from_path(root, directory_path)

        for file_path in files:
            yield SnapshotEntry.from_path(root, file_path)

    yield from walk(root)


def _is_development_directory(path: Path) -> bool:
    """Return True when directory appears to be a development project root."""

    for marker in _DEVELOPMENT_DIRECTORY_MARKERS:
        candidate = path / marker
        try:
            if candidate.exists():
                return True
        except OSError:
            continue

    for marker in _DEVELOPMENT_FILE_MARKERS:
        candidate = path / marker
        try:
            if candidate.is_file():
                return True
        except OSError:
            continue

    return False


def _chunk_entries(entries: list[SnapshotEntry], page_size: Optional[int]) -> list[list[SnapshotEntry]]:
    if page_size is None or page_size <= 0:
        return [entries]

    chunks: list[list[SnapshotEntry]] = []
    for start in range(0, len(entries), page_size):
        chunks.append(entries[start : start + page_size])
    return chunks


def _determine_page_size(
    entries: list[SnapshotEntry], page_size: Optional[int]
) -> Optional[int]:
    if page_size is not None and page_size > 0:
        return page_size

    if len(entries) >= _AUTO_BATCH_SIZE:
        return _AUTO_BATCH_SIZE

    return page_size


def _build_snapshot_path(
    snapshot_root: Path,
    directory: Path,
    generated_at: datetime,
    page_index: int,
    page_count: int,
) -> Path:
    slug = directory.name or "root"
    safe_slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in slug)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    suffix = f"_p{page_index:03d}" if page_count > 1 else ""
    filename = f"{safe_slug}_{timestamp}{suffix}.json"
    return snapshot_root / filename


def _write_snapshot_file(
    output_path: Path,
    directory: Path,
    generated_at: datetime,
    total_entries: int,
    page_index: int,
    page_count: int,
    page_size: Optional[int],
    entries: list[SnapshotEntry],
) -> None:
    payload = {
        "directory": str(directory),
        "generated_at": generated_at.isoformat(),
        "page": page_index,
        "page_count": page_count,
        "page_size": page_size,
        "total_entries": total_entries,
        "entries": [entry.to_dict() for entry in entries],
    }

    try:
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
    except OSError as exc:
        raise DirectoryInspectionError("스냅샷 파일을 저장할 수 없습니다.") from exc


def _serialize_snapshot_page(
    *,
    directory: Path,
    generated_at: datetime,
    total_entries: int,
    page_index: int,
    page_count: int,
    page_size: Optional[int],
    entries: list[SnapshotEntry],
) -> dict[str, object]:
    """Convert a snapshot page into a camelCase payload for the remote server."""

    file_insights = _collect_file_insights(entries)

    return {
        "directory": str(directory),
        "generatedAt": generated_at.isoformat(),
        "page": page_index,
        "pageCount": page_count,
        "pageSize": page_size,
        "totalEntries": total_entries,
        "userId": '621c7d3957c2ea5b9063d04c',
        "entries": [
            _serialize_snapshot_entry(entry, file_insights.get(entry.absolute_path))
            for entry in entries
        ],
    }


def _serialize_snapshot_entry(
    entry: SnapshotEntry,
    insights: Optional[FileInsights],
) -> dict[str, object]:
    payload = {
        "relativePath": entry.relative_path,
        "absolutePath": entry.absolute_path,
        "isDirectory": entry.is_directory,
        "sizeBytes": entry.size_bytes,
        "modifiedAt": entry.modified_at.isoformat(),
        "isDevelopment": entry.is_development,
    }
    if insights:
        if insights.highlights:
            payload["keywords"] = insights.highlights
        if insights.caption:
            payload["caption"] = insights.caption

    return payload


def _collect_file_insights(entries: list[SnapshotEntry]) -> dict[str, FileInsights]:
    """Return a mapping of absolute paths to extracted highlights and prompts."""

    insights: dict[str, FileInsights] = {}
    for entry in entries:
        if entry.is_directory:
            continue

        absolute_path = entry.absolute_path
        lower_path = absolute_path.lower()

        try:
            if lower_path.endswith(".pdf"):
                highlights = extract_pdf_keywords(absolute_path)
                if not highlights:
                    continue
                insights[absolute_path] = FileInsights(
                    highlights=highlights,
                    caption=None,
                )
            elif lower_path.endswith(_IMAGE_EXTENSIONS):
                image_highlights = extract_image_highlights(absolute_path)
                combined_lines = list(image_highlights.ocr_lines)

                if image_highlights.caption:
                    if image_highlights.caption not in combined_lines:
                        combined_lines.append(image_highlights.caption)

                if not combined_lines:
                    continue
                insights[absolute_path] = FileInsights(
                    highlights=combined_lines,
                    caption=image_highlights.caption,
                )
            elif lower_path.endswith((".xlsx", ".xls", ".xlsm", ".csv")):
                summary_text, signals = build_summary_text(absolute_path)
                summary_text = summary_text.strip()

                candidate_highlights: list[str] = []
                seen_highlights: set[str] = set()
                for value in (
                    signals.sections
                    + signals.banner
                    + signals.headers
                    + signals.samples
                ):
                    cleaned = value.strip()
                    if not cleaned:
                        continue
                    lowered = cleaned.lower()
                    if lowered in seen_highlights:
                        continue
                    candidate_highlights.append(cleaned)
                    seen_highlights.add(lowered)
                    if len(candidate_highlights) >= 40:
                        break

                if not candidate_highlights and summary_text:
                    candidate_highlights.append(summary_text)

                if not candidate_highlights:
                    continue

                insights[absolute_path] = FileInsights(
                    highlights=candidate_highlights,
                    caption=summary_text or None,
                )


        except PdfExtractionError as exc:
            logger.warning(
                "PDF 키워드 추출 실패: path=%s, error=%s",
                absolute_path,
                exc,
            )
        except ImageExtractionError as exc:
            logger.warning(
                "이미지 하이라이트 추출 실패: path=%s, error=%s",
                absolute_path,
                exc,
            )
        except SpreadsheetExtractionError as exc:
            logger.warning(
                "스프레드시트 요약 생성 실패: path=%s, error=%s",
                absolute_path,
                exc,
            )

    return insights
