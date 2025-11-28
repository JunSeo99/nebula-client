# 정리된 파일 API 구현 가이드

## 개요

이 문서는 FastAPI 프로젝트에서 로컬 파일을 검사하고, ML 기반 키워드를 추출한 후, Spring 서버의 **Organized Files API**로 전달하는 기능을 설명합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI (Local Client)                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │ POST /api/folders/inspect-and-organize           │   │
│  │ - 폴더 검사                                       │   │
│  │ - 파일 수집                                       │   │
│  │ - ML 키워드 추출 (PDF, 이미지, 스프레드시트)     │   │
│  │ - OrganizedFileEntry로 변환                      │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────┬─────────────────────────────────────────┘
                 │ (HTTP POST)
                 │ JSON: {
                 │   userId, baseDirectory, files[]
                 │   - originalRelativePath
                 │   - keywords[]
                 │   - paraBucket (Projects/Areas/Resources/Archive)
                 │   - ...
                 │ }
                 ▼
┌──────────────────────────────────────────────────────────┐
│  Spring Server                                            │
│  /api/organized-files/save                               │
│  ├─ 메타데이터 DB 저장                                  │
│  ├─ 중복 검사 및 업데이트 처리                          │
│  └─ 통계 정보 반환                                       │
└──────────────────────────────────────────────────────────┘
```

---

## 새로 생성된 파일들

### 1. **Schemas** (데이터 모델)

#### `app/schemas/organized_file.py`
- `ParaBucket`: PARA 버킷 Enum (Projects, Areas, Resources, Archive)
- `OrganizedFileEntry`: Spring으로 전송할 파일 정보
- `OrganizedFileSaveRequest`: 요청 모델
- `OrganizedFileSaveResponse`: 응답 모델

**사용:**
```python
from app.schemas.organized_file import OrganizedFileEntry, ParaBucket

entry = OrganizedFileEntry(
    original_relative_path="src/main.py",
    directory=False,
    development=True,
    size_bytes=1024,
    modified_at=datetime.now(timezone.utc),
    keywords=["Python", "Main"],
    korean_file_name="메인 파일.py",
    english_file_name="main.py",
    para_bucket=ParaBucket.PROJECTS,
    reason="Main project file"
)
```

---

### 2. **Services** (비즈니스 로직)

#### `app/services/folder_inspection.py` (업데이트)
새로 추가된 함수들:

- **`_get_file_type(path: Path) -> Optional[str]`**
  - 파일 타입 판정 (pdf, image, xlsx, markdown 등)

- **`_is_development_file(path: Path) -> bool`**
  - 개발 관련 파일 여부 판정

- **`async _extract_file_keywords(file_path: Path) -> List[str]`**
  - 파일에서 ML 기반 키워드 추출
  - PDF: extract_pdf_keywords()
  - 이미지: extract_image_highlights()
  - 스프레드시트: build_summary_text()
  - 텍스트: 제목/첫 줄 추출

- **`async inspect_directory_with_keywords(raw_path: str)`**
  - 폴더 검사 + 키워드 추출
  - **반환**: (FolderContentsResponse, List[DirectoryEntry with keywords])

- **`to_organized_file_entry(...) -> OrganizedFileEntry`**
  - DirectoryEntry를 Spring 전송용 OrganizedFileEntry로 변환
  - 자동 PARA 버킷 분류
  - 한글/영문 파일명 생성

**사용 예:**
```python
from app.services.folder_inspection import (
    inspect_directory_with_keywords,
    to_organized_file_entry,
)

# 키워드 포함 폴더 검사
response, entries = await inspect_directory_with_keywords("/path/to/folder")

# DirectoryEntry → OrganizedFileEntry 변환
for entry in entries:
    organized = to_organized_file_entry(
        directory_root=Path("/path/to/folder"),
        entry=entry,
        user_id="user_id"
    )
```

---

#### `app/services/organized_file_client.py` (새로 생성)
Spring 서버 클라이언트

**클래스: `OrganizedFileClient`**

메서드:
- **`async save_files(user_id, base_directory, files) -> OrganizedFileSaveResponse`**
  - 파일 저장/업데이트
  - 재시도 로직 포함 (최대 3회)
  - timeout: 30초 (설정 가능)

- **`async get_user_stats(user_id) -> dict`**
  - 사용자의 파일 통계 조회

- **`async get_files_by_bucket(user_id, bucket) -> List[dict]`**
  - PARA 버킷별 파일 조회

**사용 예:**
```python
from app.services.organized_file_client import OrganizedFileClient

client = OrganizedFileClient(base_url="http://localhost:8080")

response = await client.save_files(
    user_id="user_123",
    base_directory="/path/to/project",
    files=[organized_entry1, organized_entry2]
)

print(f"저장: {response.saved_count}, 업데이트: {response.updated_count}")
```

---

### 3. **Routers** (API 엔드포인트)

#### `app/routers/organized_files.py` (새로 생성)

**엔드포인트 1: 단일 폴더 검사 및 정리**
```
POST /api/folders/inspect-and-organize

Request:
{
    "path": "/Users/jun/Documents/MyFolder"
}

Response (200):
{
    "status": "success",
    "message": "파일이 Spring 서버로 전달되었습니다",
    "directory": "/Users/jun/Documents/MyFolder",
    "totalFiles": 10,
    "savedCount": 8,
    "updatedCount": 2,
    "failedCount": 0,
    "errorMessages": []
}
```

**흐름:**
1. 폴더 경로 검증
2. 파일 수집 + ML 키워드 추출
3. OrganizedFileEntry로 변환
4. Spring 서버로 전송
5. 결과 반환

---

**엔드포인트 2: 배치 처리 (대용량 폴더용)**
```
POST /api/folders/inspect-and-organize/batch

Request:
{
    "path": "/Users/jun/Documents/LargeFolder"
}

Response (202 Accepted):
{
    "status": "processing",
    "message": "배치 처리가 시작되었습니다",
    "directory": "/Users/jun/Documents/LargeFolder",
    "totalFiles": 500,
    "totalBatches": 10,
    "batchSize": 50
}
```

**특징:**
- 50개 파일씩 배치 생성
- 백그라운드에서 순차적 처리
- 즉시 응답 (202 Accepted)
- 개별 배치 실패해도 다음 배치 계속 처리

---

## 키워드 추출 프로세스

### 지원하는 파일 형식

| 형식 | 추출 방법 | 예시 |
|------|----------|------|
| `.pdf` | PDF 텍스트 추출 | "Introduction", "Chapter 1", "Summary" |
| `.png/.jpg` | 이미지 OCR | "Text in image", "한글 텍스트" |
| `.xlsx/.csv` | 스프레드시트 요약 | "Sales Data Q1 2024" |
| `.md` | 제목 추출 | "# Main Title" |
| `.txt` | 첫 줄 추출 | "Documentation for..." |
| `.py` | (미래 확장) | - |

### 키워드 추출 로직

```python
async def _extract_file_keywords(file_path: Path) -> List[str]:
    # 1. 파일 타입 판정
    file_type = _get_file_type(file_path)

    # 2. 타입별 추출
    if file_type == "pdf":
        keywords = extract_pdf_keywords(str(file_path))
    elif file_type == "image":
        highlights = extract_image_highlights(str(file_path))
        keywords = highlights.ocr_lines
    # ...

    # 3. 상위 5개만 반환
    return keywords[:5]
```

**에러 처리:**
- 각 파일별 추출 실패는 로깅만 하고 계속 진행
- 키워드 없음도 정상 처리

---

## 자동 PARA 분류

파일을 자동으로 PARA 버킷에 분류합니다:

```python
if entry.is_development:
    # 개발 관련 파일
    para_bucket = ParaBucket.PROJECTS
elif entry.keywords:
    # 키워드 있는 파일 (리소스)
    para_bucket = ParaBucket.RESOURCES
else:
    # 키워드 없는 파일 (보관)
    para_bucket = ParaBucket.ARCHIVE
```

**규칙:**
1. **Projects**: 개발 파일 (`.git`, `package.json`, 등)
2. **Resources**: 키워드가 추출된 파일
3. **Archive**: 키워드 없는 파일

---

## 환경 변수 설정

### `.env.example` (업데이트됨)

```bash
# 기존 설정
SERVER_URL=http://ec2-13-236-181-95.ap-southeast-2.compute.amazonaws.com:8080
LOCAL_ROOT=/absolute/path/to/project
CLIENT_PATH=/Users/jun/project/nebula-frontend

# 새로 추가 (Spring 서버 연동)
SPRING_SERVER_URL=${SERVER_URL}  # 또는 별도의 URL
SPRING_API_KEY=your-api-key-here
```

### `.env` (로컬 설정)

```bash
# 실제 값 입력
SPRING_SERVER_URL=http://localhost:8080
SPRING_API_KEY=secure-api-key-123
```

---

## 사용 예제

### 1. FastAPI 서버 시작

```bash
cd /Users/jun/project/nebula/nebula-client

# 가상환경 활성화
source .venv/bin/activate

# 서버 시작
uvicorn app.main:app --reload
```

### 2. cURL로 테스트

```bash
# 폴더 검사 및 정리
curl -X POST "http://127.0.0.1:8000/api/folders/inspect-and-organize" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/jun/Documents/TestFolder"
  }' | jq .

# 응답:
# {
#   "status": "success",
#   "message": "파일이 Spring 서버로 전달되었습니다",
#   "directory": "/Users/jun/Documents/TestFolder",
#   "totalFiles": 5,
#   "savedCount": 4,
#   "updatedCount": 1,
#   "failedCount": 0
# }
```

### 3. Python 코드에서 사용

```python
import asyncio
from pathlib import Path
from app.services.folder_inspection import inspect_directory_with_keywords, to_organized_file_entry
from app.services.organized_file_client import OrganizedFileClient

async def organize_files():
    # 1. 폴더 검사 + 키워드 추출
    response, entries = await inspect_directory_with_keywords(
        "/Users/jun/Documents/MyFolder"
    )

    print(f"수집된 파일: {len(entries)}개")

    # 2. OrganizedFileEntry로 변환
    directory_root = Path("/Users/jun/Documents/MyFolder")
    organized_entries = [
        to_organized_file_entry(directory_root, entry, "user_123")
        for entry in entries
    ]

    # 3. Spring 서버로 전송
    client = OrganizedFileClient()
    result = await client.save_files(
        user_id="user_123",
        base_directory=str(directory_root),
        files=organized_entries
    )

    print(f"저장됨: {result.saved_count}")
    print(f"업데이트: {result.updated_count}")
    print(f"실패: {result.failed_count}")

# 실행
asyncio.run(organize_files())
```

---

## 테스트

### 단위 테스트 실행

```bash
# 모든 테스트 실행
pytest tests/test_organized_files.py -v

# 특정 테스트만 실행
pytest tests/test_organized_files.py::TestOrganizedFileClient::test_save_files_success -v

# 커버리지 확인
pytest tests/test_organized_files.py --cov=app.services.organized_file_client
```

### 테스트 파일: `tests/test_organized_files.py`

포함 내용:
- OrganizedFileEntry 스키마 검증
- DirectoryEntry → OrganizedFileEntry 변환 테스트
- Spring 클라이언트 테스트 (성공, 타임아웃, 통계 조회)

---

## 에러 처리

### 일반적인 에러

#### 1. Spring 서버 연결 실패
```
OrganizedFileClientError: Spring 서버 연결 실패: ...
```
**해결:**
- Spring 서버가 실행 중인지 확인
- `SPRING_SERVER_URL` 확인
- 방화벽 설정 확인

#### 2. 폴더 경로 존재하지 않음
```
DirectoryInspectionError: 해당 경로가 존재하지 않습니다.
```
**해결:**
- 절대 경로 사용 확인
- 경로 존재 여부 확인

#### 3. 권한 문제
```
DirectoryInspectionError: 디렉터리에 접근 권한이 없습니다.
```
**해결:**
- 파일/폴더 권한 확인
- `chmod` 명령으로 권한 변경

---

## 성능 고려사항

### 배치 처리 권장

- **소규모 (< 100 파일)**: `/api/folders/inspect-and-organize` 사용
- **중규모 (100-500 파일)**: `/api/folders/inspect-and-organize/batch` 사용
- **대규모 (> 500 파일)**: 배치 API 권장 + Redis 캐싱

### 처리 시간 예상

| 파일 수 | 처리 시간 | 키워드 추출 |
|--------|----------|-----------|
| 10 | 1초 | 빠름 |
| 100 | 10초 | 중간 |
| 1000 | 100초 | 느림 (OCR 포함 시) |

**최적화:**
- OCR 비활성화 옵션 추가 가능
- 병렬 처리 구현 가능 (Celery)

---

## 다음 단계

### Phase 2 (추천)

1. **사용자 ID 관리**
   - 현재는 하드코딩된 ID 사용
   - 실제 인증 시스템 연동 필요

2. **PARA 분류 개선**
   - 현재는 간단한 규칙 기반
   - OpenAI API로 지능형 분류 가능 (INTEGRATION_SPRING.md 참고)

3. **캐싱 추가**
   - Redis를 사용한 추출된 키워드 캐싱

4. **비동기 작업 큐**
   - Celery를 사용한 백그라운드 처리

---

## 참고 자료

- **Spring API 명세**: `/app/organized-files-api.md`
- **Spring 연동 가이드**: `INTEGRATION_SPRING.md`
- **구현 체크리스트**: `IMPLEMENTATION_CHECKLIST.md`
- **FastAPI 문서**: http://127.0.0.1:8000/docs (서버 실행 후)

---

**작성자**: Claude Code
**최종 수정**: 2025-11-18
**버전**: 1.0
