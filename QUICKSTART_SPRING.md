# Spring 연동 빠른 시작 가이드

## 5분 안에 시작하기

### 1단계: 의존성 설치 (1분)

```bash
# 프로젝트 디렉터리에서
cd /Users/jun/project/nebula/nebula-client

# 활성화된 가상환경 확인
source .venv/bin/activate

# 필요한 패키지 설치
pip install tenacity pydantic-settings
```

### 2단계: 환경 변수 설정 (1분)

```bash
# .env 파일 생성/수정
cat >> .env << EOF

# Spring 서버 연동
SPRING_SERVER_URL=http://localhost:8080
SPRING_API_KEY=your-api-key-here
EOF
```

### 3단계: 스키마 파일 생성 (1분)

**파일**: `app/schemas/organization.py`

복사 & 붙여넣기: [INTEGRATION_SPRING.md의 구현 예제](#3-fastapi-측-라우터-구현) 에서 `app/schemas/organization.py` 섹션을 참고하세요.

### 4단계: Spring 클라이언트 생성 (1분)

**파일**: `app/services/spring_integration.py`

복사 & 붙여넣기: [INTEGRATION_SPRING.md의 구현 예제](#2-fastapi-측-서비스-구현) 에서 `app/services/spring_integration.py` 섹션을 참고하세요.

### 5단계: 라우터 생성 (1분)

**파일**: `app/routers/organization.py`

복사 & 붙여넣기: [INTEGRATION_SPRING.md의 구현 예제](#3-fastapi-측-라우터-구현) 에서 `app/routers/organization.py` 섹션을 참고하세요.

### 6단계: main.py 업데이트 (1분)

```python
# app/main.py

from fastapi import FastAPI
from app.routers import organization  # 추가

app = FastAPI(title="Nebula Client API")

# 라우터 등록 (기존 라우터 아래에 추가)
app.include_router(organization.router)

# ... 기존 코드 ...
```

---

## 테스트하기

### Spring 서버 Mock으로 테스트

```python
# tests/test_spring_integration_quick.py

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from app.services.spring_integration import SpringClient
from app.schemas.organization import SnapshotBatchRequest, FileEntry


@pytest.mark.asyncio
async def test_send_batch_success():
    """배치 전송 성공 테스트"""

    # Spring 클라이언트 생성
    client = SpringClient(
        base_url="http://localhost:8080",
        api_key="test-key"
    )

    # Mock httpx.post
    with patch('httpx.AsyncClient.post') as mock_post:
        # Mock 응답 설정
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "taskId": "task_123",
            "batchNumber": 1,
            "totalBatches": 5,
            "status": "RECEIVED",
            "message": "배치가 수신되었습니다"
        }
        mock_post.return_value = mock_response

        # 배치 요청 생성
        batch_request = SnapshotBatchRequest(
            task_id="task_123",
            batch_number=1,
            total_batches=5,
            directory="/tmp/test",
            user_id="user_123",
            strategy="BALANCED",
            max_cost_budget=50.0,
            generated_at=datetime.now(timezone.utc),
            entries=[
                FileEntry(
                    relative_path="test.txt",
                    absolute_path="/tmp/test/test.txt",
                    is_directory=False,
                    size_bytes=100,
                    modified_at=datetime.now(timezone.utc),
                    keywords=["test"],
                    confidence=0.9
                )
            ]
        )

        # 테스트 실행
        response = await client.send_snapshot_batch(batch_request)

        # 검증
        assert response.status == "RECEIVED"
        assert response.batch_number == 1


# 테스트 실행
# pytest tests/test_spring_integration_quick.py -v
```

### 엔드포인트 테스트

```bash
# FastAPI 서버 실행
uvicorn app.main:app --reload

# 다른 터미널에서 테스트
```

```bash
# 1. 파일 정리 시작
curl -X POST "http://127.0.0.1:8000/api/organize" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/jun/Documents/TestFolder",
    "strategy": "BALANCED",
    "max_cost_budget": 50.0
  }' \
  | jq .

# 응답:
# {
#   "taskId": "...",
#   "status": "PROCESSING",
#   "message": "파일 정리가 시작되었습니다",
#   "totalFiles": 50,
#   "totalBatches": 1
# }

# 2. 작업 상태 조회
curl "http://127.0.0.1:8000/api/organize/{taskId}" \
  | jq .

# 3. 결과 조회 (Spring에서 제공)
# Spring 서버에서 응답이 올 때까지 대기...
```

---

## 에러 처리

### 문제 1: "Spring 서버에 연결할 수 없습니다"

```
원인: Spring 서버가 실행 중이지 않음

해결:
1. Spring 서버가 localhost:8080에서 실행 중인지 확인
   curl http://localhost:8080/health

2. SPRING_SERVER_URL 환경 변수 확인
   echo $SPRING_SERVER_URL

3. 방화벽 설정 확인
```

### 문제 2: "유효하지 않은 API 키입니다"

```
원인: SPRING_API_KEY가 잘못됨

해결:
1. Spring 서버에서 API 키 발급받기
2. .env 파일에 정확히 입력
3. 앱 재시작
   # FastAPI 서버 재실행
```

### 문제 3: "경로가 존재하지 않습니다"

```
원인: 정리할 폴더 경로가 잘못됨

해결:
1. 절대 경로 사용 확인 (~/path는 불가)
   /Users/jun/Documents/MyFolder (O)
   ~/Documents/MyFolder (X)

2. 폴더 권한 확인
   ls -ld /path/to/folder
```

---

## 다음 단계

### 1단계: 배치 처리 최적화
```python
# app/services/ml_extraction.py 생성

from concurrent.futures import ThreadPoolExecutor
import asyncio

async def extract_files_parallel(files):
    """파일을 병렬로 처리"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = [
            loop.run_in_executor(executor, extract_single_file, f)
            for f in files
        ]
        return await asyncio.gather(*tasks)
```

### 2단계: 비용 관리 추가
```python
# app/services/cost_manager.py 생성

class CostManager:
    """OpenAI API 비용 관리"""

    COSTS = {
        "gpt-4": {"input": 0.03/1000, "output": 0.06/1000},
        "gpt-3.5-turbo": {"input": 0.001/1000, "output": 0.002/1000}
    }

    def estimate_cost(self, model, tokens):
        return tokens * self.COSTS[model]["input"]
```

### 3단계: 진행 상황 추적
```python
# app/services/task_tracker.py 생성

from redis import Redis

class TaskTracker:
    """Redis를 사용한 작업 추적"""

    def __init__(self):
        self.redis = Redis(host='localhost', port=6379)

    def set_progress(self, task_id, progress):
        self.redis.set(f"task:{task_id}:progress", progress)

    def get_progress(self, task_id):
        return self.redis.get(f"task:{task_id}:progress")
```

---

## 전체 흐름 (Spring 서버와 통신)

```
1. 클라이언트 요청
   POST /api/organize
   {
     "path": "/Users/jun/Documents",
     "strategy": "BALANCED"
   }

2. FastAPI 처리
   ├─ 경로 검증
   ├─ 파일 수집 (50개 단위)
   ├─ ML 추출 (PDF, 이미지 등)
   └─ 배치 생성

3. Spring 전송
   POST /api/snapshots/batch (50개 파일씩)
   {
     "taskId": "...",
     "batchNumber": 1,
     "totalBatches": 10,
     "entries": [...]
   }

4. Spring 처리
   ├─ 메타데이터 저장
   ├─ 모든 배치 수집
   └─ OpenAI 호출

5. 결과 반환
   GET /api/organize/{taskId}
   {
     "status": "COMPLETED",
     "result": {
       "organization": {...},
       "confidence": 0.92
     }
   }

6. 재정리 실행
   POST /api/reorganize/execute
   ├─ 폴더 생성
   ├─ 파일 이동
   └─ 완료 보고
```

---

## 디버깅 팁

### 로그 확인
```bash
# FastAPI 로그에서 Spring 통신 내역 확인
tail -f app.log | grep "Spring"

# 배치 전송 로그
tail -f app.log | grep "배치.*전송"
```

### Mock 데이터로 테스트
```python
# tests/mock_spring_server.py

from fastapi import FastAPI
from fastapi.responses import JSONResponse

mock_app = FastAPI()

@mock_app.post("/api/snapshots/batch")
async def mock_batch(request: dict):
    return JSONResponse({
        "taskId": request.get("taskId"),
        "batchNumber": request.get("batchNumber"),
        "status": "RECEIVED"
    })

# 테스트 실행
# uvicorn tests.mock_spring_server:mock_app --port 9000
```

그 후 `.env`에서:
```
SPRING_SERVER_URL=http://localhost:9000
```

---

## 성능 확인

```python
# tests/performance_test.py

import time
from datetime import datetime

async def test_performance():
    """1000개 파일 처리 성능 테스트"""

    start = time.time()

    # 1000개 파일 처리
    files = [create_mock_file() for _ in range(1000)]
    batches = chunk_files(files, 50)

    for batch in batches:
        await client.send_snapshot_batch(batch)

    duration = time.time() - start

    print(f"총 시간: {duration:.2f}초")
    print(f"배치당 시간: {duration/len(batches):.2f}초")
    print(f"파일당 시간: {duration/1000*1000:.0f}ms")

    # 예상 결과:
    # 총 시간: 25.34초
    # 배치당 시간: 1.27초
    # 파일당 시간: 25ms
```

---

## 다음 읽을 문서

1. **[INTEGRATION_SPRING.md](./INTEGRATION_SPRING.md)** - 상세 API 명세
2. **[IMPLEMENTATION_CHECKLIST.md](./IMPLEMENTATION_CHECKLIST.md)** - 구현 체크리스트
3. **[AGENTS.md](./AGENTS.md)** - 프로젝트 가이드라인

---

## 도움말

```bash
# FastAPI 문서 확인
open http://127.0.0.1:8000/docs

# 필요한 로그 활성화
export LOGGING_LEVEL=DEBUG
uvicorn app.main:app --reload --log-level debug
```

---

**작성자**: Claude Code
**최종 수정**: 2025-11-11
**소요 시간**: ~5분 (최소 설정)
