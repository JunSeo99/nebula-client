import math

import pytest

from tests.keyword_tooling.keyword_extractor import KeywordExtractor, extract_keywords


@pytest.fixture()
def extractor() -> KeywordExtractor:
    # Disable semantic reranking for deterministic tests.
    return KeywordExtractor(enable_semantic_rerank=False)


def test_extract_keywords_prioritizes_domain_terms(extractor: KeywordExtractor) -> None:
    text = (
        "This technical design elaborates the ingestion pipeline that collects "
        "events from Kafka topics and processes them with Spark streaming jobs. "
        "Operational constraints include exactly-once semantics and schema evolution"
    )
    metadata = {
        "file_type": "Architecture Design",
        "tags": ["kafka", "spark", "streaming"],
        "owner": "Data Platform Team",
    }

    keywords = extractor.extract(text=text, metadata=metadata, top_k=10)

    assert any("ingestion" in keyword.lower() for keyword in keywords)
    assert any("kafka" in keyword.lower() for keyword in keywords)
    assert any("spark" in keyword.lower() for keyword in keywords)
    assert len(keywords) <= 10


def test_metadata_phrases_surface_in_results(extractor: KeywordExtractor) -> None:
    text = (
        "The report summarises customer impact after the outage."
        " Root-cause analysis points to stale feature flags."
    )
    metadata = {
        "document_type": "Incident Report",
        "severity": "SEV-1",
        "services": ["Feature Flag Service"],
    }

    keywords = extractor.extract(text=text, metadata=metadata, top_k=6)

    assert any("incident report" in keyword.lower() for keyword in keywords)
    assert any("feature flag" in keyword.lower() for keyword in keywords)
    assert keywords[0] != ""


def test_extract_keywords_handles_korean_corpus(extractor: KeywordExtractor) -> None:
    text = (
        "이 문서는 결제 시스템 장애 분석과 복구 절차를 설명합니다. "
        "주요 원인은 데이터베이스 잠금 경합입니다."
    )
    metadata = {"문서종류": "장애 보고서"}

    keywords = extractor.extract(text=text, metadata=metadata, top_k=6)

    # Ensure key domain words survive extraction.
    collected = " ".join(keywords)
    assert "결제" in collected
    assert "장애" in collected
    assert "데이터베이스" in collected


def test_extract_keywords_empty_inputs() -> None:
    assert extract_keywords(text="", metadata=None) == []
    assert extract_keywords(text="", metadata={}) == []
    assert extract_keywords(text="   ", metadata=None) == []
