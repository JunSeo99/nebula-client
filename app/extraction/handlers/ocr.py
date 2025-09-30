# -*- coding: utf-8 -*-
import easyocr
import numpy as np


def calculate_font_size(bbox):
    """좌표를 이용해 폰트 크기 계산"""
    # bbox는 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 형태
    x_coords = [point[0] for point in bbox]
    y_coords = [point[1] for point in bbox]

    width = max(x_coords) - min(x_coords)
    height = max(y_coords) - min(y_coords)

    # 폰트 크기는 높이를 기준으로 계산 (일반적으로 높이가 폰트 크기와 비례)
    return height


def process_ocr_results(results, top_n=5):
    """OCR 결과를 폰트 크기순으로 정렬하고 상위 N개만 반환"""
    all_results = []

    for (bbox, text, confidence) in results:
        font_size = calculate_font_size(bbox)
        all_results.append({
            'text': text,
            'confidence': confidence,
            'font_size': font_size,
            'bbox': bbox
        })

    # 폰트 크기순으로 정렬 (큰 것부터)
    all_results.sort(key=lambda x: x['font_size'], reverse=True)

    # 상위 N개만 반환
    return all_results[:top_n]


# EasyOCR 초기화 (한국어, 영어 지원)
reader = easyocr.Reader(['ko', 'en'])

# images 폴더의 모든 이미지 파일 처리
import os
import glob

# images 폴더의 이미지 파일들 찾기
image_files = glob.glob("images/*.png") + glob.glob("images/*.jpg") + glob.glob("images/*.jpeg")

for image_file in image_files:
    print(f"\n=== {os.path.basename(image_file)} (폰트 크기순 상위 5개) ===")

    try:
        # 이미지 OCR 실행
        result = reader.readtext(image_file)
        filtered_results = process_ocr_results(result, top_n=5)

        for i, item in enumerate(filtered_results, 1):
            print(f"{i}. {item['text']}")

    except Exception as e:
        print(f"오류 발생: {e}")
