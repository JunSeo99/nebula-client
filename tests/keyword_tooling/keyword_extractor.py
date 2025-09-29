"""Keyword extraction utilities tailored for metadata-aware documents.

The module stays under ``tests/`` to avoid touching runtime code while still
providing production-grade logic that can be imported from tests or sandboxes.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Sequence

__all__ = [
    "KeywordExtractor",
    "extract_keywords",
]


_SENTENCE_SPLIT_REGEX = re.compile(r"[.!?\n]+")
_TOKEN_REGEX = re.compile(r"[A-Za-z0-9]+|[가-힣]+", re.UNICODE)
_CAMEL_CASE_REGEX = re.compile(r"(?<!^)(?=[A-Z])")

_DEFAULT_STOPWORDS = {
    # English stopwords
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    # Korean stopwords and particles
    "그리고",
    "그",  # this
    "그것",
    "그녀",
    "그러나",
    "그러면",
    "그런",
    "그럼",
    "그의",
    "그에",
    "그것은",
    "그들은",
    "나는",
    "내가",
    "너는",
    "너의",
    "너희",
    "당신",
    "당신의",
    "때문",
    "때문에",
    "또한",
    "또는",
    "때",
    "미만",
    "부터",
    "부터는",
    "으로",
    "으로서",
    "으로써",
    "에게",
    "에서",
    "에게는",
    "에게서",
    "에게서는",
    "와",
    "와는",
    "으로는",
    "의",
    "이",
    "이것",
    "이것은",
    "이런",
    "이는",
    "입니다",
    "있다",
    "있는",
    "있으며",
    "있어서",
    "있으면",
    "저",
    "저는",
    "저희",
    "저의",
    "저것",
    "저것은",
    "저희는",
    "저희의",
    "좀",
    "처럼",
    "하지만",
    "합니다",
    "했다",
    "했다",
    "한다",
    "하는",
}


@dataclass(frozen=True)
class KeywordCandidate:
    """Container holding the candidate phrase and associated scores."""

    phrase: str
    score: float
    weight: float


class KeywordExtractor:
    """Extracts representative keywords by combining RAKE-style statistics with
    optional semantic re-ranking.

    The extractor remains self-contained and dependency-light so it can execute
    inside testing sandboxes, yet it gracefully leverages ``sentence_transformers``
    if the package is available in the local environment.
    """

    def __init__(
        self,
        stopwords: Optional[Iterable[str]] = None,
        metadata_boost: float = 0.35,
        camel_case_boost: float = 0.15,
        semantic_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        enable_semantic_rerank: bool = True,
        metadata_only_penalty: float = 0.6,
    ) -> None:
        self.stopwords = {token.lower() for token in (stopwords or _DEFAULT_STOPWORDS)}
        self.metadata_boost = metadata_boost
        self.camel_case_boost = camel_case_boost
        self.enable_semantic_rerank = enable_semantic_rerank
        self.semantic_model_name = semantic_model_name
        self.metadata_only_penalty = metadata_only_penalty
        self._semantic_model = None

    @property
    def semantic_model(self) -> Any | None:
        if not self.enable_semantic_rerank:
            return None
        if self._semantic_model is not None:
            return self._semantic_model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:  # pragma: no cover - executed only when dependency missing
            self._semantic_model = None
            self.enable_semantic_rerank = False
            return None
        try:
            model = SentenceTransformer(self.semantic_model_name)
        except Exception:  # pragma: no cover - model load failures should not crash tests
            model = None
            self.enable_semantic_rerank = False
        self._semantic_model = model
        return model

    def extract(
        self,
        text: str,
        metadata: Optional[Mapping[str, Any]] = None,
        top_k: int = 8,
        min_score: float = 0.0,
    ) -> List[str]:
        clean_text = text.strip() if text else ""

        metadata_tokens = self._prepare_metadata(metadata)

        if not clean_text and not metadata_tokens:
            return []

        candidates = self._generate_candidates(clean_text, metadata_tokens)
        if not candidates:
            return []

        scored = self._score_candidates(candidates, metadata_tokens)
        reranked = self._maybe_semantic_rerank(clean_text, metadata_tokens, scored)

        unique_phrases: MutableMapping[str, KeywordCandidate] = {}
        for candidate in reranked:
            normalized = candidate.phrase.lower()
            if normalized in unique_phrases:
                stored = unique_phrases[normalized]
                if candidate.score > stored.score:
                    unique_phrases[normalized] = candidate
            else:
                unique_phrases[normalized] = candidate

        ordered = sorted(
            (cand for cand in unique_phrases.values() if cand.score >= min_score),
            key=lambda item: item.score,
            reverse=True,
        )
        return [candidate.phrase for candidate in ordered[: max(top_k, 0)]]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _prepare_metadata(self, metadata: Optional[Mapping[str, Any]]) -> List[str]:
        if not metadata:
            return []
        pieces: List[str] = []
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                joined = ", ".join(self._coerce_to_text(item) for item in value if item is not None)
                if joined:
                    pieces.append(f"{key}: {joined}")
                continue
            pieces.append(f"{key}: {self._coerce_to_text(value)}")
        return pieces

    def _coerce_to_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)):
            return f"{value}"
        return json.dumps(value, ensure_ascii=False)

    def _generate_candidates(
        self,
        text: str,
        metadata_tokens: Sequence[str],
    ) -> List[List[str]]:
        sentences = self._split_sentences(text, metadata_tokens)
        candidates: List[List[str]] = []

        for sentence in sentences:
            tokens = self._tokenize(sentence)
            if not tokens:
                continue
            current_phrase: List[str] = []
            for token in tokens:
                lower = token.lower()
                if lower in self.stopwords or len(lower) <= 1:
                    if current_phrase:
                        candidates.append(current_phrase)
                        current_phrase = []
                else:
                    current_phrase.append(token)
            if current_phrase:
                candidates.append(current_phrase)
        return candidates

    def _split_sentences(self, text: str, metadata_tokens: Sequence[str]) -> List[str]:
        material = text
        if metadata_tokens:
            material = "\n".join((*metadata_tokens, text))
        sentences = [segment.strip() for segment in _SENTENCE_SPLIT_REGEX.split(material) if segment.strip()]
        return sentences

    def _tokenize(self, text: str) -> List[str]:
        return _TOKEN_REGEX.findall(text)

    def _score_candidates(
        self,
        candidates: Sequence[Sequence[str]],
        metadata_tokens: Sequence[str],
    ) -> List[KeywordCandidate]:
        word_frequency: Counter[str] = Counter()
        word_degree: MutableMapping[str, int] = defaultdict(int)

        for candidate in candidates:
            unique_tokens = [token.lower() for token in candidate]
            length = len(unique_tokens)
            for token in unique_tokens:
                word_frequency[token] += 1
                word_degree[token] += length

        for token, freq in word_frequency.items():
            word_degree[token] += freq - 1

        keyword_candidates: List[KeywordCandidate] = []

        metadata_token_set = {
            token.lower()
            for sentence in metadata_tokens
            for token in self._tokenize(sentence)
        }

        for candidate in candidates:
            normalized_tokens = [token.lower() for token in candidate]
            if not normalized_tokens:
                continue
            score = 0.0
            for token in normalized_tokens:
                freq = word_frequency[token]
                degree = word_degree[token]
                if freq == 0:
                    continue
                score += degree / freq
            # Average to avoid bias toward very long phrases.
            score /= len(candidate)

            metadata_overlap = sum(1 for token in normalized_tokens if token in metadata_token_set)
            if metadata_overlap:
                score *= 1.0 + metadata_overlap * self.metadata_boost
                if metadata_overlap == len(candidate):
                    score *= self.metadata_only_penalty

            if any(self._looks_like_camel_case(token) for token in candidate):
                score *= 1.0 + self.camel_case_boost

            phrase = self._recompose_phrase(candidate)
            keyword_candidates.append(
                KeywordCandidate(
                    phrase=phrase,
                    score=score,
                    weight=float(len(candidate)),
                )
            )
        return keyword_candidates

    def _maybe_semantic_rerank(
        self,
        text: str,
        metadata_tokens: Sequence[str],
        candidates: Sequence[KeywordCandidate],
    ) -> List[KeywordCandidate]:
        model = self.semantic_model
        if model is None or not candidates:
            # No semantic rerank possible.
            return list(candidates)

        combined_text = "\n".join((*metadata_tokens, text)) if metadata_tokens else text
        try:
            document_embedding = model.encode(combined_text, normalize_embeddings=True)
            phrases = [candidate.phrase for candidate in candidates]
            candidate_embeddings = model.encode(phrases, normalize_embeddings=True)
        except Exception:  # pragma: no cover - defensive path when model fails
            return list(candidates)

        reranked: List[KeywordCandidate] = []
        for candidate, embedding in zip(candidates, candidate_embeddings):
            semantic_similarity = float(self._cosine_similarity(document_embedding, embedding))
            semantic_boost = max(semantic_similarity, 0.0)
            adjusted_score = candidate.score * (1.0 + semantic_boost)
            reranked.append(
                KeywordCandidate(
                    phrase=candidate.phrase,
                    score=adjusted_score,
                    weight=candidate.weight,
                )
            )
        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked

    def _cosine_similarity(self, left: Sequence[float], right: Sequence[float]) -> float:
        numerator = sum(x * y for x, y in zip(left, right))
        left_norm = math.sqrt(sum(x * x for x in left))
        right_norm = math.sqrt(sum(y * y for y in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _recompose_phrase(self, tokens: Sequence[str]) -> str:
        return " ".join(tokens)

    def _looks_like_camel_case(self, token: str) -> bool:
        # CamelCase or PascalCase often signal type or component names.
        if token.isupper() or token.islower():
            return False
        return bool(_CAMEL_CASE_REGEX.search(token))


def extract_keywords(
    text: str,
    metadata: Optional[Mapping[str, Any]] = None,
    top_k: int = 8,
    *,
    extractor: Optional[KeywordExtractor] = None,
) -> List[str]:
    """Convenience wrapper returning the top ``k`` keywords for a document."""

    selected_extractor = extractor or KeywordExtractor()
    safe_text = text or ""
    return selected_extractor.extract(text=safe_text, metadata=metadata, top_k=top_k)
