"""Schemas for folder selection and inspection APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FolderSelectionRequest(BaseModel):
    """Client-supplied directory path to inspect."""

    path: str = Field(
        ..., description="Absolute or user-resolved path to the directory to inspect."
    )


class FileInfo(BaseModel):
    """Metadata describing a single file or subdirectory."""

    name: str = Field(..., description="Base name of the entry.")
    path: str = Field(..., description="Absolute path to the entry on disk.")
    is_directory: bool = Field(..., description="Whether the entry is a directory.")
    size_bytes: int = Field(..., ge=0, description="Size in bytes (0 for directories).")
    modified_at: datetime = Field(..., description="Last modification timestamp in UTC.")


class FolderContentsResponse(BaseModel):
    """Aggregated directory listing details."""

    directory: str = Field(..., description="Normalized directory path that was inspected.")
    entries: list[FileInfo] = Field(
        default_factory=list,
        description="Immediate child files and directories ordered by name.",
    )


class FolderSnapshotRequest(BaseModel):
    """Parameters for generating a recursive directory snapshot."""

    path: str = Field(
        ..., description="Absolute or user-resolved path to the directory to snapshot."
    )
    page_size: Optional[int] = Field(
        None,
        gt=0,
        description=(
            "Optional page size for chunking large snapshots into multiple JSON files."
        ),
    )


class SnapshotPageInfo(BaseModel):
    """Metadata about a written snapshot JSON file."""

    page: int = Field(..., ge=1, description="1-based page index.")
    path: str = Field(..., description="Filesystem path to the generated JSON file.")
    entry_count: int = Field(..., ge=0, description="Number of directory entries in this page.")


class DevelopmentDirectoryInfo(BaseModel):
    """Directory detected as a development workspace and not traversed."""

    relative_path: str = Field(
        ...,
        description="Path to the directory relative to the snapshot root.",
    )
    absolute_path: str = Field(
        ...,
        description="Absolute filesystem path to the development directory.",
    )


class FolderSnapshotResponse(BaseModel):
    """Details about generated directory snapshots."""

    directory: str = Field(..., description="Normalized directory path that was snapshotted.")
    generated_at: datetime = Field(..., description="UTC timestamp when the snapshot was created.")
    total_entries: int = Field(..., ge=0, description="Total entries included across all pages.")
    page_size: Optional[int] = Field(
        None, description="Applied page size; null indicates a single-file snapshot."
    )
    page_count: int = Field(..., ge=1, description="Number of JSON files generated for this snapshot.")
    pages: list[SnapshotPageInfo] = Field(
        default_factory=list,
        description="Per-file metadata for the snapshot output.",
    )
    development_directories: list[DevelopmentDirectoryInfo] = Field(
        default_factory=list,
        description="Directories flagged as development workspaces during snapshot.",
    )
