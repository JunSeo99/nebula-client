"""키워드 추출 기능을 직접 테스트하는 스크립트"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from app.services.keyword_extraction import keybert_analyze
from app.services.folder_snapshot import snapshot_directory


def test_keybert_basic():
    """KeyBERT 기본 기능 테스트"""
    print("=" * 50)
    print("KeyBERT 기본 테스트")
    print("=" * 50)
    
    sample_text = """
    FastAPI는 현대적인 Python 웹 프레임워크입니다. 
    높은 성능과 자동 API 문서 생성 기능을 제공합니다.
    Pydantic을 사용하여 데이터 검증을 수행합니다.
    비동기 프로그래밍을 지원하여 빠른 응답 속도를 보장합니다.
    """
    
    try:
        keywords, key_sents = keybert_analyze(sample_text, top_n_keywords=5)
        print(f"\n추출된 키워드 ({len(keywords)}개):")
        for kw, score in keywords:
            print(f"  - {kw} (점수: {score:.3f})")
        
        print(f"\n핵심 문장 후보 ({len(key_sents)}개):")
        for sent, score in key_sents[:3]:  # 상위 3개만
            print(f"  - {sent[:80]}... (점수: {score:.3f})")
        
        print("\n✅ KeyBERT 테스트 성공!")
        return True
    except Exception as e:
        print(f"\n❌ KeyBERT 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_snapshot_with_keywords(test_dir: str):
    """실제 디렉토리로 스냅샷 테스트"""
    print("\n" + "=" * 50)
    print("스냅샷 키워드 추출 테스트")
    print("=" * 50)
    
    try:
        result = snapshot_directory(test_dir)
        print(f"\n스냅샷 생성 완료:")
        print(f"  - 디렉토리: {result.directory}")
        print(f"  - 총 항목: {result.total_entries}개")
        print(f"  - 페이지 수: {result.page_count}")
        
        # 첫 번째 페이지의 키워드 확인
        if result.pages:
            import json
            snapshot_path = result.pages[0].path
            with open(snapshot_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            entries_with_keywords = [
                entry for entry in data["entries"]
                if "keywords" in entry and entry["keywords"]
            ]
            
            print(f"\n키워드가 추출된 파일: {len(entries_with_keywords)}개")
            for entry in entries_with_keywords[:5]:  # 최대 5개만 표시
                print(f"\n  📄 {entry['relativePath']}")
                print(f"     키워드: {entry['keywords']}")
        
        print("\n✅ 스냅샷 테스트 성공!")
        return True
    except Exception as e:
        print(f"\n❌ 스냅샷 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("키워드 추출 기능 테스트 시작\n")
    
    # 1. KeyBERT 기본 테스트
    keybert_ok = test_keybert_basic()
    
    # 2. 실제 디렉토리 테스트 (선택사항)
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
        print(f"\n테스트 디렉토리: {test_dir}")
        snapshot_ok = test_snapshot_with_keywords(test_dir)
    else:
        print("\n💡 실제 디렉토리로 테스트하려면:")
        print("   python test_keywords.py <디렉토리경로>")
        snapshot_ok = None
    
    print("\n" + "=" * 50)
    if keybert_ok:
        print("✅ 모든 테스트 통과!")
    else:
        print("❌ 일부 테스트 실패")
    print("=" * 50)

