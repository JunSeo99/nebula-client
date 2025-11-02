"""OCR helpers for extracting prominent text from images."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence


class OcrExtractionError(RuntimeError):
    """Raised when OCR processing fails."""


_OCR_READER = None


def _load_easyocr_reader():
    """Lazily instantiate an EasyOCR reader for Korean and English."""

    global _OCR_READER

    if _OCR_READER is not None:
        return _OCR_READER

    try:
        import easyocr  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise OcrExtractionError("EasyOCR 라이브러리를 찾을 수 없습니다.") from exc

    try:
        _OCR_READER = easyocr.Reader(["ko", "en"])  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - library specific error
        raise OcrExtractionError("EasyOCR 리더 초기화에 실패했습니다.") from exc

    return _OCR_READER


def _calculate_box_height(bbox: Sequence[Sequence[float]]) -> float:
    """Return an approximate text height from an OCR bounding box."""

    if len(bbox) < 2:
        return 0.0

    y_coords = [point[1] for point in bbox]
    height = max(y_coords) - min(y_coords)
    return float(height)


def _normalize_lines(candidates: Iterable[str]) -> List[str]:
    """Trim, collapse whitespace, deduplicate while preserving order."""

    normalized: List[str] = []
    seen: set[str] = set()
    for raw in candidates:
        cleaned = re.sub(r"\s+", " ", raw).strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def extract_ocr_titles(path: str, *, size_ratio: float = 0.8) -> List[str]:
    """Return OCR text lines whose height is above ``size_ratio`` of the maximum."""

    if size_ratio <= 0 or size_ratio > 1:
        raise ValueError("size_ratio must be within (0, 1].")

    reader = _load_easyocr_reader()

    try:
        results = reader.readtext(path)  # type: ignore[attr-defined]
    except FileNotFoundError as exc:
        raise OcrExtractionError("이미지 파일을 찾을 수 없습니다.") from exc
    except Exception as exc:  # pragma: no cover - upstream specific
        raise OcrExtractionError("이미지에서 텍스트를 추출하지 못했습니다.") from exc

    if not results:
        return []

    heights = [_calculate_box_height(bbox) for bbox, *_ in results]
    heights = [height for height in heights if height > 0]
    if not heights:
        return []

    max_height = max(heights)
    threshold = max_height * size_ratio

    filtered: List[str] = []
    for (bbox, text, _confidence) in results:
        if not text or not text.strip():
            continue
        height = _calculate_box_height(bbox)
        if height >= threshold:
            filtered.append(text)

    return _normalize_lines(filtered)


__all__ = [
    "OcrExtractionError",
    "extract_ocr_titles",
]
