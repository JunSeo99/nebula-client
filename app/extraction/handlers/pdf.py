"""Utilities for extracting text and keywords from PDF documents."""

from __future__ import annotations

import re
from typing import List

from app.services.keyword_extraction import keybert_analyze


class PdfExtractionError(RuntimeError):
    """Raised when PDF processing fails."""


def _load_pymupdf():
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise PdfExtractionError("PyMuPDF(fitz) 라이브러리를 찾을 수 없습니다.") from exc
    return fitz


def extract_pdf_head_text(path: str, n_pages: int = 1) -> str:
    """Return plain text extracted from the first ``n_pages`` of a PDF file."""

    fitz = _load_pymupdf()

    try:
        with fitz.open(path) as doc:
            pages = min(max(n_pages, 1), doc.page_count)
            parts: List[str] = []
            for index in range(pages):
                page = doc.load_page(index)
                parts.append(page.get_text("text") or "")
    except (RuntimeError, ValueError, OSError) as exc:
        raise PdfExtractionError("PDF 파일에서 텍스트를 읽을 수 없습니다.") from exc

    text = "\n".join(parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_keywords(
    path: str,
    *,
    max_pages: int = 3,
    top_keywords: int = 5,
) -> List[str]:
    """Extract representative keywords from the beginning of a PDF document."""

    text = extract_pdf_head_text(path, n_pages=max_pages)
    if not text:
        return []

    try:
        keywords, _ = keybert_analyze(text, top_n_keywords=top_keywords)
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise PdfExtractionError("PDF 키워드 추출 중 오류가 발생했습니다.") from exc

    return [keyword for keyword, score in keywords if keyword]


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
