"""Image utilities combining OCR highlights and caption generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.extraction.handlers.ocr import OcrExtractionError, extract_ocr_titles


class ImageExtractionError(RuntimeError):
    """Raised when image processing fails."""


@dataclass(frozen=True)
class ImageHighlights:
    """Bundle OCR-derived lines and an optional caption for an image."""

    ocr_lines: List[str]
    caption: Optional[str] = None


_CAPTION_PIPELINE: Optional[tuple[object, object, str]] = None


def _load_image(path: str):
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImageExtractionError("Pillow 라이브러리를 찾을 수 없습니다.") from exc

    try:
        return Image.open(path).convert("RGB")
    except FileNotFoundError as exc:
        raise ImageExtractionError("이미지 파일을 찾을 수 없습니다.") from exc
    except Exception as exc:  # pragma: no cover - image specific error
        raise ImageExtractionError("이미지 파일을 열지 못했습니다.") from exc


def _load_caption_pipeline(model_name: str = "microsoft/git-base"):
    global _CAPTION_PIPELINE

    if _CAPTION_PIPELINE is not None:
        return _CAPTION_PIPELINE

    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoProcessor  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImageExtractionError("이미지 캡셔닝을 위해 torch 및 transformers가 필요합니다.") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)
        model = model.to(device)
        model.eval()
    except Exception as exc:  # pragma: no cover - model load error
        raise ImageExtractionError("이미지 캡셔닝 모델 로드에 실패했습니다.") from exc

    _CAPTION_PIPELINE = (processor, model, device)
    return _CAPTION_PIPELINE


def generate_image_caption(path: str, *, max_length: int = 64) -> Optional[str]:
    """Generate a caption for an image file using a vision-language model."""

    try:
        image = _load_image(path)
    except ImageExtractionError:
        raise

    try:
        import torch  # type: ignore
    except ImportError:
        raise ImageExtractionError("이미지 캡셔닝을 위해 torch가 필요합니다.")

    try:
        processor, model, device = _load_caption_pipeline()
    except ImageExtractionError:
        raise

    try:
        inputs = processor(images=image, return_tensors="pt")  # type: ignore[call-arg]
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            output_ids = model.generate(  # type: ignore[attr-defined]
                **inputs,
                max_length=max_length,
                num_beams=3,
                do_sample=False,
                early_stopping=True,
            )
    except Exception as exc:  # pragma: no cover - inference error
        raise ImageExtractionError("이미지 캡션 생성 중 오류가 발생했습니다.") from exc

    try:
        caption = processor.batch_decode(output_ids, skip_special_tokens=True)[0]
    except Exception as exc:  # pragma: no cover
        raise ImageExtractionError("생성된 캡션을 해석하지 못했습니다.") from exc

    return caption.strip()


def extract_image_highlights(path: str, *, size_ratio: float = 0.8) -> ImageHighlights:
    """Return OCR-derived lines and an optional caption for the image."""

    try:
        ocr_lines = extract_ocr_titles(path, size_ratio=size_ratio)
    except OcrExtractionError as exc:
        raise ImageExtractionError("이미지에서 텍스트를 추출하지 못했습니다.") from exc

    caption: Optional[str]
    try:
        caption = generate_image_caption(path)
    except ImageExtractionError:
        caption = None

    normalized_caption: Optional[str] = None
    if caption:
        normalized_caption = " ".join(caption.split()).strip()
        if not normalized_caption:
            normalized_caption = None

    return ImageHighlights(ocr_lines=ocr_lines, caption=normalized_caption)


__all__ = [
    "ImageExtractionError",
    "ImageHighlights",
    "extract_image_highlights",
    "generate_image_caption",
]
