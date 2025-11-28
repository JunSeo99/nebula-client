"""정리된 파일 및 Spring 연동 테스트"""

import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.schemas.organized_file import (
    OrganizedFileEntry,
    ParaBucket,
)
from app.services.folder_inspection import (
    to_organized_file_entry,
    DirectoryEntry,
)
from app.services.organized_file_client import (
    OrganizedFileClient,
    OrganizedFileClientError,
)


class TestOrganizedFileEntry:
    """OrganizedFileEntry 스키마 테스트"""

    def test_create_entry_with_keywords(self):
        """키워드를 포함한 항목 생성"""
        entry = OrganizedFileEntry(
            original_relative_path="src/main.py",
            directory=False,
            development=True,
            size_bytes=1024,
            modified_at=datetime.now(timezone.utc),
            keywords=["Python", "Main", "Entry"],
            korean_file_name="메인 파일.py",
            english_file_name="main.py",
            para_bucket=ParaBucket.PROJECTS,
            reason="Main project file",
        )

        assert entry.original_relative_path == "src/main.py"
        assert entry.keywords == ["Python", "Main", "Entry"]
        assert entry.para_bucket == ParaBucket.PROJECTS


class TestToOrganizedFileEntry:
    """DirectoryEntry → OrganizedFileEntry 변환 테스트"""

    def test_convert_development_file(self):
        """개발 파일 변환"""
        # DirectoryEntry 생성
        entry = DirectoryEntry(
            name="package.json",
            path=Path("/project/package.json"),
            is_directory=False,
            size_bytes=512,
            modified_at=datetime.now(timezone.utc),
            keywords=["dependencies", "npm"],
            is_development=True,
        )

        # 변환
        organized = to_organized_file_entry(
            directory_root=Path("/project"),
            entry=entry,
            user_id="test_user",
        )

        # 검증
        assert organized.original_relative_path == "package.json"
        assert organized.development is True
        assert organized.para_bucket == ParaBucket.PROJECTS
        assert organized.keywords == ["dependencies", "npm"]

    def test_convert_resource_file(self):
        """리소스 파일 변환"""
        entry = DirectoryEntry(
            name="guide.md",
            path=Path("/project/docs/guide.md"),
            is_directory=False,
            size_bytes=2048,
            modified_at=datetime.now(timezone.utc),
            keywords=["Guide", "Documentation"],
            is_development=False,
        )

        organized = to_organized_file_entry(
            directory_root=Path("/project"),
            entry=entry,
            user_id="test_user",
        )

        assert organized.original_relative_path == "docs/guide.md"
        assert organized.development is False
        assert organized.para_bucket == ParaBucket.RESOURCES
        assert "Documentation" in organized.keywords

    def test_convert_archive_file(self):
        """보관 파일 변환 (키워드 없음)"""
        entry = DirectoryEntry(
            name="old_backup.zip",
            path=Path("/project/old_backup.zip"),
            is_directory=False,
            size_bytes=5000,
            modified_at=datetime.now(timezone.utc),
            keywords=[],
            is_development=False,
        )

        organized = to_organized_file_entry(
            directory_root=Path("/project"),
            entry=entry,
            user_id="test_user",
        )

        assert organized.para_bucket == ParaBucket.ARCHIVE


class TestOrganizedFileClient:
    """Spring 클라이언트 테스트"""

    @pytest.mark.asyncio
    async def test_client_initialization_with_url(self):
        """클라이언트 초기화 (URL 직접 지정)"""
        client = OrganizedFileClient(base_url="http://localhost:8080")
        assert client.base_url == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_client_initialization_without_url(self):
        """클라이언트 초기화 실패 (URL 없음)"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(OrganizedFileClientError):
                OrganizedFileClient(base_url=None)

    @pytest.mark.asyncio
    async def test_save_files_success(self):
        """파일 저장 성공"""
        client = OrganizedFileClient(base_url="http://localhost:8080")

        # Mock httpx.post
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "totalProcessed": 1,
                "savedCount": 1,
                "updatedCount": 0,
                "failedCount": 0,
                "errorMessages": [],
                "savedFiles": [
                    {
                        "id": "mongodb_id",
                        "originalRelativePath": "test.txt",
                        "koreanFileName": "테스트.txt",
                        "englishFileName": "test.txt",
                        "paraBucket": "Resources",
                        "paraFolder": None,
                        "operation": "CREATED",
                    }
                ],
                "processedAt": "2025-11-18T12:00:00Z",
            }
            mock_post.return_value = mock_response

            # 테스트 실행
            entry = OrganizedFileEntry(
                original_relative_path="test.txt",
                directory=False,
                development=False,
                size_bytes=100,
                modified_at=datetime.now(timezone.utc),
                keywords=["test"],
                korean_file_name="테스트.txt",
                english_file_name="test.txt",
                para_bucket=ParaBucket.RESOURCES,
                reason="Test file",
            )

            response = await client.save_files(
                user_id="test_user",
                base_directory="/tmp",
                files=[entry],
            )

            # 검증
            assert response.saved_count == 1
            assert response.updated_count == 0
            assert len(response.saved_files) == 1

    @pytest.mark.asyncio
    async def test_save_files_timeout(self):
        """파일 저장 타임아웃"""
        client = OrganizedFileClient(
            base_url="http://localhost:8080",
            timeout=0.001,  # 매우 짧은 타임아웃
            max_retries=1,
        )

        with patch('httpx.AsyncClient.post') as mock_post:
            import httpx
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            entry = OrganizedFileEntry(
                original_relative_path="test.txt",
                directory=False,
                development=False,
                size_bytes=100,
                modified_at=datetime.now(timezone.utc),
                keywords=["test"],
                korean_file_name="테스트.txt",
                english_file_name="test.txt",
                para_bucket=ParaBucket.RESOURCES,
                reason="Test file",
            )

            with pytest.raises(OrganizedFileClientError):
                await client.save_files(
                    user_id="test_user",
                    base_directory="/tmp",
                    files=[entry],
                )

    @pytest.mark.asyncio
    async def test_get_user_stats(self):
        """사용자 통계 조회"""
        client = OrganizedFileClient(base_url="http://localhost:8080")

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "totalFiles": 10,
                "projectsCount": 2,
                "areasCount": 3,
                "resourcesCount": 4,
                "archiveCount": 1,
                "developmentCount": 5,
            }
            mock_get.return_value = mock_response

            stats = await client.get_user_stats("test_user")

            assert stats["totalFiles"] == 10
            assert stats["projectsCount"] == 2
            assert stats["areasCount"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
