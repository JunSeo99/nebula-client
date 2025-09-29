"""Transmit snapshot payloads to the remote Nebula server."""

from __future__ import annotations

import os
from typing import Any, Mapping

import httpx

from app.services.folder_inspection import DirectoryInspectionError


_SERVER_URL_ENV = "SERVER_URL"
_ENDPOINT_PATH = "/generate-filename"
_DEFAULT_TIMEOUT = 10.0


def send_snapshot_payload(payload: Mapping[str, Any]) -> None:
    """Send a snapshot page payload to the configured server.

    Raises:
        DirectoryInspectionError: When configuration is missing or the request fails.
    """

    print(payload)
    return
    base_url = os.getenv(_SERVER_URL_ENV)
    if not base_url:
        raise DirectoryInspectionError("SERVER_URL 환경 변수가 설정되지 않았습니다.")

    url = f"{base_url.rstrip('/')}{_ENDPOINT_PATH}"

    try:
        response = httpx.post(url, json=payload, timeout=_DEFAULT_TIMEOUT)
    except httpx.HTTPError as exc:
        raise DirectoryInspectionError("스냅샷 데이터를 서버로 전송하지 못했습니다.") from exc

    if response.status_code >= 400:
        raise DirectoryInspectionError(
            "스냅샷 전송 중 서버에서 오류를 반환했습니다."
        )
