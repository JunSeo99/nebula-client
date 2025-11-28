# 프론트엔드 - Organized Files API 사용 가이드

FastAPI 서버의 Organized Files API를 프론트엔드에서 사용하는 방법을 설명합니다.

---

## 📋 목차

1. [API 클라이언트 설정](#api-클라이언트-설정)
2. [TypeScript 사용](#typescript-사용)
3. [React 컴포넌트](#react-컴포넌트)
4. [사용 예제](#사용-예제)
5. [에러 처리](#에러-처리)
6. [트러블슈팅](#트러블슈팅)

---

## API 클라이언트 설정

### 설치

```bash
# 1. frontend-client.ts를 프로젝트에 복사
cp frontend-client.ts /path/to/your/frontend/src/api/

# 2. 필요한 경우 타입 정의 추가
# frontend-client.ts 파일의 인터페이스 사용
```

### 기본 설정

```typescript
import {
  inspectAndOrganizeFolder,
  inspectAndOrganizeBatch,
  getUserStats,
  getFilesByBucket,
} from "./api/frontend-client";

// API 서버 주소 설정 (기본값: http://localhost:8000)
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

---

## TypeScript 사용

### 1. 단일 폴더 처리 (페이징 지원)

```typescript
// 기본값: 100개씩 처리
async function organizeSmallFolder() {
  try {
    const result = await inspectAndOrganizeFolder(
      "/Users/jun/Documents/MyFolder",
      API_BASE_URL
    );

    console.log(`총 파일: ${result.totalFiles}개`);
    console.log(`총 페이지: ${result.totalPages}개`);
    console.log(`저장: ${result.savedCount}개`);
    console.log(`업데이트: ${result.updatedCount}개`);
    console.log(`실패: ${result.failedCount}개`);

    if (result.errorMessages.length > 0) {
      console.error("에러 메시지:", result.errorMessages);
    }
  } catch (error) {
    console.error("처리 실패:", error);
  }
}

// 커스텀 페이지 크기: 200개씩 처리
async function organizeLargeFolder() {
  try {
    const result = await inspectAndOrganizeFolder(
      "/Users/jun/Documents/LargeFolder",
      API_BASE_URL,
      200  // 페이지 크기 (10-500)
    );

    console.log(`${result.totalPages}개 페이지로 처리 완료`);
    console.log(`저장: ${result.savedCount}, 업데이트: ${result.updatedCount}`);
  } catch (error) {
    console.error("처리 실패:", error);
  }
}
```

### 2. 배치 폴더 처리 (대규모)

```typescript
// 100개 이상의 파일을 가진 폴더 배치 처리
async function organizeLargeFolder() {
  try {
    const result = await inspectAndOrganizeBatch(
      "/Users/jun/Documents/LargeFolder",
      API_BASE_URL
    );

    console.log(
      `배치 처리 시작: ${result.totalFiles}개 파일을 ${result.totalBatches}개 배치로 처리`
    );
    // 백그라운드에서 비동기 처리됨 (202 Accepted 응답)
  } catch (error) {
    console.error("배치 처리 실패:", error);
  }
}
```

### 3. 사용자 통계 조회

```typescript
async function getUserFileStats(userId: string) {
  try {
    const stats = await getUserStats(userId, API_BASE_URL);

    console.log(`총 파일: ${stats.totalFiles}개`);
    console.log(`프로젝트: ${stats.projectsCount}개`);
    console.log(`영역: ${stats.areasCount}개`);
    console.log(`리소스: ${stats.resourcesCount}개`);
    console.log(`보관: ${stats.archiveCount}개`);
  } catch (error) {
    console.error("통계 조회 실패:", error);
  }
}
```

### 4. PARA 버킷별 파일 조회

```typescript
async function getProjectFiles(userId: string) {
  try {
    const files = await getFilesByBucket(
      userId,
      "Projects",
      API_BASE_URL
    );

    console.log(`프로젝트 파일: ${files.length}개`);
    files.forEach((file) => {
      console.log(`- ${file.originalRelativePath}`);
    });
  } catch (error) {
    console.error("파일 조회 실패:", error);
  }
}
```

---

## React 컴포넌트

### 기본 사용

```typescript
import { OrganizedFilesComponent } from "./components/OrganizedFilesComponent";

function App() {
  return (
    <div>
      <h1>파일 정리</h1>
      <OrganizedFilesComponent />
    </div>
  );
}
```

### 커스터마이징

```typescript
import React, { useState } from "react";
import { inspectAndOrganizeFolder } from "./api/frontend-client";

export function CustomOrganizeComponent() {
  const [loading, setLoading] = useState(false);

  const handleOrganize = async (folderPath: string) => {
    setLoading(true);
    try {
      const result = await inspectAndOrganizeFolder(folderPath);

      // 커스텀 로직
      if (result.failedCount > 0) {
        alert(
          `⚠️ ${result.failedCount}개 파일이 실패했습니다`
        );
      }

      // UI 업데이트
      updateUI(result);
    } finally {
      setLoading(false);
    }
  };

  return (
    // ... 컴포넌트 렌더링
  );
}
```

---

## 사용 예제

### 예제 1: 폴더 선택 후 정리

```typescript
// Electron IPC 또는 웹 File API 사용
async function selectFolderAndOrganize() {
  let folderPath: string;

  // 1. 폴더 선택
  if (window.electronAPI) {
    // Electron 환경
    folderPath = await window.electronAPI.selectFolder();
  } else {
    // 웹 브라우저 (현재 미지원)
    folderPath = prompt("폴더 경로를 입력하세요:");
  }

  if (!folderPath) return;

  // 2. 파일 정리
  const result = await inspectAndOrganizeFolder(folderPath);

  // 3. 결과 표시
  showResult(result);
}
```

### 예제 2: 진행 상황 표시

```typescript
async function organizeWithProgress(
  folderPath: string,
  onProgress: (message: string) => void
) {
  onProgress("폴더 검사 중...");

  try {
    onProgress("파일 정리 중...");
    const result = await inspectAndOrganizeFolder(folderPath);

    onProgress(
      `완료! 저장: ${result.savedCount}, 업데이트: ${result.updatedCount}`
    );
  } catch (error) {
    onProgress(`실패: ${error}`);
  }
}

// 사용
organizeWithProgress("/path/to/folder", (msg) => {
  console.log(msg);
  // UI 업데이트
});
```

### 예제 3: 대량 폴더 처리

```typescript
async function organizeMultipleFolders(folderPaths: string[]) {
  const results = [];

  for (const folderPath of folderPaths) {
    try {
      const result = await inspectAndOrganizeFolder(folderPath);
      results.push({ path: folderPath, ...result });
    } catch (error) {
      results.push({ path: folderPath, error });
    }
  }

  return results;
}
```

---

## 에러 처리

### HTTP 에러 (400, 500 등)

```typescript
async function safeOrganizeFolder(folderPath: string) {
  try {
    const result = await inspectAndOrganizeFolder(folderPath);
    return result;
  } catch (error) {
    if (error instanceof Error) {
      const message = error.message;

      if (message.includes("400")) {
        console.error("폴더 경로가 유효하지 않습니다");
      } else if (message.includes("503")) {
        console.error("Spring 서버에 연결할 수 없습니다");
      } else if (message.includes("500")) {
        console.error("서버 내부 에러가 발생했습니다");
      } else {
        console.error("알 수 없는 에러:", message);
      }
    }
  }
}
```

### 네트워크 에러

```typescript
async function organizeWithRetry(
  folderPath: string,
  maxRetries: number = 3
) {
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await inspectAndOrganizeFolder(folderPath);
    } catch (error) {
      lastError = error as Error;
      console.warn(`시도 ${attempt}/${maxRetries} 실패, 재시도 중...`);

      // 지수 백오프
      if (attempt < maxRetries) {
        await new Promise((resolve) =>
          setTimeout(resolve, Math.pow(2, attempt) * 1000)
        );
      }
    }
  }

  throw new Error(`모든 재시도가 실패했습니다: ${lastError?.message}`);
}
```

---

## 트러블슈팅

### 1. CORS 에러

```
Error: Access to XMLHttpRequest at 'http://localhost:8000/...'
from origin 'http://localhost:3000' has been blocked by CORS policy
```

**해결:**

FastAPI 서버의 `app/main.py`에 CORS 설정 추가:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. 폴더 경로 에러

```
Error: 해당 경로가 존재하지 않습니다
```

**해결:**

- 절대 경로를 사용하세요
- 폴더가 실제로 존재하는지 확인하세요
- 권한을 확인하세요

```typescript
// ❌ 잘못된 예
inspectAndOrganizeFolder("~/Documents/MyFolder");
inspectAndOrganizeFolder("./my-folder");

// ✅ 올바른 예
inspectAndOrganizeFolder("/Users/jun/Documents/MyFolder");
inspectAndOrganizeFolder("/home/user/Documents/MyFolder");
```

### 3. 타임아웃 에러

```
Error: Spring 서버 타임아웃 (30초)
```

**해결:**

- Spring 서버가 실행 중인지 확인
- 네트워크 연결 확인
- 대용량 폴더는 배치 처리 사용

```typescript
// 배치 처리 사용 (비동기)
const result = await inspectAndOrganizeBatch(folderPath);
```

### 4. 권한 에러

```
Error: 디렉터리에 접근 권한이 없습니다
```

**해결:**

```bash
# 폴더 권한 확인
ls -ld /path/to/folder

# 필요시 권한 변경
chmod 755 /path/to/folder
```

---

## 응답 형식

### 성공 응답 (200)

```json
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

### 배치 처리 응답 (202)

```json
{
  "status": "processing",
  "message": "배치 처리가 시작되었습니다",
  "directory": "/Users/jun/Documents/LargeFolder",
  "totalFiles": 500,
  "totalBatches": 10,
  "batchSize": 50
}
```

### 에러 응답 (400, 500)

```json
{
  "detail": "해당 경로가 존재하지 않습니다"
}
```

---

## 최적 사용 가이드

### 엔드포인트 선택

| 파일 수 | 권장 방법 | 페이지 크기 | 특징 |
|--------|----------|----------|------|
| < 100 | 단일 처리 | 기본값 (100) | 동기 처리, 빠른 응답 |
| 100-500 | 단일 처리 | 100-200 | 동기 처리, 여러 페이지 |
| 500+ | 배치 처리 | - | 비동기 처리, 백그라운드 |

### 페이지 크기 선택 기준

| 페이지 크기 | 메모리 | 네트워크 | 응답 시간 | 권장 상황 |
|----------|--------|--------|---------|----------|
| 50 | 낮음 | 빠름 | 짧음 | 느린 네트워크, 저사양 기기 |
| 100 | 중간 | 중간 | 중간 | 일반적인 상황 (기본값) |
| 200 | 높음 | 느림 | 길어짐 | 빠른 네트워크, 고사양 기기 |
| 500 | 매우 높음 | 느림 | 길어짐 | 로컬 네트워크, 특수 상황 |

### 예상 처리 시간

```
파일 100개, 페이지 크기 100:
→ 1개 페이지 → 약 1-2초

파일 500개, 페이지 크기 100:
→ 5개 페이지 → 약 5-10초

파일 1000개, 페이지 크기 100:
→ 10개 페이지 → 약 10-20초

파일 1000개+:
→ 배치 처리 권장 (비동기 처리)
```

---

**Last Updated**: 2025-11-19
**Version**: 1.0
