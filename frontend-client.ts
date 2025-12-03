/**
 * Organized Files API 클라이언트
 *
 * 프론트엔드에서 FastAPI 서버의 organized files 엔드포인트를 호출하기 위한 클라이언트
 */

interface InspectAndOrganizeRequest {
  path: string;
}

interface OrganizedFilesResponse {
  status: "success" | "error";
  message: string;
  directory: string;
  totalFiles: number;
  savedCount: number;
  updatedCount: number;
  failedCount: number;
  errorMessages: string[];
}

interface BatchProcessResponse {
  status: "processing";
  message: string;
  directory: string;
  totalFiles: number;
  totalBatches: number;
  batchSize: number;
}

/**
 * 폴더를 검사하고 파일을 정리하며 Spring 서버로 전송 (페이징 지원)
 *
 * @param path - 검사할 폴더의 절대 경로
 * @param baseUrl - FastAPI 서버 URL (기본값: http://localhost:8000)
 * @param pageSize - 한 번에 처리할 파일 수 (기본값: 100, 범위: 10-500)
 * @returns 정리 결과
 *
 * @example
 * ```typescript
 * // 기본 사용 (100개씩 처리)
 * const result = await inspectAndOrganizeFolder('/Users/jun/Documents/MyFolder');
 * console.log(`${result.savedCount}개 파일 저장, ${result.updatedCount}개 업데이트`);
 *
 * // 커스텀 페이지 크기
 * const result = await inspectAndOrganizeFolder(
 *   '/Users/jun/Documents/LargeFolder',
 *   'http://localhost:8000',
 *   200  // 200개씩 처리
 * );
 * console.log(`총 ${result.totalPages}개 페이지 처리 완료`);
 * ```
 */
export async function inspectAndOrganizeFolder(
  path: string,
  baseUrl: string = "http://localhost:8000",
  pageSize: number = 100
): Promise<OrganizedFilesResponse & { totalPages?: number; pageSize?: number }> {
  // 페이지 크기 검증 (10-500)
  const validPageSize = Math.max(10, Math.min(pageSize, 500));

  const url = new URL(`${baseUrl}/api/folders/inspect-and-organize`);
  url.searchParams.append("page_size", validPageSize.toString());

  try {
    const response = await fetch(url.toString(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path } as InspectAndOrganizeRequest),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return (await response.json()) as OrganizedFilesResponse & {
      totalPages?: number;
      pageSize?: number;
    };
  } catch (error) {
    throw new Error(
      `파일 정리 요청 실패: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

/**
 * Generation 포맷으로 폴더를 검사하고 처리 (새로운 DTO 구조)
 *
 * @param path - 검사할 폴더의 절대 경로
 * @param baseUrl - FastAPI 서버 URL (기본값: http://localhost:8000)
 * @param pageSize - 한 번에 처리할 파일 수 (기본값: 100, 범위: 10-500)
 * @returns 정리 결과
 *
 * @example
 * ```typescript
 * const result = await inspectAndOrganizeWithGeneration(
 *   '/Users/jun/Documents/MyFolder'
 * );
 * console.log(`저장: ${result.savedCount}, 업데이트: ${result.updatedCount}`);
 * ```
 */
export async function inspectAndOrganizeWithGeneration(
  path: string,
  baseUrl: string = "http://localhost:8000",
  pageSize: number = 100
): Promise<OrganizedFilesResponse & { totalPages?: number; pageSize?: number }> {
  // 페이지 크기 검증 (10-500)
  const validPageSize = Math.max(10, Math.min(pageSize, 500));

  const url = new URL(`${baseUrl}/api/folders/inspect-and-organize-with-generation`);
  url.searchParams.append("page_size", validPageSize.toString());

  try {
    const response = await fetch(url.toString(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path } as InspectAndOrganizeRequest),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return (await response.json()) as OrganizedFilesResponse & {
      totalPages?: number;
      pageSize?: number;
    };
  } catch (error) {
    throw new Error(
      `파일 정리 요청 실패: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

/**
 * 대용량 폴더를 배치 단위로 처리
 *
 * @param path - 검사할 폴더의 절대 경로
 * @param baseUrl - FastAPI 서버 URL (기본값: http://localhost:8000)
 * @returns 배치 처리 시작 응답 (비동기 처리)
 *
 * @example
 * ```typescript
 * const result = await inspectAndOrganizeBatch('/Users/jun/Documents/LargeFolder');
 * console.log(`총 ${result.totalFiles}개 파일을 ${result.totalBatches}개 배치로 처리 중...`);
 * ```
 */
export async function inspectAndOrganizeBatch(
  path: string,
  baseUrl: string = "http://localhost:8000"
): Promise<BatchProcessResponse> {
  const url = `${baseUrl}/api/folders/inspect-and-organize/batch`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path } as InspectAndOrganizeRequest),
    });

    if (response.status !== 202 && !response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return (await response.json()) as BatchProcessResponse;
  } catch (error) {
    throw new Error(
      `배치 처리 요청 실패: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

/**
 * 사용자의 파일 통계 조회
 *
 * @param userId - 사용자 ID
 * @param baseUrl - FastAPI 서버 URL
 */
export async function getUserStats(
  userId: string,
  baseUrl: string = "http://localhost:8000"
): Promise<Record<string, any>> {
  const url = `${baseUrl}/api/organized-files/user/${userId}/stats`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    throw new Error(
      `통계 조회 실패: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

/**
 * PARA 버킷별 파일 조회
 *
 * @param userId - 사용자 ID
 * @param bucket - PARA 버킷 (Projects, Areas, Resources, Archive)
 * @param baseUrl - FastAPI 서버 URL
 */
export async function getFilesByBucket(
  userId: string,
  bucket: "Projects" | "Areas" | "Resources" | "Archive",
  baseUrl: string = "http://localhost:8000"
): Promise<Record<string, any>[]> {
  const url = `${baseUrl}/api/organized-files/user/${userId}/bucket/${bucket}`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    throw new Error(
      `파일 조회 실패: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}
