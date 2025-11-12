"""간단한 키워드 추출 테스트 - 서버 없이"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from app.services.folder_snapshot import snapshot_directory
import json

def test_keywords_in_folder(folder_path: str):
    """폴더의 파일들에서 키워드 추출 테스트"""
    print(f"테스트 폴더: {folder_path}\n")
    print("=" * 60)
    
    try:
        # 스냅샷 생성
        result = snapshot_directory(folder_path)
        
        print(f"✅ 스냅샷 생성 완료!")
        print(f"   - 총 항목: {result.total_entries}개")
        print(f"   - 페이지 수: {result.page_count}")
        
        # 키워드가 추출된 파일들 확인
        if result.pages:
            print("\n" + "=" * 60)
            print("📋 키워드 추출 결과:")
            print("=" * 60)
            
            total_with_keywords = 0
            for page in result.pages:
                with open(page.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                entries_with_keywords = [
                    entry for entry in data["entries"]
                    if "keywords" in entry and entry["keywords"]
                ]
                
                total_with_keywords += len(entries_with_keywords)
                
                for entry in entries_with_keywords:
                    file_type = "📄" if not entry.get("isDirectory", False) else "📁"
                    print(f"\n{file_type} {entry['relativePath']}")
                    keywords = entry["keywords"]
                    if isinstance(keywords, list):
                        print(f"   키워드 ({len(keywords)}개): {', '.join(keywords[:10])}")
                        if len(keywords) > 10:
                            print(f"   ... 외 {len(keywords) - 10}개")
                    else:
                        print(f"   키워드: {keywords}")
            
            print("\n" + "=" * 60)
            print(f"✅ 키워드가 추출된 파일: {total_with_keywords}개")
            print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python test_simple.py <폴더경로>")
        print("\n예시:")
        print("  python test_simple.py .")
        print("  python test_simple.py C:\\Users\\dong6\\Documents")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    test_keywords_in_folder(folder_path)

