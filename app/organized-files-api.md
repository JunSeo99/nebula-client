# Organized Files API Documentation

정리된 파일 저장, 조회, 관리를 위한 REST API 문서입니다.

## 📋 목차
- [개요](#개요)
- [Base URL](#base-url)
- [공통 데이터 구조](#공통-데이터-구조)
- [API 엔드포인트](#api-엔드포인트)
- [에러 처리](#에러-처리)
- [사용 예시](#사용-예시)

## 개요

이 API는 PARA(Projects, Areas, Resources, Archive) 방법론에 따라 정리된 파일들을 MongoDB에 저장, 조회, 관리하는 기능을 제공합니다.

### 주요 기능
- ✅ 배치 파일 저장/업데이트 (한 번에 여러 파일 처리)
- ✅ 자동 중복 검사 (기존 파일 업데이트 vs 신규 저장)
- ✅ PARA 방법론 지원 (Projects, Areas, Resources, Archive)
- ✅ 상세한 통계 조회
- ✅ 버킷별 파일 조회
- ✅ 개별 파일 관리 (조회, 삭제)

## Base URL

```
http://localhost:8080/api/organized-files
```

## 공통 데이터 구조

### OrganizedFileEntry

```typescript
interface OrganizedFileEntry {
  id?: string;                    // 업데이트시에만 사용 (선택사항)
  originalRelativePath: string;   // 원본 상대 경로 (필수)
  directory: boolean;             // 디렉토리 여부
  development: boolean;           // 개발 관련 파일 여부
  sizeBytes: number;              // 파일 크기 (바이트)
  modifiedAt: string;             // 수정 시간 (ISO 8601 형식)
  keywords: string[];             // 키워드 목록
  
  // PARA 정리 정보
  koreanFileName: string;         // 한글 파일명
  englishFileName: string;        // 영문 파일명
  paraBucket: string;            // PARA 버킷 (Projects/Areas/Resources/Archive)
  paraFolder?: string;           // 하위 폴더명 (선택사항)
  reason: string;                // 정리 이유
}
```

### SavedFile

```typescript
interface SavedFile {
  id: string;                    // MongoDB 문서 ID
  originalRelativePath: string;   // 원본 상대 경로
  koreanFileName: string;        // 한글 파일명
  englishFileName: string;       // 영문 파일명
  paraBucket: string;           // PARA 버킷
  paraFolder: string;           // PARA 폴더
  operation: 'CREATED' | 'UPDATED';  // 수행된 작업
}
```

### FileStats

```typescript
interface FileStats {
  totalFiles: number;      // 전체 파일 수
  projectsCount: number;   // Projects 버킷 파일 수
  areasCount: number;      // Areas 버킷 파일 수
  resourcesCount: number;  // Resources 버킷 파일 수
  archiveCount: number;    // Archive 버킷 파일 수
  developmentCount: number; // 개발 관련 파일 수
}
```

## API 엔드포인트

### 1. 파일 저장/업데이트

**POST** `/save`

정리된 파일들을 MongoDB에 저장하거나 업데이트합니다.

#### Request Body
```typescript
interface SaveRequest {
  userId: string;                    // 사용자 ID (MongoDB ObjectId)
  baseDirectory: string;            // 기본 디렉토리 경로
  files: OrganizedFileEntry[];      // 저장할 파일 목록
}
```

#### Response
```typescript
interface SaveResponse {
  totalProcessed: number;       // 처리된 전체 파일 수
  savedCount: number;          // 새로 저장된 파일 수
  updatedCount: number;        // 업데이트된 파일 수
  failedCount: number;         // 실패한 파일 수
  errorMessages: string[];     // 에러 메시지 목록
  savedFiles: SavedFile[];     // 저장/업데이트된 파일 정보
  processedAt: string;         // 처리 완료 시간 (ISO 8601)
}
```

#### 예시
```javascript
// Request
const response = await fetch('/api/organized-files/save', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    userId: '621c7d3957c2ea5b9063d04c',
    baseDirectory: '/Users/jun/project',
    files: [
      {
        originalRelativePath: 'src/components/LoginForm.tsx',
        directory: false,
        development: true,
        sizeBytes: 4096,
        modifiedAt: '2024-01-16T14:30:00Z',
        keywords: ['React', 'TypeScript', 'Authentication'],
        koreanFileName: '로그인 폼 컴포넌트.tsx',
        englishFileName: 'Login Form Component.tsx',
        paraBucket: 'Projects',
        paraFolder: 'frontend',
        reason: 'Active project component for authentication'
      }
    ]
  })
});

// Response
{
  "totalProcessed": 1,
  "savedCount": 1,
  "updatedCount": 0,
  "failedCount": 0,
  "errorMessages": [],
  "savedFiles": [
    {
      "id": "691c6d5e6a98595a6f17b3d7",
      "originalRelativePath": "src/components/LoginForm.tsx",
      "koreanFileName": "로그인 폼 컴포넌트.tsx",
      "englishFileName": "Login Form Component.tsx",
      "paraBucket": "Projects",
      "paraFolder": "frontend",
      "operation": "CREATED"
    }
  ],
  "processedAt": "2025-11-18T12:58:06.931566Z"
}
```

---

### 2. 사용자 파일 전체 조회

**GET** `/user/{userId}`

특정 사용자의 모든 정리된 파일을 조회합니다.

#### Parameters
- `userId` (path): 사용자 ID (MongoDB ObjectId)

#### Response
```typescript
OrganizedFileDocument[]
```

#### 예시
```javascript
const response = await fetch('/api/organized-files/user/621c7d3957c2ea5b9063d04c');
const files = await response.json();
// files: 해당 사용자의 모든 정리된 파일 배열
```

---

### 3. 파일 통계 조회

**GET** `/user/{userId}/stats`

특정 사용자의 파일 통계 정보를 조회합니다.

#### Parameters
- `userId` (path): 사용자 ID

#### Response
```typescript
FileStats
```

#### 예시
```javascript
const response = await fetch('/api/organized-files/user/621c7d3957c2ea5b9063d04c/stats');
const stats = await response.json();

// Response
{
  "totalFiles": 5,
  "projectsCount": 1,
  "areasCount": 1,
  "resourcesCount": 3,
  "archiveCount": 0,
  "developmentCount": 2
}
```

---

### 4. PARA 버킷별 파일 조회

**GET** `/user/{userId}/bucket/{paraBucket}`

특정 사용자의 특정 PARA 버킷에 속한 파일들을 조회합니다.

#### Parameters
- `userId` (path): 사용자 ID
- `paraBucket` (path): PARA 버킷 이름 (`Projects`, `Areas`, `Resources`, `Archive`)

#### Response
```typescript
OrganizedFileDocument[]
```

#### 예시
```javascript
// Projects 버킷의 파일들 조회
const response = await fetch('/api/organized-files/user/621c7d3957c2ea5b9063d04c/bucket/Projects');
const projectFiles = await response.json();
```

---

### 5. 개별 파일 조회

**GET** `/user/{userId}/file/{fileId}`

특정 파일의 상세 정보를 조회합니다.

#### Parameters
- `userId` (path): 사용자 ID
- `fileId` (path): 파일 ID (MongoDB ObjectId)

#### Response
```typescript
OrganizedFileDocument | 404 Not Found
```

#### 예시
```javascript
const response = await fetch('/api/organized-files/user/621c7d3957c2ea5b9063d04c/file/691c6d5e6a98595a6f17b3d7');
if (response.ok) {
  const file = await response.json();
  // file: 파일 상세 정보
} else {
  // 파일을 찾을 수 없음
}
```

---

### 6. 파일 삭제

**DELETE** `/user/{userId}/file/{fileId}`

특정 파일을 삭제합니다.

#### Parameters
- `userId` (path): 사용자 ID
- `fileId` (path): 파일 ID

#### Response
- `200 OK`: "File deleted successfully"
- `404 Not Found`: 파일을 찾을 수 없음
- `500 Internal Server Error`: 서버 에러

#### 예시
```javascript
const response = await fetch('/api/organized-files/user/621c7d3957c2ea5b9063d04c/file/691c6d5e6a98595a6f17b3d7', {
  method: 'DELETE'
});

if (response.ok) {
  const message = await response.text();
  console.log(message); // "File deleted successfully"
}
```

## 에러 처리

### HTTP 상태 코드
- `200 OK`: 성공
- `404 Not Found`: 리소스를 찾을 수 없음
- `500 Internal Server Error`: 서버 에러

### 에러 응답 형태
```typescript
interface ErrorResponse {
  error: string;        // 에러 메시지
  details?: any;       // 추가 에러 상세 정보 (선택사항)
}
```

### 일반적인 에러 케이스
1. **잘못된 userId 형식**: MongoDB ObjectId 형식이 아닌 경우
2. **필수 필드 누락**: `originalRelativePath`, `paraBucket` 등 필수 필드 누락
3. **파일 소유권 문제**: 다른 사용자의 파일에 접근 시도
4. **MongoDB 연결 에러**: 데이터베이스 연결 실패

## 사용 예시

### React TypeScript 예시

```typescript
// API 클라이언트 클래스
class OrganizedFilesAPI {
  private baseURL = '/api/organized-files';

  // 파일 저장/업데이트
  async saveFiles(userId: string, baseDirectory: string, files: OrganizedFileEntry[]) {
    const response = await fetch(`${this.baseURL}/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        userId,
        baseDirectory,
        files
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to save files: ${response.status}`);
    }

    return response.json();
  }

  // 파일 통계 조회
  async getFileStats(userId: string): Promise<FileStats> {
    const response = await fetch(`${this.baseURL}/user/${userId}/stats`);
    
    if (!response.ok) {
      throw new Error(`Failed to get stats: ${response.status}`);
    }

    return response.json();
  }

  // PARA 버킷별 파일 조회
  async getFilesByBucket(userId: string, bucket: string) {
    const response = await fetch(`${this.baseURL}/user/${userId}/bucket/${bucket}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get files by bucket: ${response.status}`);
    }

    return response.json();
  }

  // 파일 삭제
  async deleteFile(userId: string, fileId: string): Promise<boolean> {
    const response = await fetch(`${this.baseURL}/user/${userId}/file/${fileId}`, {
      method: 'DELETE'
    });

    return response.ok;
  }
}

// 사용 예시
const api = new OrganizedFilesAPI();

// 파일 저장
try {
  const result = await api.saveFiles('621c7d3957c2ea5b9063d04c', '/Users/jun/project', [
    {
      originalRelativePath: 'src/App.tsx',
      directory: false,
      development: true,
      sizeBytes: 2048,
      modifiedAt: new Date().toISOString(),
      keywords: ['React', 'App'],
      koreanFileName: '앱 메인.tsx',
      englishFileName: 'App Main.tsx',
      paraBucket: 'Projects',
      paraFolder: 'frontend',
      reason: 'Main application component'
    }
  ]);
  
  console.log(`${result.savedCount} files saved, ${result.updatedCount} files updated`);
} catch (error) {
  console.error('Error saving files:', error);
}
```

### Vue.js 예시

```javascript
// Composable function
export function useOrganizedFiles() {
  const baseURL = '/api/organized-files';

  const saveFiles = async (userId, baseDirectory, files) => {
    const response = await $fetch(`${baseURL}/save`, {
      method: 'POST',
      body: {
        userId,
        baseDirectory,
        files
      }
    });
    return response;
  };

  const getStats = async (userId) => {
    return await $fetch(`${baseURL}/user/${userId}/stats`);
  };

  const getFilesByBucket = async (userId, bucket) => {
    return await $fetch(`${baseURL}/user/${userId}/bucket/${bucket}`);
  };

  return {
    saveFiles,
    getStats,
    getFilesByBucket
  };
}
```

## 중요 참고사항

### 1. PARA 버킷 이름
- 정확한 대소문자 구분: `Projects`, `Areas`, `Resources`, `Archive`
- 다른 이름 사용시 검증 에러 발생

### 2. userId 형식
- MongoDB ObjectId 형식 (24자 16진수 문자열)
- 예: `621c7d3957c2ea5b9063d04c`

### 3. 날짜 형식
- ISO 8601 형식 사용: `2024-01-16T14:30:00Z`
- JavaScript: `new Date().toISOString()`

### 4. 중복 처리 로직
- `originalRelativePath`를 기준으로 중복 판단
- 기존 파일 존재시 자동으로 업데이트 수행
- `id` 필드는 업데이트시 무시됨 (자동으로 기존 ID 사용)

### 5. 에러 복구
- 배치 처리시 개별 파일 실패가 전체 처리를 중단시키지 않음
- `errorMessages` 배열에서 실패한 파일들의 에러 확인 가능

이 API를 사용하여 PARA 방법론에 따른 파일 관리 시스템을 구축할 수 있습니다. 추가 질문이나 기능 요청이 있으면 언제든 문의해 주세요! 🚀