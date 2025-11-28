"""스키마 for organized files to send to Spring server."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class ParaBucket(str, Enum):
    """PARA 방법론 버킷"""
    PROJECTS = "Projects"
    AREAS = "Areas"
    RESOURCES = "Resources"
    ARCHIVE = "Archive"


class FileEntryForGeneration(BaseModel):
    """Spring 서버로 전송할 파일 정보 (Generation용)"""

    relative_path: str = Field(
        ...,
        alias="relativePath",
        description="파일의 상대 경로"
    )
    absolute_path: str = Field(
        ...,
        alias="absolutePath",
        description="파일의 절대 경로"
    )
    is_directory: bool = Field(
        ...,
        alias="isDirectory",
        description="디렉토리 여부"
    )
    size_bytes: int = Field(
        ...,
        alias="sizeBytes",
        ge=0,
        description="파일 크기 (바이트)"
    )
    modified_at: str = Field(
        ...,
        alias="modifiedAt",
        description="수정 시간 (ISO 8601 형식)"
    )
    is_development: bool = Field(
        default=False,
        alias="isDevelopment",
        description="개발 관련 파일 여부"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="추출된 키워드 목록"
    )

    class Config:
        populate_by_name = True


class OrganizedFileEntry(BaseModel):
    """Spring 서버로 전송할 정리된 파일 정보 (이전 버전, 호환성용)"""

    original_relative_path: str = Field(
        ...,
        alias="originalRelativePath",
        description="원본 상대 경로 (필수)"
    )
    directory: bool = Field(
        ...,
        description="디렉토리 여부"
    )
    development: bool = Field(
        default=False,
        description="개발 관련 파일 여부"
    )
    size_bytes: int = Field(
        ...,
        alias="sizeBytes",
        ge=0,
        description="파일 크기 (바이트)"
    )
    modified_at: datetime = Field(
        ...,
        alias="modifiedAt",
        description="수정 시간 (ISO 8601 형식)"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="추출된 키워드 목록"
    )
    korean_file_name: str = Field(
        ...,
        alias="koreanFileName",
        description="한글 파일명"
    )
    english_file_name: str = Field(
        ...,
        alias="englishFileName",
        description="영문 파일명"
    )
    para_bucket: ParaBucket = Field(
        ...,
        alias="paraBucket",
        description="PARA 버킷 (Projects/Areas/Resources/Archive)"
    )
    para_folder: Optional[str] = Field(
        None,
        alias="paraFolder",
        description="하위 폴더명 (선택사항)"
    )
    reason: str = Field(
        ...,
        description="정리 이유"
    )

    class Config:
        populate_by_name = True  # alias 사용 허용


class OrganizedFileSaveWithGenerationRequest(BaseModel):
    """Spring 서버로 전송할 요청 (Generation용)"""

    user_id: str = Field(
        ...,
        alias="userId",
        description="사용자 ID (MongoDB ObjectId)"
    )
    base_directory: str = Field(
        ...,
        alias="baseDirectory",
        description="기본 디렉터리 경로"
    )
    files: List[FileEntryForGeneration] = Field(
        ...,
        description="처리할 파일 목록"
    )

    class Config:
        populate_by_name = True


class OrganizedFileSaveRequest(BaseModel):
    """Spring 서버로 전송할 요청 (이전 버전, 호환성용)"""

    user_id: str = Field(
        ...,
        alias="userId",
        description="사용자 ID (MongoDB ObjectId)"
    )
    base_directory: str = Field(
        ...,
        alias="baseDirectory",
        description="기본 디렉터리 경로"
    )
    files: List[OrganizedFileEntry] = Field(
        ...,
        description="저장할 파일 목록"
    )

    class Config:
        populate_by_name = True


class SavedFile(BaseModel):
    """Spring 서버 응답 - 저장된 파일 정보"""

    id: str
    original_relative_path: str = Field(alias="originalRelativePath")
    korean_file_name: str = Field(alias="koreanFileName")
    english_file_name: str = Field(alias="englishFileName")
    para_bucket: str = Field(alias="paraBucket")
    para_folder: Optional[str] = Field(None, alias="paraFolder")
    operation: str  # 'CREATED' | 'UPDATED'

    class Config:
        populate_by_name = True


class OrganizedFileSaveResponse(BaseModel):
    """Spring 서버 응답"""

    total_processed: int = Field(alias="totalProcessed")
    saved_count: int = Field(alias="savedCount")
    updated_count: int = Field(alias="updatedCount")
    failed_count: int = Field(alias="failedCount")
    error_messages: List[str] = Field(alias="errorMessages")
    saved_files: List[SavedFile] = Field(alias="savedFiles")
    processed_at: datetime = Field(alias="processedAt")

    class Config:
        populate_by_name = True


class FileStats(BaseModel):
    """파일 통계"""

    total_files: int = Field(alias="totalFiles")
    projects_count: int = Field(alias="projectsCount")
    areas_count: int = Field(alias="areasCount")
    resources_count: int = Field(alias="resourcesCount")
    archive_count: int = Field(alias="archiveCount")
    development_count: int = Field(alias="developmentCount")

    class Config:
        populate_by_name = True
