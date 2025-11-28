"""파일 정리 및 Spring 서버 연동 라우터"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.schemas.folder import FolderSelectionRequest
from app.services.folder_inspection import (
    DirectoryInspectionError,
    inspect_directory_with_keywords,
    to_organized_file_entry,
    to_file_entry_for_generation,
)
from app.services.organized_file_client import (
    OrganizedFileClient,
    OrganizedFileClientError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["organized-files"])


@router.post("/folders/inspect-and-organize")
async def inspect_and_organize_folder(
    payload: FolderSelectionRequest,
    page_size: int = 100,
) -> JSONResponse:
    """
    폴더를 검사하고 파일에서 키워드를 추출한 후 Spring 서버로 전달

    페이징을 지원하여 대용량 폴더도 처리 가능

    Steps:
    1. 폴더 경로 검증
    2. 파일 수집 및 ML 키워드 추출
    3. 페이지별로 Spring 서버로 전송
    4. 결과 반환

    Request:
    {
        "path": "/Users/jun/Documents/MyFolder"
    }

    Query Parameters:
    - page_size: 한 번에 전송할 파일 수 (기본값: 100, 최대: 500)

    Response (200):
    {
        "status": "success",
        "message": "파일이 Spring 서버로 전달되었습니다",
        "directory": "/Users/jun/Documents/MyFolder",
        "totalFiles": 250,
        "totalPages": 3,
        "pageSize": 100,
        "savedCount": 240,
        "updatedCount": 10,
        "failedCount": 0
    }

    Response (400/500):
    {
        "status": "error",
        "message": "에러 메시지"
    }
    """
    try:
        # 페이지 크기 검증 (최대 500)
        if page_size < 10 or page_size > 500:
            page_size = 100

        logger.info(f"폴더 검사 및 정리 시작: {payload.path} (페이지 크기: {page_size})")

        # 1. 폴더 경로 검증 및 파일 수집 (키워드 추출 포함)
        folder_response, entries_with_keywords = (
            await inspect_directory_with_keywords(payload.path)
        )

        total_files = len(entries_with_keywords)
        logger.info(f"파일 수집 완료: {total_files}개 파일")

        # 2. DirectoryEntry를 OrganizedFileEntry로 변환
        directory_root = Path(folder_response.directory)
        user_id = "621c7d3957c2ea5b9063d04c"  # TODO: 실제 사용자 ID 사용

        organized_entries = [
            to_organized_file_entry(
                directory_root=directory_root,
                entry=entry,
                user_id=user_id,
            )
            for entry in entries_with_keywords
        ]

        logger.info(
            f"OrganizedFileEntry 변환 완료: "
            f"{len(organized_entries)}개 항목"
        )

        # 3. 페이징: 파일을 page_size씩 나누어 전송
        total_saved = 0
        total_updated = 0
        total_failed = 0
        all_error_messages = []

        spring_client = OrganizedFileClient()

        # 페이지 수 계산
        total_pages = (total_files + page_size - 1) // page_size

        for page_num in range(total_pages):
            start_idx = page_num * page_size
            end_idx = min((page_num + 1) * page_size, total_files)
            page_entries = organized_entries[start_idx:end_idx]

            logger.info(
                f"Spring 서버로 페이지 전송: "
                f"페이지 {page_num + 1}/{total_pages} "
                f"({len(page_entries)}개 파일)"
            )

            try:
                spring_response = await spring_client.save_files(
                    user_id=user_id,
                    base_directory=str(directory_root),
                    files=page_entries,
                )

                total_saved += spring_response.saved_count
                total_updated += spring_response.updated_count
                total_failed += spring_response.failed_count
                all_error_messages.extend(spring_response.error_messages)

                logger.info(
                    f"페이지 {page_num + 1} 전송 완료: "
                    f"{spring_response.saved_count} 저장, "
                    f"{spring_response.updated_count} 업데이트, "
                    f"{spring_response.failed_count} 실패"
                )
            except OrganizedFileClientError as exc:
                logger.error(f"페이지 {page_num + 1} 전송 실패: {exc}")
                # 한 페이지 실패해도 계속 진행
                total_failed += len(page_entries)
                all_error_messages.append(f"페이지 {page_num + 1} 전송 실패: {str(exc)}")
                continue

        logger.info(
            f"모든 페이지 전송 완료: "
            f"{total_saved} 저장, "
            f"{total_updated} 업데이트, "
            f"{total_failed} 실패"
        )

        # 4. 결과 반환
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "파일이 Spring 서버로 전달되었습니다",
                "directory": str(directory_root),
                "totalFiles": total_files,
                "totalPages": total_pages,
                "pageSize": page_size,
                "savedCount": total_saved,
                "updatedCount": total_updated,
                "failedCount": total_failed,
                "errorMessages": all_error_messages,
            },
        )

    except DirectoryInspectionError as exc:
        logger.error(f"폴더 검사 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except OrganizedFileClientError as exc:
        logger.error(f"Spring 서버 전송 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spring 서버 연동 실패: {str(exc)}",
        )

    except Exception as exc:
        logger.exception(f"예상치 못한 에러: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파일 정리 중 에러가 발생했습니다",
        )


@router.post("/folders/inspect-and-organize/batch")
async def inspect_and_organize_batch(
    payload: FolderSelectionRequest,
) -> JSONResponse:
    """
    폴더를 검사하고 배치 단위로 Spring 서버로 전달 (대용량 파일 처리용)

    배치 크기: 50개 파일씩

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
        "totalBatches": 10
    }
    """
    try:
        logger.info(f"배치 폴더 검사 시작: {payload.path}")

        # 1. 폴더 경로 검증 및 파일 수집
        folder_response, entries_with_keywords = (
            await inspect_directory_with_keywords(payload.path)
        )

        total_files = len(entries_with_keywords)
        batch_size = 50

        # 2. 배치 생성
        batches = [
            entries_with_keywords[i : i + batch_size]
            for i in range(0, total_files, batch_size)
        ]

        logger.info(
            f"배치 생성 완료: {len(batches)}개 배치 "
            f"(배치 크기: {batch_size})"
        )

        # 3. 백그라운드 작업으로 배치 처리
        import asyncio

        asyncio.create_task(
            _process_batches_in_background(
                batches=batches,
                directory_root=Path(folder_response.directory),
            )
        )

        # 4. 즉시 응답
        return JSONResponse(
            status_code=202,  # Accepted
            content={
                "status": "processing",
                "message": "배치 처리가 시작되었습니다",
                "directory": str(folder_response.directory),
                "totalFiles": total_files,
                "totalBatches": len(batches),
                "batchSize": batch_size,
            },
        )

    except DirectoryInspectionError as exc:
        logger.error(f"폴더 검사 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception(f"예상치 못한 에러: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="배치 처리 중 에러가 발생했습니다",
        )


async def _process_batches_in_background(
    batches: list[list],
    directory_root: Path,
) -> None:
    """백그라운드에서 배치를 순차적으로 처리"""
    user_id = "621c7d3957c2ea5b9063d04c"  # TODO: 실제 사용자 ID 사용
    spring_client = OrganizedFileClient()

    for batch_num, batch_entries in enumerate(batches, start=1):
        try:
            logger.info(
                f"배치 {batch_num}/{len(batches)} 처리 중... "
                f"({len(batch_entries)}개 파일)"
            )

            # 배치의 파일들을 OrganizedFileEntry로 변환
            organized_entries = [
                to_organized_file_entry(
                    directory_root=directory_root,
                    entry=entry,
                    user_id=user_id,
                )
                for entry in batch_entries
            ]

            # Spring 서버로 전송
            response = await spring_client.save_files(
                user_id=user_id,
                base_directory=str(directory_root),
                files=organized_entries,
            )

            logger.info(
                f"배치 {batch_num} 완료: "
                f"{response.saved_count} 저장, "
                f"{response.updated_count} 업데이트, "
                f"{response.failed_count} 실패"
            )

        except OrganizedFileClientError as exc:
            logger.error(f"배치 {batch_num} 전송 실패: {exc}")
            # 다음 배치 계속 처리
            continue

        except Exception as exc:
            logger.exception(f"배치 {batch_num} 처리 중 에러: {exc}")
            # 다음 배치 계속 처리
            continue

    logger.info("모든 배치 처리 완료")


@router.post("/folders/inspect-and-organize-with-generation")
async def inspect_and_organize_with_generation(
    payload: FolderSelectionRequest,
    page_size: int = 100,
) -> JSONResponse:
    """
    폴더를 검사하고 새로운 Generation 포맷으로 Spring 서버로 전달

    새로운 DTO 구조를 사용하여 AI 기반 파일 정리를 수행합니다.

    Steps:
    1. 폴더 경로 검증
    2. 파일 수집 및 ML 키워드 추출
    3. FileEntryForGeneration 포맷으로 변환
    4. 페이지별로 Spring 서버로 전송
    5. 결과 반환

    Request:
    {
        "path": "/Users/jun/Documents/MyFolder"
    }

    Query Parameters:
    - page_size: 한 번에 전송할 파일 수 (기본값: 100, 최대: 500)

    Response (200):
    {
        "status": "success",
        "message": "파일이 Spring 서버로 전달되었습니다",
        "directory": "/Users/jun/Documents/MyFolder",
        "totalFiles": 250,
        "totalPages": 3,
        "pageSize": 100,
        "savedCount": 240,
        "updatedCount": 10,
        "failedCount": 0
    }
    """
    try:
        # 페이지 크기 검증 (최대 500)
        if page_size < 10 or page_size > 500:
            page_size = 100

        logger.info(
            f"Generation 포맷 폴더 검사 시작: {payload.path} "
            f"(페이지 크기: {page_size})"
        )

        # 1. 폴더 경로 검증 및 파일 수집 (키워드 추출 포함)
        folder_response, entries_with_keywords = (
            await inspect_directory_with_keywords(payload.path)
        )

        total_files = len(entries_with_keywords)
        logger.info(f"파일 수집 완료: {total_files}개 파일")

        # 2. DirectoryEntry를 FileEntryForGeneration으로 변환
        directory_root = Path(folder_response.directory)
        user_id = "621c7d3957c2ea5b9063d04c"  # TODO: 실제 사용자 ID 사용

        generation_entries = [
            to_file_entry_for_generation(
                directory_root=directory_root,
                entry=entry,
            )
            for entry in entries_with_keywords
        ]

        logger.info(
            f"FileEntryForGeneration 변환 완료: "
            f"{len(generation_entries)}개 항목"
        )

        # 3. 페이징: 파일을 page_size씩 나누어 전송
        total_saved = 0
        total_updated = 0
        total_failed = 0
        all_error_messages = []

        spring_client = OrganizedFileClient()

        # 페이지 수 계산
        total_pages = (total_files + page_size - 1) // page_size

        for page_num in range(total_pages):
            start_idx = page_num * page_size
            end_idx = min((page_num + 1) * page_size, total_files)
            page_entries = generation_entries[start_idx:end_idx]

            logger.info(
                f"Spring 서버로 Generation 페이지 전송: "
                f"페이지 {page_num + 1}/{total_pages} "
                f"({len(page_entries)}개 파일)"
            )

            try:
                spring_response = await spring_client.save_files_with_generation(
                    user_id=user_id,
                    base_directory=str(directory_root),
                    files=page_entries,
                )

                total_saved += spring_response.saved_count
                total_updated += spring_response.updated_count
                total_failed += spring_response.failed_count
                all_error_messages.extend(spring_response.error_messages)

                logger.info(
                    f"Generation 페이지 {page_num + 1} 전송 완료: "
                    f"{spring_response.saved_count} 저장, "
                    f"{spring_response.updated_count} 업데이트, "
                    f"{spring_response.failed_count} 실패"
                )
            except OrganizedFileClientError as exc:
                logger.error(f"Generation 페이지 {page_num + 1} 전송 실패: {exc}")
                # 한 페이지 실패해도 계속 진행
                total_failed += len(page_entries)
                all_error_messages.append(
                    f"Generation 페이지 {page_num + 1} 전송 실패: {str(exc)}"
                )
                continue

        logger.info(
            f"모든 Generation 페이지 전송 완료: "
            f"{total_saved} 저장, "
            f"{total_updated} 업데이트, "
            f"{total_failed} 실패"
        )

        # 4. 결과 반환
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "파일이 Spring 서버로 전달되었습니다",
                "directory": str(directory_root),
                "totalFiles": total_files,
                "totalPages": total_pages,
                "pageSize": page_size,
                "savedCount": total_saved,
                "updatedCount": total_updated,
                "failedCount": total_failed,
                "errorMessages": all_error_messages,
            },
        )

    except DirectoryInspectionError as exc:
        logger.error(f"폴더 검사 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except OrganizedFileClientError as exc:
        logger.error(f"Spring 서버 전송 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spring 서버 연동 실패: {str(exc)}",
        )

    except Exception as exc:
        logger.exception(f"예상치 못한 에러: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파일 정리 중 에러가 발생했습니다",
        )
