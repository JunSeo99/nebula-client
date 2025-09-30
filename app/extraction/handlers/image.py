# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121  # (CUDA 환경인 경우 예시)
# pip install transformers pillow requests tqdm
# 한글 번역까지 원하면:

# git_caption.py
# -*- coding: utf-8 -*-
import argparse
import os
import io
import glob
import sys
from typing import List, Optional

import torch
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

import requests
from transformers import (
    AutoProcessor,
    AutoModelForCausalLM,
)


def load_image_from_path(path: str) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGB")
    except (FileNotFoundError, UnidentifiedImageError):
        return None


def load_image_from_url(url: str, timeout: float = 20.0) -> Optional[Image.Image]:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def init_git_model(model_name: str = "microsoft/git-base", dtype: str = "auto"):
    """
    dtype: "auto" | "fp16" | "fp32"  (fp16은 CUDA 필요)
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if dtype == "fp16":
        torch_dtype = torch.float16
    elif dtype == "fp32":
        torch_dtype = torch.float32
    else:
        # auto: GPU면 fp16, 아니면 float32
        torch_dtype = torch.float16 if device == "cuda" else torch.float32

    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch_dtype,
    ).to(device)
    model.eval()
    return processor, model, device


def generate_caption(
        image: Image.Image,
        processor,
        model,
        device: str,
        max_length: int = 50,
        num_beams: int = 3,
        do_sample: bool = False,
) -> str:
    """
    GIT 모델로 영어 캡션 생성
    """
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_length=max_length,
            num_beams=num_beams,
            do_sample=do_sample,
            early_stopping=True,
        )
    caption = processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()
    return caption


def list_images_in_dir(dir_path: str) -> List[str]:
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.tiff"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(dir_path, p)))
    files.sort()
    return files


def run_single_image(
        image: Image.Image,
        processor,
        model,
        device: str,
) -> str:
    en = generate_caption(image, processor, model, device)
    return en


def main():
    parser = argparse.ArgumentParser(
        description="Image captioning with microsoft/git-base"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--path", type=str, help="Local image file path")
    group.add_argument("--url", type=str, help="Image URL")
    group.add_argument("--dir", type=str, help="Directory containing images")

    parser.add_argument("--dtype", type=str, default="auto", choices=["auto", "fp16", "fp32"],
                        help="Computation dtype (auto/fp16/fp32)")
    parser.add_argument("--max-length", type=int, default=50, help="Max tokens for caption")
    parser.add_argument("--num-beams", type=int, default=3, help="Beam search width")
    parser.add_argument("--sample", action="store_true", help="Use sampling instead of pure beam search")
    parser.add_argument("--model", type=str, default="microsoft/git-base", help="GIT model name")

    args = parser.parse_args()

    try:
        processor, model, device = init_git_model(args.model, args.dtype)
    except Exception as e:
        print(f"[ERR] Failed to load model ({args.model}): {e}", file=sys.stderr)
        sys.exit(1)

    if args.path:
        img = load_image_from_path(args.path)
        if img is None:
            print(f"[ERR] Cannot open image: {args.path}", file=sys.stderr)
            sys.exit(2)
        en = generate_caption(img, processor, model, device,
                              max_length=args.max_length,
                              num_beams=args.num_beams,
                              do_sample=args.sample)
        print(f"[EN] {en}")

    elif args.url:
        img = load_image_from_url(args.url)
        if img is None:
            print(f"[ERR] Cannot fetch image from URL: {args.url}", file=sys.stderr)
            sys.exit(3)
        en = generate_caption(img, processor, model, device,
                              max_length=args.max_length,
                              num_beams=args.num_beams,
                              do_sample=args.sample)
        print(f"[EN] {en}")

    elif args.dir:
        files = list_images_in_dir(args.dir)
        if not files:
            print(f"[ERR] No images found in: {args.dir}", file=sys.stderr)
            sys.exit(4)

        print(f"\n폴더: {args.dir}")
        print("=" * 50)

        for fp in tqdm(files, desc="Captioning"):
            img = load_image_from_path(fp)
            if img is None:
                print(f"[SKIP] {fp} (unreadable)")
                continue
            en = generate_caption(img, processor, model, device,
                                  max_length=args.max_length,
                                  num_beams=args.num_beams,
                                  do_sample=args.sample)

            # 파일명만 추출 (경로 제거)
            filename = fp.split('\\')[-1] if '\\' in fp else fp.split('/')[-1]
            print(f"\n{filename}")
            print(f"{en}")
            print("-" * 30)


if __name__ == "__main__":
    main()
