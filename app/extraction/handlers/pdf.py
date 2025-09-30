"""Utilities for extracting prominent text segments from PDF documents."""

from __future__ import annotations

import re
from typing import List


class PdfExtractionError(RuntimeError):
    """Raised when PDF processing fails."""


def _load_pymupdf():
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise PdfExtractionError("PyMuPDF(fitz) 라이브러리를 찾을 수 없습니다.") from exc
    return fitz


def extract_pdf_head_text(path: str, n_pages: int = 1) -> List[str]:
    """Return title-like text extracted from the first ``n_pages`` of a PDF file."""

    fitz = _load_pymupdf()

    try:
        with fitz.open(path) as doc:
            pages = min(max(n_pages, 1), doc.page_count)
            plain_text_parts: List[str] = []
            page_dicts = []
            font_sizes: List[float] = []

            for index in range(pages):
                page = doc.load_page(index)
                plain_text_parts.append(page.get_text("text") or "")

                page_dict = page.get_text("dict")
                page_dicts.append(page_dict)

                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "")
                            size = span.get("size")
                            if not text or not text.strip():
                                continue
                            if size is None:
                                continue
                            font_sizes.append(float(size))
    except (RuntimeError, ValueError, OSError) as exc:
        raise PdfExtractionError("PDF 파일에서 텍스트를 읽을 수 없습니다.") from exc

    extracted_lines: List[str] = []

    if font_sizes:
        max_size = max(font_sizes)
        threshold = max_size * 0.8

        for page_dict in page_dicts:
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    span_texts: List[str] = []
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        size = span.get("size")
                        if not text or not text.strip():
                            continue
                        if size is None:
                            continue
                        span_size = float(size)
                        if span_size >= threshold:
                            span_texts.append(text)
                    if span_texts:
                        line_text = "".join(span_texts).strip()
                        if line_text:
                            extracted_lines.append(line_text)

    if not extracted_lines:
        fallback = "\n".join(plain_text_parts)
        fallback = re.sub(r"[ \t]+\n", "\n", fallback)
        fallback = re.sub(r"\n{3,}", "\n\n", fallback)
        extracted_lines = [
            line.strip()
            for line in fallback.splitlines()
            if line.strip()
        ]

    normalized: List[str] = []
    seen = set()
    for line in extracted_lines:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    return normalized


def extract_pdf_keywords(
    path: str,
    *,
    max_pages: int = 1,
    top_keywords: int = 5,
) -> List[str]:
    """Return prominent text lines from the beginning of a PDF document."""

    try:
        return extract_pdf_head_text(path, n_pages=max_pages)
    except PdfExtractionError:
        raise
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise PdfExtractionError("PDF 제목 텍스트 추출 중 오류가 발생했습니다.") from exc


def split_sentences_ko(text: str) -> List[str]:
    """Fallback Korean sentence splitter used by keyword extraction."""

    text = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[\.!\?])\s+(?=[가-힣A-Z0-9])", text)
    normalized: List[str] = []
    for sentence in sentences:
        normalized.extend(re.split(r"(?<=다\.)\s+(?=[가-힣A-Z0-9])", sentence))
    return [sentence.strip() for sentence in normalized if len(sentence.strip()) >= 8]


__all__ = [
    "PdfExtractionError",
    "extract_pdf_head_text",
    "extract_pdf_keywords",
    "split_sentences_ko",
]
