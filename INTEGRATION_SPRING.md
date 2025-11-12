# Spring 서버 연동 가이드

## 목차
1. [개요](#개요)
2. [시스템 아키텍처](#시스템-아키텍처)
3. [데이터 흐름](#데이터-흐름)
4. [FastAPI → Spring API 명세](#fastapi--spring-api-명세)
5. [구현 예제](#구현-예제)
6. [메시지 큐 통합](#메시지-큐-통합)
7. [에러 처리](#에러-처리)
8. [배포 및 운영](#배포-및-운영)

---

## 개요

Nebula Client의 FastAPI 서버는 **로컬 파일 수집 및 ML 기반 메타데이터 추출**을 담당하고,
**Spring 메타데이터 서버**에 이를 전달하여 중앙 집중식으로 관리합니다.

### 역할 분담
```
┌─────────────────────────────────────────────────────────┐
│  FastAPI (Local Client)                                  │
│  ├─ 파일 시스템 접근                                      │
│  ├─ 로컬 ML 추출 (PDF, 이미지, 스프레드시트)              │
│  └─ 메타데이터 수집 (배치 단위)                           │
└────────────┬────────────────────────────────────────────┘
             │ (메타데이터 + 키워드)
             ▼
┌──────────────────────────────────────────────────────────┐
│  Spring Metadata Server (Central)                         │
│  ├─ 메타데이터 DB 저장                                    │
│  ├─ 배치 조율 및 상태 관리                                │
│  ├─ OpenAI API 호출 조정                                  │
│  └─ 최종 폴더 구조 결정                                   │
└──────────────────────────────────────────────────────────┘
             │ (재정리 명령)
             ▼
┌──────────────────────────────────────────────────────────┐
│  FastAPI (재정리 실행)                                    │
│  ├─ 폴더 생성                                             │
│  ├─ 파일 이동 (또는 심링크)                               │
│  └─ 완료 보고                                             │
└──────────────────────────────────────────────────────────┘
```

---

## 시스템 아키텍처

### FastAPI 에서 Spring 으로 전달하는 데이터 구조

```
사용자 폴더 선택
    ↓
파일 수집 (배치 50개)
    ↓
ML 추출 (병렬 처리)
    ├─ PDF: extract_pdf_keywords()
    ├─ 이미지: extract_image_highlights()
    └─ 스프레드시트: build_summary_text()
    ↓
메타데이터 + 키워드 생성
    ↓
Spring 서버로 전송
    ├─ Method: POST /api/snapshots/batch
    ├─ Payload: {directory, files[], keywords[], ...}
    └─ Response: {taskId, batchNumber, ...}
    ↓
Spring이 OpenAI 호출
    ├─ 배치 1-N: 초안 생성
    └─ 재귀: 점진적 개선
    ↓
파일 재정리 결과 반환
```

---

## 데이터 흐름

### 1. 클라이언트 요청 (Next.js → FastAPI)

```
POST /folders/organize
Content-Type: application/json

{
  "path": "/Users/jun/Documents/MyProject",
  "strategy": "BALANCED",
  "max_cost_budget": 50.0
}
```

### 2. FastAPI 백그라운드 처리

```
1. 경로 검증
2. 파일 수집 (재귀적)
3. 50개 단위로 배치 생성
4. 각 파일에 대해:
   - 메타데이터 추출 (크기, 수정일, 타입)
   - ML 기반 키워드 추출
5. Spring 서버로 배치 전송 (HTTP POST)
```

### 3. Spring 처리

```
1. 메타데이터 DB 저장
2. 배치 번호 추적
3. 모든 배치 수집 완료 시:
   - OpenAI API 호출 (배치 1)
   - 초안 생성
4. 재귀적 개선 (최대 3회)
5. 최종 폴더 구조 결정
6. FastAPI로 재정리 명령 전송
```

### 4. FastAPI 재정리 실행

```
1. 전달받은 구조 대로 폴더 생성
2. 파일 이동 (또는 심링크)
3. 완료 보고
```

---

## FastAPI → Spring API 명세

### 1. 배치 전송 API

**엔드포인트**: `POST /api/snapshots/batch`

**요청 헤더**:
```
Content-Type: application/json
X-User-ID: {user_id}
X-API-Key: {api_key}
```

**요청 본문**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "batchNumber": 1,
  "totalBatches": 10,
  "directory": "/Users/jun/Documents/MyProject",
  "userId": "user_621c7d3957c2ea5b9063d04c",
  "strategy": "BALANCED",
  "maxCostBudget": 50.0,
  "generatedAt": "2025-11-11T10:30:00Z",
  "entries": [
    {
      "relativePath": "README.md",
      "absolutePath": "/Users/jun/Documents/MyProject/README.md",
      "isDirectory": false,
      "sizeBytes": 2048,
      "modifiedAt": "2025-11-10T15:20:00Z",
      "isDevelopment": false,
      "fileType": "markdown",
      "keywords": ["파일 정리", "문서", "가이드"],
      "caption": "프로젝트 설명서",
      "confidence": 0.95
    },
    {
      "relativePath": "src/main.py",
      "absolutePath": "/Users/jun/Documents/MyProject/src/main.py",
      "isDirectory": false,
      "sizeBytes": 5120,
      "modifiedAt": "2025-11-11T09:00:00Z",
      "isDevelopment": true,
      "fileType": "python",
      "keywords": ["FastAPI", "메인 진입점", "라우터"],
      "caption": null,
      "confidence": 0.87
    },
    {
      "relativePath": "docs/architecture.pdf",
      "absolutePath": "/Users/jun/Documents/MyProject/docs/architecture.pdf",
      "isDirectory": false,
      "sizeBytes": 1024000,
      "modifiedAt": "2025-11-05T14:30:00Z",
      "isDevelopment": false,
      "fileType": "pdf",
      "keywords": ["아키텍처", "시스템 설계", "마이크로서비스"],
      "caption": "시스템 아키텍처 문서",
      "confidence": 0.92
    }
  ]
}
```

**응답 (200 OK)**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "batchNumber": 1,
  "totalBatches": 10,
  "status": "RECEIVED",
  "message": "배치가 수신되어 처리 중입니다",
  "receivedAt": "2025-11-11T10:30:05Z",
  "nextBatchExpectedAt": "2025-11-11T10:30:30Z"
}
```

**응답 (400 Bad Request)**:
```json
{
  "error": "INVALID_REQUEST",
  "message": "entries 필드는 필수입니다",
  "timestamp": "2025-11-11T10:30:05Z"
}
```

**응답 (401 Unauthorized)**:
```json
{
  "error": "UNAUTHORIZED",
  "message": "유효하지 않은 API 키입니다",
  "timestamp": "2025-11-11T10:30:05Z"
}
```

**응답 (429 Too Many Requests)**:
```json
{
  "error": "RATE_LIMITED",
  "message": "API 요청 제한을 초과했습니다. 60초 후 재시도하세요",
  "retryAfter": 60,
  "timestamp": "2025-11-11T10:30:05Z"
}
```

---

### 2. 작업 상태 조회 API

**엔드포인트**: `GET /api/snapshots/tasks/{taskId}`

**요청 헤더**:
```
X-User-ID: {user_id}
X-API-Key: {api_key}
```

**응답 (200 OK)**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "status": "PROCESSING",
  "directory": "/Users/jun/Documents/MyProject",
  "totalFiles": 500,
  "processedBatches": 5,
  "totalBatches": 10,
  "progress": {
    "percentage": 50,
    "filesProcessed": 250,
    "estimatedTimeRemaining": 300
  },
  "batches": [
    {
      "batchNumber": 1,
      "status": "COMPLETED",
      "filesCount": 50,
      "receivedAt": "2025-11-11T10:30:05Z",
      "processedAt": "2025-11-11T10:30:30Z"
    }
  ],
  "aiProcessing": {
    "status": "PENDING",
    "iteration": 0,
    "maxIterations": 2,
    "confidence": 0
  }
}
```

---

### 3. 재정리 결과 조회 API

**엔드포인트**: `GET /api/snapshots/tasks/{taskId}/result`

**응답 (200 OK - 처리 중)**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "status": "AI_PROCESSING",
  "message": "AI가 폴더 구조를 재정리 중입니다 (2/3 반복)",
  "progress": 65
}
```

**응답 (200 OK - 완료)**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "status": "COMPLETED",
  "result": {
    "organization": {
      "Projects": [
        {
          "folderName": "2025-Q1-WebApp",
          "files": [
            "src/main.py",
            "src/utils.py",
            "requirements.txt"
          ],
          "reasoning": "현재 진행 중인 웹 애플리케이션 개발 프로젝트"
        }
      ],
      "Areas": [
        {
          "folderName": "Documentation",
          "files": [
            "docs/architecture.pdf",
            "docs/api-spec.md"
          ],
          "reasoning": "지속적으로 관리하는 문서 영역"
        }
      ],
      "Resources": [
        {
          "folderName": "References",
          "files": [
            "tutorial.pdf",
            "best-practices.md"
          ],
          "reasoning": "참고 자료 및 학습 리소스"
        }
      ],
      "Archives": [
        {
          "folderName": "2024-Completed",
          "files": [
            "old-project-backup.zip"
          ],
          "reasoning": "완료된 과거 프로젝트"
        }
      ]
    },
    "statistics": {
      "totalFiles": 500,
      "totalFolders": 4,
      "organizationConfidence": 0.92,
      "improvements": [
        "개발 파일과 문서를 명확히 분리",
        "중복된 리소스 통합",
        "오래된 파일 보관처리"
      ]
    },
    "executionDetails": {
      "aiIterations": 2,
      "estimatedTokenUsage": 4500,
      "estimatedCost": 3.50,
      "processingTimeSeconds": 125
    }
  },
  "readyToExecute": true,
  "message": "재정리 계획이 준비되었습니다. 실행하시겠습니까?"
}
```

---

### 4. 재정리 실행 명령 (Spring → FastAPI 콜백)

**엔드포인트**: `POST /api/reorganize/execute`

**요청 헤더**:
```
Content-Type: application/json
X-Spring-Server: true
X-API-Key: {api_key}
```

**요청 본문**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "sourceDirectory": "/Users/jun/Documents/MyProject",
  "targetBaseDirectory": "/Users/jun/Documents/MyProject-Organized",
  "fileOperations": [
    {
      "sourceAbsolutePath": "/Users/jun/Documents/MyProject/src/main.py",
      "targetRelativePath": "Projects/2025-Q1-WebApp/src/main.py",
      "operation": "MOVE",
      "createSymlink": false
    },
    {
      "sourceAbsolutePath": "/Users/jun/Documents/MyProject/docs/architecture.pdf",
      "targetRelativePath": "Areas/Documentation/docs/architecture.pdf",
      "operation": "MOVE",
      "createSymlink": true
    }
  ],
  "folderStructure": {
    "Projects": [],
    "Areas": [],
    "Resources": [],
    "Archives": []
  }
}
```

**응답 (200 OK)**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "status": "EXECUTING",
  "message": "재정리를 시작했습니다",
  "executionStartedAt": "2025-11-11T10:35:00Z"
}
```

---

### 5. 재정리 완료 보고 (FastAPI → Spring)

**엔드포인트**: `POST /api/snapshots/tasks/{taskId}/execution-result`

**요청 본문**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "status": "SUCCESS",
  "executionSummary": {
    "totalOperations": 50,
    "succeededOperations": 48,
    "failedOperations": 2,
    "duration": 125,
    "newFolderStructure": {
      "Projects": {
        "2025-Q1-WebApp": 25,
        "2025-Q2-MobileApp": 12
      },
      "Areas": {
        "Documentation": 8,
        "Research": 5
      },
      "Resources": {
        "References": 10
      },
      "Archives": {
        "2024-Completed": 3
      }
    },
    "errors": [
      {
        "filePath": "/Users/jun/Documents/MyProject/protected-file.txt",
        "reason": "권한 부족",
        "severity": "WARNING"
      }
    ]
  },
  "executedAt": "2025-11-11T10:37:05Z"
}
```

**응답 (200 OK)**:
```json
{
  "taskId": "task_507f1f77bcf86cd799439011",
  "status": "COMPLETED",
  "message": "재정리가 완료되었습니다",
  "completedAt": "2025-11-11T10:37:10Z"
}
```

---

## 구현 예제

### 1. FastAPI 측: 스키마 정의

**파일**: `app/schemas/organization.py`

```python
"""파일 정리 및 Spring 연동 스키마"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class OrganizationStrategy(str, Enum):
    """파일 정리 전략"""
    COST_EFFECTIVE = "COST_EFFECTIVE"
    BALANCED = "BALANCED"
    PREMIUM = "PREMIUM"


class FileEntry(BaseModel):
    """파일/폴더 메타데이터"""
    relative_path: str = Field(..., description="루트 기준 상대 경로")
    absolute_path: str = Field(..., description="절대 경로")
    is_directory: bool = Field(..., description="폴더 여부")
    size_bytes: int = Field(..., ge=0, description="파일 크기")
    modified_at: datetime = Field(..., description="수정 시간")
    is_development: bool = Field(default=False, description="개발 폴더 여부")
    file_type: Optional[str] = Field(None, description="파일 타입")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    caption: Optional[str] = Field(None, description="파일 요약")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="추출 신뢰도")


class SnapshotBatchRequest(BaseModel):
    """Spring으로 전송할 배치"""
    task_id: str = Field(..., description="작업 ID")
    batch_number: int = Field(..., ge=1, description="배치 번호")
    total_batches: int = Field(..., ge=1, description="전체 배치 수")
    directory: str = Field(..., description="루트 디렉터리")
    user_id: str = Field(..., description="사용자 ID")
    strategy: OrganizationStrategy = Field(..., description="정리 전략")
    max_cost_budget: Optional[float] = Field(None, ge=0, description="최대 예산")
    generated_at: datetime = Field(..., description="생성 시간")
    entries: List[FileEntry] = Field(..., description="파일 목록")


class SnapshotBatchResponse(BaseModel):
    """Spring 응답"""
    task_id: str
    batch_number: int
    total_batches: int
    status: str
    message: str
    received_at: datetime
    next_batch_expected_at: Optional[datetime] = None


class TaskStatusResponse(BaseModel):
    """작업 상태"""
    task_id: str
    status: str  # PROCESSING, AI_PROCESSING, COMPLETED, FAILED
    progress: Optional[int] = None
    message: Optional[str] = None


class FolderStructureItem(BaseModel):
    """폴더 구조 항목"""
    folder_name: str
    files: List[str]
    reasoning: str


class OrganizationResult(BaseModel):
    """최종 정리 결과"""
    organization: dict[str, List[FolderStructureItem]]
    statistics: dict
    execution_details: dict
    ready_to_execute: bool


class OrganizationRequest(BaseModel):
    """클라이언트 요청"""
    path: str = Field(..., description="정리할 폴더 경로")
    strategy: OrganizationStrategy = Field(default=OrganizationStrategy.BALANCED)
    max_cost_budget: Optional[float] = Field(None, description="최대 비용")
```

---

### 2. FastAPI 측: 서비스 구현

**파일**: `app/services/spring_integration.py`

```python
"""Spring 서버와의 연동 서비스"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from datetime import datetime, timezone
import asyncio

import httpx
from pydantic import ValidationError

from app.schemas.organization import (
    SnapshotBatchRequest,
    SnapshotBatchResponse,
    FileEntry,
)

logger = logging.getLogger(__name__)


class SpringIntegrationError(Exception):
    """Spring 연동 실패"""
    pass


class SpringClient:
    """Spring 서버 클라이언트"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    async def send_snapshot_batch(
        self,
        batch_request: SnapshotBatchRequest,
    ) -> SnapshotBatchResponse:
        """배치 전송"""
        url = f"{self.base_url}/api/snapshots/batch"
        headers = self._build_headers()

        payload = batch_request.model_dump(
            by_alias=True,
            exclude_none=True,
            mode="json"
        )

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout,
                    )

                if response.status_code == 200:
                    return SnapshotBatchResponse(**response.json())
                elif response.status_code == 429:
                    # 속도 제한: 지수 백오프
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Spring 서버가 속도 제한 중. {wait_time}초 대기..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                elif response.status_code >= 400:
                    error_data = response.json()
                    raise SpringIntegrationError(
                        f"Spring 에러 ({response.status_code}): "
                        f"{error_data.get('message', 'Unknown error')}"
                    )

            except httpx.TimeoutException as exc:
                if attempt == self.max_retries - 1:
                    raise SpringIntegrationError(
                        f"Spring 서버 타임아웃 (시도 {attempt + 1}/{self.max_retries})"
                    ) from exc
                await asyncio.sleep(2 ** attempt)

            except httpx.RequestError as exc:
                if attempt == self.max_retries - 1:
                    raise SpringIntegrationError(
                        f"Spring 서버 연결 실패: {str(exc)}"
                    ) from exc
                await asyncio.sleep(2 ** attempt)

        raise SpringIntegrationError(
            f"최대 재시도 횟수 초과 ({self.max_retries})"
        )

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """작업 상태 조회"""
        url = f"{self.base_url}/api/snapshots/tasks/{task_id}"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                raise SpringIntegrationError(
                    f"상태 조회 실패: {response.status_code}"
                )

        except httpx.RequestError as exc:
            raise SpringIntegrationError(
                f"상태 조회 네트워크 오류: {str(exc)}"
            ) from exc

    async def get_organization_result(self, task_id: str) -> dict[str, Any]:
        """정리 결과 조회"""
        url = f"{self.base_url}/api/snapshots/tasks/{task_id}/result"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                raise SpringIntegrationError(
                    f"결과 조회 실패: {response.status_code}"
                )

        except httpx.RequestError as exc:
            raise SpringIntegrationError(
                f"결과 조회 네트워크 오류: {str(exc)}"
            ) from exc

    async def report_execution_result(
        self,
        task_id: str,
        execution_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """재정리 완료 보고"""
        url = (
            f"{self.base_url}/api/snapshots/tasks/{task_id}/execution-result"
        )
        headers = self._build_headers()

        payload = {
            "taskId": task_id,
            "status": "SUCCESS",
            "executionSummary": execution_summary,
            "executedAt": datetime.now(timezone.utc).isoformat(),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                raise SpringIntegrationError(
                    f"완료 보고 실패: {response.status_code}"
                )

        except httpx.RequestError as exc:
            raise SpringIntegrationError(
                f"완료 보고 네트워크 오류: {str(exc)}"
            ) from exc

    def _build_headers(self) -> dict[str, str]:
        """요청 헤더 생성"""
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
```

---

### 3. FastAPI 측: 라우터 구현

**파일**: `app/routers/organization.py`

```python
"""파일 정리 및 재정리 라우터"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from app.schemas.organization import (
    OrganizationRequest,
    OrganizationStrategy,
    FileEntry,
    SnapshotBatchRequest,
)
from app.services.spring_integration import SpringClient, SpringIntegrationError
from app.services.folder_inspection import (
    DirectoryInspectionError,
    resolve_directory,
)
from app.services.ml_extraction import extract_file_insights
from app.extraction.handlers.image import extract_image_highlights
from app.extraction.handlers.pdf import extract_pdf_keywords
from app.extraction.handlers.xls import build_summary_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["organization"])


# 의존성: Spring 클라이언트
async def get_spring_client() -> SpringClient:
    """Spring 클라이언트 의존성"""
    import os
    return SpringClient(
        base_url=os.getenv("SPRING_SERVER_URL", "http://localhost:8080"),
        api_key=os.getenv("SPRING_API_KEY", ""),
    )


# 진행 중인 작업 저장소 (실제로는 Redis 사용 권장)
_task_storage: dict[str, dict] = {}


@router.post("/organize")
async def organize_folder(
    request: OrganizationRequest,
    spring_client: SpringClient = Depends(get_spring_client),
) -> JSONResponse:
    """
    파일 정리 시작

    1. 경로 검증
    2. 파일 수집
    3. 배치 생성
    4. Spring에 전송
    5. 작업 ID 반환
    """
    task_id = str(uuid.uuid4())

    try:
        # 1. 경로 검증
        directory = resolve_directory(request.path)
        logger.info(f"[{task_id}] 정리 시작: {directory}")

        # 2. 파일 수집 및 메타데이터 추출
        files = await _collect_and_extract_files(
            directory,
            task_id,
        )

        logger.info(
            f"[{task_id}] {len(files)}개 파일 수집 완료"
        )

        # 3. 배치 생성 (50개 단위)
        batch_size = _get_batch_size(request.strategy)
        batches = _chunk_files(files, batch_size)

        logger.info(
            f"[{task_id}] {len(batches)}개 배치 생성 (배치 크기: {batch_size})"
        )

        # 4. Spring에 배치 전송 (백그라운드)
        import asyncio
        asyncio.create_task(
            _send_batches_to_spring(
                task_id=task_id,
                directory=str(directory),
                user_id="user_" + task_id[:12],  # 임시 사용자 ID
                batches=batches,
                strategy=request.strategy,
                max_cost_budget=request.max_cost_budget,
                spring_client=spring_client,
            )
        )

        # 5. 작업 저장
        _task_storage[task_id] = {
            "status": "PROCESSING",
            "directory": str(directory),
            "total_files": len(files),
            "total_batches": len(batches),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return JSONResponse(
            status_code=202,  # Accepted
            content={
                "taskId": task_id,
                "status": "PROCESSING",
                "message": "파일 정리가 시작되었습니다",
                "totalFiles": len(files),
                "totalBatches": len(batches),
            },
        )

    except DirectoryInspectionError as exc:
        logger.error(f"[{task_id}] 경로 검증 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception(f"[{task_id}] 예상치 못한 오류: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파일 정리 시작 중 오류가 발생했습니다",
        )


@router.get("/organize/{task_id}")
async def get_organization_status(
    task_id: str,
    spring_client: SpringClient = Depends(get_spring_client),
) -> JSONResponse:
    """작업 상태 조회"""
    try:
        # 로컬 상태 확인
        if task_id in _task_storage:
            local_status = _task_storage[task_id]
        else:
            local_status = None

        # Spring에서 상태 조회
        spring_status = await spring_client.get_task_status(task_id)

        return JSONResponse(
            content={
                "taskId": task_id,
                "localStatus": local_status,
                "springStatus": spring_status,
            }
        )

    except SpringIntegrationError as exc:
        logger.error(f"Spring 상태 조회 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spring 서버와 통신할 수 없습니다",
        )


@router.post("/reorganize/execute")
async def execute_reorganization(
    request: dict,
) -> JSONResponse:
    """
    Spring에서 보낸 재정리 명령 실행

    요청:
    {
        "taskId": "...",
        "sourceDirectory": "...",
        "targetBaseDirectory": "...",
        "fileOperations": [...]
    }
    """
    task_id = request.get("taskId")

    try:
        logger.info(
            f"[{task_id}] 재정리 실행 시작: "
            f"{request.get('sourceDirectory')} → "
            f"{request.get('targetBaseDirectory')}"
        )

        # TODO: 파일 이동 로직 구현
        # 1. 폴더 구조 생성
        # 2. 파일 이동 (또는 심링크)
        # 3. 오류 처리 및 로깅

        execution_summary = {
            "totalOperations": len(request.get("fileOperations", [])),
            "succeededOperations": 0,
            "failedOperations": 0,
            "duration": 0,
            "errors": [],
        }

        # Spring에 완료 보고
        # await spring_client.report_execution_result(task_id, execution_summary)

        return JSONResponse(
            status_code=202,
            content={
                "taskId": task_id,
                "status": "EXECUTING",
                "message": "재정리를 시작했습니다",
            },
        )

    except Exception as exc:
        logger.exception(f"[{task_id}] 재정리 실행 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="재정리 실행 중 오류가 발생했습니다",
        )


# 헬퍼 함수들

async def _collect_and_extract_files(
    directory,
    task_id: str,
) -> list[FileEntry]:
    """파일 수집 및 메타데이터 추출"""
    files = []

    for path in directory.rglob("*"):
        if path.name.startswith("."):
            continue

        try:
            file_type = _get_file_type(path)
            keywords = []
            caption = None
            confidence = 0.0

            # ML 기반 키워드 추출
            if path.is_file():
                try:
                    if file_type == "pdf":
                        keywords = extract_pdf_keywords(str(path))
                        confidence = 0.9
                    elif file_type == "image":
                        result = extract_image_highlights(str(path))
                        keywords = result.ocr_lines
                        caption = result.caption
                        confidence = 0.85
                    elif file_type in ("xlsx", "csv"):
                        caption, _ = build_summary_text(str(path))
                        keywords = [caption] if caption else []
                        confidence = 0.8
                except Exception as exc:
                    logger.warning(
                        f"[{task_id}] {path}에서 키워드 추출 실패: {exc}"
                    )

            files.append(
                FileEntry(
                    relative_path=str(path.relative_to(directory)),
                    absolute_path=str(path),
                    is_directory=path.is_dir(),
                    size_bytes=path.stat().st_size,
                    modified_at=datetime.fromtimestamp(
                        path.stat().st_mtime,
                        tz=timezone.utc,
                    ),
                    file_type=file_type,
                    keywords=keywords[:5],  # 상위 5개만
                    caption=caption,
                    confidence=confidence,
                )
            )

        except Exception as exc:
            logger.warning(
                f"[{task_id}] {path} 처리 중 오류: {exc}"
            )
            continue

    return files


def _get_file_type(path) -> Optional[str]:
    """파일 타입 결정"""
    suffix = path.suffix.lower()

    type_mapping = {
        ".pdf": "pdf",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".webp": "image",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".csv": "csv",
        ".md": "markdown",
        ".txt": "text",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
    }

    return type_mapping.get(suffix)


def _chunk_files(files: list[FileEntry], batch_size: int) -> list[list[FileEntry]]:
    """파일을 배치로 분할"""
    batches = []
    for i in range(0, len(files), batch_size):
        batches.append(files[i : i + batch_size])
    return batches


def _get_batch_size(strategy: OrganizationStrategy) -> int:
    """전략에 따른 배치 크기"""
    mapping = {
        OrganizationStrategy.COST_EFFECTIVE: 100,
        OrganizationStrategy.BALANCED: 50,
        OrganizationStrategy.PREMIUM: 20,
    }
    return mapping.get(strategy, 50)


async def _send_batches_to_spring(
    task_id: str,
    directory: str,
    user_id: str,
    batches: list[list[FileEntry]],
    strategy: OrganizationStrategy,
    max_cost_budget: Optional[float],
    spring_client: SpringClient,
) -> None:
    """배치를 순차적으로 Spring에 전송"""
    total_batches = len(batches)

    for batch_num, batch_files in enumerate(batches, start=1):
        try:
            logger.info(
                f"[{task_id}] 배치 {batch_num}/{total_batches} 전송 중..."
            )

            batch_request = SnapshotBatchRequest(
                task_id=task_id,
                batch_number=batch_num,
                total_batches=total_batches,
                directory=directory,
                user_id=user_id,
                strategy=strategy,
                max_cost_budget=max_cost_budget,
                generated_at=datetime.now(timezone.utc),
                entries=batch_files,
            )

            response = await spring_client.send_snapshot_batch(batch_request)

            logger.info(
                f"[{task_id}] 배치 {batch_num} 전송 완료: {response.status}"
            )

        except SpringIntegrationError as exc:
            logger.error(
                f"[{task_id}] 배치 {batch_num} 전송 실패: {exc}"
            )
            # TODO: 재시도 로직 또는 실패 처리
            break

        except Exception as exc:
            logger.exception(
                f"[{task_id}] 배치 {batch_num} 예상치 못한 오류: {exc}"
            )
            break
```

---

### 4. main.py에서 라우터 등록

```python
# app/main.py

from fastapi import FastAPI
from app.routers import organization

app = FastAPI(title="Nebula Client API")

# 라우터 등록
app.include_router(organization.router)

# 기존 라우터들...
```

---

### 5. 환경 변수 설정

**`.env.example`**에 추가:

```bash
# Spring 서버 연동
SPRING_SERVER_URL=http://localhost:8080
SPRING_API_KEY=your-api-key-here

# 작업 큐 (추후)
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

---

## 메시지 큐 통합

### RabbitMQ를 사용한 비동기 처리 (권장)

**파일**: `app/services/message_queue.py`

```python
"""메시지 큐 기반 이벤트 발행"""

from abc import ABC, abstractmethod
import json
from typing import Any, Dict
import aio_pika
import logging

logger = logging.getLogger(__name__)


class MessagePublisher(ABC):
    """메시지 발행 추상 클래스"""

    @abstractmethod
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        pass


class RabbitMQPublisher(MessagePublisher):
    """RabbitMQ 기반 메시지 발행"""

    def __init__(self, url: str = "amqp://localhost/"):
        self.url = url
        self.connection = None
        self.channel = None

    async def connect(self) -> None:
        """RabbitMQ 연결"""
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """메시지 발행"""
        if not self.channel:
            await self.connect()

        exchange = await self.channel.declare_exchange(
            "nebula_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        message_body = json.dumps(message, default=str).encode()

        await exchange.publish(
            aio_pika.Message(
                body=message_body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=topic,
        )

        logger.info(f"Published message to {topic}")

    async def close(self) -> None:
        """연결 종료"""
        if self.connection:
            await self.connection.close()
```

---

## 에러 처리

### 재시도 정책

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SpringIntegrationError),
)
async def send_with_retry(self, batch_request):
    """3회 재시도, 지수 백오프"""
    return await self.send_snapshot_batch(batch_request)
```

---

## 배포 및 운영

### Docker Compose 설정

**`docker-compose.yml`**:

```yaml
version: "3.8"

services:
  fastapi:
    build: .
    ports:
      - "8000:8000"
    environment:
      SPRING_SERVER_URL: http://spring-server:8080
      SPRING_API_KEY: ${SPRING_API_KEY}
      REDIS_URL: redis://redis:6379
    depends_on:
      - redis
      - spring-server
    volumes:
      - ./app:/app/app

  spring-server:
    image: spring-server:latest
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: jdbc:postgresql://postgres:5432/nebula
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: nebula
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

---

### 모니터링 및 로깅

```python
# app/middleware/logging.py

import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    """요청 로깅 미들웨어"""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {duration:.2f}s"
    )

    return response
```

---

## 결론

이 가이드를 통해 FastAPI와 Spring 서버를 효과적으로 연동할 수 있습니다:

1. **FastAPI**: 로컬 파일 수집 및 ML 추출에 집중
2. **Spring**: 메타데이터 중앙 관리 및 AI 조율
3. **메시지 큐**: 비동기 처리로 확장성 확보
4. **에러 처리**: 재시도 정책으로 안정성 확보

질문이나 추가 설명이 필요하면 문의하세요!
