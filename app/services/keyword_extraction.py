"""
keyword_extractor.py
- KeyBERT로 한국어 키워드/핵심문장 추출
- 모델 로딩은 모듈 전역에서 1회만 실행(캐싱)
"""

from __future__ import annotations
from typing import List, Tuple

# sentence_splitter 모듈이 있으면 우선 사용, 없으면 로컬 구현 사용
try:
    from .sentence_splitter import split_sentences_ko  # type: ignore
except Exception:
    import re

    def split_sentences_ko(text: str) -> List[str]:
        """마침표/물음표/느낌표 기준 단문 분할 (아주 단순 버전)."""
        if not text or not text.strip():
            return []
        sentence_endings = r"[.!?]+"
        sentences = re.split(sentence_endings, text)
        return [s.strip() for s in sentences if s.strip()]

# --- KeyBERT/Embedding 준비 (전역 캐시) ---
_KEYBERT = None
_SENT_EMBED = None
_MODEL_NAME = "jhgan/ko-sroberta-multitask"


def _get_models():
    """KeyBERT와 SentenceTransformer를 전역으로 1회 로드."""
    global _KEYBERT, _SENT_EMBED
    if _KEYBERT is None or _SENT_EMBED is None:
        from sentence_transformers import SentenceTransformer
        from keybert import KeyBERT

        _SENT_EMBED = SentenceTransformer(_MODEL_NAME)
        _KEYBERT = KeyBERT(model=_SENT_EMBED)
    return _KEYBERT, _SENT_EMBED


def keybert_analyze(
    text: str,
    top_n_keywords: int = 5,
) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    """
    입력 텍스트에서 키워드(top_n)와 핵심문장(각 문장당 1개 후보)을 추출.

    Returns:
        keywords: [(키워드, 점수), ...] 길이 top_n
        key_sents: [(핵심문 후보(문장 일부 또는 n-gram), 점수), ...] 문장 수만큼 or 비어있음
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    text = text.replace("\x00", " ")  # 혹시 입력 문자열에 null byte가 섞였을 경우 예방

    kb, _ = _get_models()

    # 1) 키워드 추출 (단일 단어 n-gram)
    keywords: List[Tuple[str, float]] = kb.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 1),
        use_mmr=False,
        top_n=top_n_keywords,
    )

    # 2) 문장 분할 후, 각 문장에서 긴 n-gram 기반 핵심 구절 1개씩 추출
    sents = split_sentences_ko(text)
    key_sents: List[Tuple[str, float]] = []

    if sents:
        # KeyBERT는 리스트 입력 시 문서별 결과 리스트를 반환한다.
        # 여기서는 각 문장마다 top_n=1로 1개씩만 뽑아서 평탄화한다.
        per_sent = kb.extract_keywords(
            sents,
            keyphrase_ngram_range=(5, 10),  # 긴 구절 위주
            use_mmr=False,
            top_n=1,
        )
        # per_sent는 [[(phrase, score)] , [(phrase, score)], ...] 형태
        for items in per_sent:
            if items:
                key_sents.append(items[0])

    return keywords, key_sents


__all__ = ["keybert_analyze", "split_sentences_ko"]