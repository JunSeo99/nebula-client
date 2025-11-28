"""Spring 서버의 Organized Files API 클라이언트"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

import httpx

from app.schemas.organized_file import (
    OrganizedFileEntry,
    OrganizedFileSaveRequest,
    OrganizedFileSaveResponse,
    FileEntryForGeneration,
    OrganizedFileSaveWithGenerationRequest,
)

logger = logging.getLogger(__name__)


class OrganizedFileClientError(Exception):
    """Organized Files API 클라이언트 에러"""
    pass


class OrganizedFileClient:
    """Spring 서버의 Organized Files API 클라이언트"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 600.0,
        max_retries: int = 3,
    ):
        """
        초기화

        Args:
            base_url: Spring 서버 URL (기본값: 환경변수 SPRING_SERVER_URL)
            timeout: 요청 타임아웃 (초)
            max_retries: 최대 재시도 횟수
        """
        self.base_url = (
            base_url
            or os.getenv("SPRING_SERVER_URL", os.getenv("SERVER_URL", "http://localhost:8080"))
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.base_url:
            raise OrganizedFileClientError(
                "SPRING_SERVER_URL 환경변수가 설정되지 않았습니다"
            )

    async def save_files(
        self,
        user_id: str,
        base_directory: str,
        files: List[OrganizedFileEntry],
    ) -> OrganizedFileSaveResponse:
        """
        정리된 파일들을 Spring 서버에 저장

        Args:
            user_id: 사용자 ID (MongoDB ObjectId)
            base_directory: 기본 디렉터리 경로
            files: 저장할 파일 목록

        Returns:
            저장 결과

        Raises:
            OrganizedFileClientError: API 호출 실패
        """
        url = f"{self.base_url}/api/organized-files/save"

        # 요청 본문 준비
        request_data = OrganizedFileSaveRequest(
            user_id=user_id,
            base_directory=base_directory,
            files=files,
        )

        logger.info(
            f"Spring 서버로 파일 저장 요청: user_id={user_id}, "
            f"file_count={len(files)}"
        )

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=request_data.model_dump(
                            by_alias=True,
                            exclude_none=True,
                            mode="json"
                        ),
                        timeout=self.timeout,
                    )

                if response.status_code == 200:
                    logger.info(
                        f"파일 저장 성공: {response.json()['savedCount']} 저장, "
                        f"{response.json()['updatedCount']} 업데이트"
                    )
                    return OrganizedFileSaveResponse(**response.json())

                elif response.status_code == 400:
                    error_data = response.json()
                    raise OrganizedFileClientError(
                        f"Bad Request: {error_data.get('error', 'Unknown error')}"
                    )

                elif response.status_code == 401:
                    raise OrganizedFileClientError("Unauthorized: 인증 실패")

                elif response.status_code == 500:
                    error_data = response.json()
                    logger.warning(
                        f"Spring 서버 에러 (500). "
                        f"재시도 {attempt + 1}/{self.max_retries}"
                    )
                    if attempt == self.max_retries - 1:
                        raise OrganizedFileClientError(
                            f"Server Error: {error_data.get('error', 'Unknown error')}"
                        )
                    continue

                else:
                    raise OrganizedFileClientError(
                        f"Unexpected status code: {response.status_code}"
                    )

            except httpx.TimeoutException as exc:
                logger.error(
                    f"Spring 서버 타임아웃 ({self.timeout}초). "
                    f"배치 처리 사용 권장"
                )
                raise OrganizedFileClientError(
                    f"Spring 서버 타임아웃 ({self.timeout}초). "
                    f"대량 파일 처리 시 배치 처리 사용 권장"
                ) from exc

            except httpx.RequestError as exc:
                logger.warning(
                    f"Spring 서버 연결 실패 "
                    f"(시도 {attempt + 1}/{self.max_retries})"
                )
                if attempt == self.max_retries - 1:
                    raise OrganizedFileClientError(
                        f"Spring 서버 연결 실패: {str(exc)}"
                    ) from exc
                continue

        raise OrganizedFileClientError(
            f"최대 재시도 횟수 초과 ({self.max_retries})"
        )

    async def save_files_with_generation(
        self,
        user_id: str,
        base_directory: str,
        files: List[FileEntryForGeneration],
    ) -> OrganizedFileSaveResponse:
        """
        Generation용 새로운 포맷으로 파일 저장 (AI 생성 기반)

        Args:
            user_id: 사용자 ID (MongoDB ObjectId)
            base_directory: 기본 디렉터리 경로
            files: 저장할 파일 목록 (FileEntryForGeneration)

        Returns:
            저장 결과

        Raises:
            OrganizedFileClientError: API 호출 실패
        """
        url = f"{self.base_url}/api/organized-files/save"

        # 요청 본문 준비
        request_data = OrganizedFileSaveWithGenerationRequest(
            user_id=user_id,
            base_directory=base_directory,
            files=files,
        )

        logger.info(
            f"Spring 서버로 파일 저장 요청 (Generation): user_id={user_id}, "
            f"file_count={len(files)}"
        )

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=request_data.model_dump(
                            by_alias=True,
                            exclude_none=True,
                            mode="json"
                        ),
                        timeout=self.timeout,
                    )

                if response.status_code == 200:
                    logger.info(
                        f"파일 저장 성공: {response.json()['savedCount']} 저장, "
                        f"{response.json()['updatedCount']} 업데이트"
                    )
                    return OrganizedFileSaveResponse(**response.json())

                elif response.status_code == 400:
                    error_data = response.json()
                    raise OrganizedFileClientError(
                        f"Bad Request: {error_data.get('error', 'Unknown error')}"
                    )

                elif response.status_code == 401:
                    raise OrganizedFileClientError("Unauthorized: 인증 실패")

                elif response.status_code == 500:
                    error_data = response.json()
                    logger.warning(
                        f"Spring 서버 에러 (500). "
                        f"재시도 {attempt + 1}/{self.max_retries}"
                    )
                    if attempt == self.max_retries - 1:
                        raise OrganizedFileClientError(
                            f"Server Error: {error_data.get('error', 'Unknown error')}"
                        )
                    continue

                else:
                    raise OrganizedFileClientError(
                        f"Unexpected status code: {response.status_code}"
                    )

            except httpx.TimeoutException as exc:
                logger.error(
                    f"Spring 서버 타임아웃 ({self.timeout}초). "
                    f"배치 처리 사용 권장"
                )
                raise OrganizedFileClientError(
                    f"Spring 서버 타임아웃 ({self.timeout}초). "
                    f"대량 파일 처리 시 배치 처리 사용 권장"
                ) from exc

            except httpx.RequestError as exc:
                logger.warning(
                    f"Spring 서버 연결 실패 "
                    f"(시도 {attempt + 1}/{self.max_retries})"
                )
                if attempt == self.max_retries - 1:
                    raise OrganizedFileClientError(
                        f"Spring 서버 연결 실패: {str(exc)}"
                    ) from exc
                continue

        raise OrganizedFileClientError(
            f"최대 재시도 횟수 초과 ({self.max_retries})"
        )

    async def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """
        사용자의 파일 통계 조회

        Args:
            user_id: 사용자 ID

        Returns:
            파일 통계

        Raises:
            OrganizedFileClientError: API 호출 실패
        """
        url = f"{self.base_url}/api/organized-files/user/{user_id}/stats"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                raise OrganizedFileClientError(
                    f"통계 조회 실패: {response.status_code}"
                )

        except httpx.RequestError as exc:
            raise OrganizedFileClientError(
                f"통계 조회 네트워크 에러: {str(exc)}"
            ) from exc

    async def get_files_by_bucket(
        self,
        user_id: str,
        bucket: str,
    ) -> List[dict[str, Any]]:
        """
        PARA 버킷별 파일 조회

        Args:
            user_id: 사용자 ID
            bucket: PARA 버킷 (Projects, Areas, Resources, Archive)

        Returns:
            파일 목록

        Raises:
            OrganizedFileClientError: API 호출 실패
        """
        url = (
            f"{self.base_url}/api/organized-files/user/{user_id}/bucket/{bucket}"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                raise OrganizedFileClientError(
                    f"파일 조회 실패: {response.status_code}"
                )

        except httpx.RequestError as exc:
            raise OrganizedFileClientError(
                f"파일 조회 네트워크 에러: {str(exc)}"
            ) from exc
