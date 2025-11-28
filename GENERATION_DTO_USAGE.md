# Generation DTO 사용 가이드

새로운 `OrganizedFileSaveWithGenerationRequestDto` DTO 구조를 사용하는 방법을 설명합니다.

---

## 📋 목차

1. [개요](#개요)
2. [API 엔드포인트](#api-엔드포인트)
3. [DTO 구조](#dto-구조)
4. [사용 예제](#사용-예제)
5. [마이그레이션](#마이그레이션)

---

## 개요

### 기존 vs 새로운 구조

**기존 (OrganizedFileSaveRequest)**:
```json
{
  "userId": "621c7d3957c2ea5b9063d04c",
  "baseDirectory": "/path/to/folder",
  "files": [
    {
      "originalRelativePath": "file.txt",
      "directory": false,
      "development": false,
      "sizeBytes": 100,
      "modifiedAt": "2025-11-19T10:30:00Z",
      "keywords": ["keyword"],
      "koreanFileName": "파일.txt",
      "englishFileName": "file.txt",
      "paraBucket": "Resources",
      "paraFolder": null,
      "reason": "Auto organized"
    }
  ]
}
```

**새로운 (OrganizedFileSaveWithGenerationRequest)**:
```json
{
  "userId": "621c7d3957c2ea5b9063d04c",
  "baseDirectory": "/path/to/folder",
  "files": [
    {
      "relativePath": "file.txt",
      "absolutePath": "/path/to/folder/file.txt",
      "isDirectory": false,
      "sizeBytes": 100,
      "modifiedAt": "2025-11-19T10:30:00Z",
      "isDevelopment": false,
      "keywords": ["keyword"]
    }
  ]
}
```

### 주요 차이점

| 항목 | 기존 | 새로운 |
|------|------|--------|
| 파일명 생성 | 클라이언트 | **Spring 서버** (AI 기반) |
| PARA 분류 | 클라이언트 | **Spring 서버** (AI 기반) |
| paraFolder | 포함 | 제거 |
| 절대경로 | 미포함 | **포함** |
| 한글/영문명 | **포함** | 제거 |

---

## API 엔드포인트

### 기존 엔드포인트
```
POST /api/folders/inspect-and-organize
POST /api/folders/inspect-and-organize?page_size=100
```

### 새로운 엔드포인트 ⭐
```
POST /api/folders/inspect-and-organize-with-generation
POST /api/folders/inspect-and-organize-with-generation?page_size=100
```

---

## DTO 구조

### FileEntryForGeneration (파일 정보)

```python
class FileEntryForGeneration(BaseModel):
    relative_path: str              # 상대 경로
    absolute_path: str              # 절대 경로
    is_directory: bool              # 디렉토리 여부
    size_bytes: int                 # 파일 크기 (바이트)
    modified_at: str                # 수정 시간 (ISO 8601)
    is_development: bool            # 개발 파일 여부
    keywords: List[str]             # 추출된 키워드
```

### OrganizedFileSaveWithGenerationRequest (요청)

```python
class OrganizedFileSaveWithGenerationRequest(BaseModel):
    user_id: str                                      # 사용자 ID
    base_directory: str                               # 기본 디렉터리
    files: List[FileEntryForGeneration]              # 파일 목록
```

---

## 사용 예제

### TypeScript/JavaScript

#### 기본 사용
```typescript
import { inspectAndOrganizeWithGeneration } from "./api/frontend-client";

async function organizeWithGeneration() {
  try {
    const result = await inspectAndOrganizeWithGeneration(
      "/Users/jun/Documents/MyFolder"
    );

    console.log(`총 파일: ${result.totalFiles}개`);
    console.log(`저장: ${result.savedCount}개`);
    console.log(`업데이트: ${result.updatedCount}개`);

    // 이제 Spring 서버가 AI 기반으로 다음을 수행:
    // - 파일명 자동 생성
    // - PARA 분류 자동 수행
    // - 파일 정보 저장
  } catch (error) {
    console.error("처리 실패:", error);
  }
}
```

#### 커스텀 페이지 크기
```typescript
const result = await inspectAndOrganizeWithGeneration(
  "/Users/jun/Documents/LargeFolder",
  "http://localhost:8000",
  200  // 200개씩 처리
);

console.log(`${result.totalPages}개 페이지로 처리 완료`);
```

#### React 컴포넌트에서 사용
```typescript
import React, { useState } from "react";
import { inspectAndOrganizeWithGeneration } from "./api/frontend-client";

function GenerationOrganizeComponent() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleOrganize = async (folderPath: string) => {
    setLoading(true);
    try {
      const result = await inspectAndOrganizeWithGeneration(folderPath);
      setResult(result);

      alert(
        `완료!\n` +
        `저장: ${result.savedCount}개\n` +
        `업데이트: ${result.updatedCount}개`
      );
    } catch (error) {
      alert(`오류: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={() => handleOrganize("/path/to/folder")}
        disabled={loading}
      >
        {loading ? "처리 중..." : "AI 기반 파일 정리"}
      </button>
      {result && (
        <div>
          <p>총 파일: {result.totalFiles}개</p>
          <p>저장됨: {result.savedCount}개</p>
        </div>
      )}
    </div>
  );
}
```

### Python (FastAPI)

클라이언트 코드는 자동으로 처리됩니다:

```python
from app.services.organized_file_client import OrganizedFileClient
from app.services.folder_inspection import (
    inspect_directory_with_keywords,
    to_file_entry_for_generation,
)

async def process_with_generation(folder_path: str, user_id: str):
    # 1. 폴더 검사
    response, entries = await inspect_directory_with_keywords(folder_path)

    # 2. Generation 포맷으로 변환
    from pathlib import Path
    directory_root = Path(response.directory)

    generation_entries = [
        to_file_entry_for_generation(directory_root, entry)
        for entry in entries
    ]

    # 3. Spring 서버로 전송
    client = OrganizedFileClient()
    result = await client.save_files_with_generation(
        user_id=user_id,
        base_directory=str(directory_root),
        files=generation_entries,
    )

    print(f"저장: {result.saved_count}개")
    print(f"업데이트: {result.updated_count}개")
```

### cURL 테스트

```bash
# 기본값 (100개씩)
curl -X POST "http://localhost:8000/api/folders/inspect-and-organize-with-generation?page_size=100" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/jun/Documents/MyFolder"
  }' | jq .

# 응답 예시
{
  "status": "success",
  "message": "파일이 Spring 서버로 전달되었습니다",
  "directory": "/Users/jun/Documents/MyFolder",
  "totalFiles": 250,
  "totalPages": 3,
  "pageSize": 100,
  "savedCount": 240,
  "updatedCount": 10,
  "failedCount": 0,
  "errorMessages": []
}
```

---

## 마이그레이션

### 기존 코드를 새로운 코드로 마이그레이션하기

#### 이전
```typescript
// 기존 방식
const result = await inspectAndOrganizeFolder(
  "/Users/jun/Documents/MyFolder"
);
```

#### 이후
```typescript
// 새로운 방식 (AI 기반 파일 정리)
const result = await inspectAndOrganizeWithGeneration(
  "/Users/jun/Documents/MyFolder"
);

// 또는 기존 방식 계속 사용 가능
const oldResult = await inspectAndOrganizeFolder(
  "/Users/jun/Documents/MyFolder"
);
```

### 장점

| 측면 | 개선 |
|------|------|
| 파일명 생성 | 간단한 규칙 → **AI 기반 자동 생성** |
| PARA 분류 | 키워드 기반 → **AI 기반 지능형 분류** |
| 유연성 | 고정됨 → **Spring에서 맞춤 설정 가능** |
| 확장성 | 제한적 → **새로운 요구사항 수용** |

### 동시 운영

두 가지 방식을 동시에 지원하므로, 점진적 마이그레이션이 가능합니다:

```typescript
// 방식 1: 기존 (OrganizedFileSaveRequest)
const oldResult = await inspectAndOrganizeFolder("/path");

// 방식 2: 새로운 (OrganizedFileSaveWithGenerationRequest)
const newResult = await inspectAndOrganizeWithGeneration("/path");

// 두 결과를 비교하거나 병렬 처리 가능
```

---

## 성능 비교

| 작업 | 기존 방식 | 새로운 방식 |
|------|----------|----------|
| 클라이언트 처리 | 1-2초 | ~500ms (간소화됨) |
| 서버 처리 | ~500ms | 2-5초 (AI 생성) |
| **전체** | **1-2초** | **2-5초** |
| 결과 품질 | 기본 | **높음** ⭐ |

---

## 답변 형식

### 성공 응답 (200)

```json
{
  "status": "success",
  "message": "파일이 Spring 서버로 전달되었습니다",
  "directory": "/Users/jun/Documents/MyFolder",
  "totalFiles": 250,
  "totalPages": 3,
  "pageSize": 100,
  "savedCount": 240,
  "updatedCount": 10,
  "failedCount": 0,
  "errorMessages": []
}
```

### 에러 응답 (400, 500)

```json
{
  "detail": "해당 경로가 존재하지 않습니다"
}
```

---

## 권장 사항

### 언제 어느 방식을 사용할까?

| 상황 | 권장 방식 |
|------|----------|
| 빠른 처리 필요 | `inspectAndOrganizeFolder` |
| 최고의 결과 품질 원함 | `inspectAndOrganizeWithGeneration` ⭐ |
| AI 기반 분류 필요 | `inspectAndOrganizeWithGeneration` ⭐ |
| 맞춤형 파일명 생성 원함 | `inspectAndOrganizeWithGeneration` ⭐ |

---

**Last Updated**: 2025-11-19
**Version**: 1.0
