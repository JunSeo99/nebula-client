"""Launch the full Nebula client stack (API, Next.js, PyWebView)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import Iterable, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_HOST = os.getenv("HOST", "127.0.0.1")
DEFAULT_API_PORT = int(os.getenv("PORT", "8000"))
DEFAULT_NEXT_HOST = os.getenv("NEXT_HOST", "127.0.0.1")
DEFAULT_NEXT_PORT = int(os.getenv("NEXT_PORT", "3000"))


class ProcessManager:
    """Track spawned subprocesses and ensure graceful shutdown."""

    def __init__(self) -> None:
        self._processes: list[subprocess.Popen[bytes]] = []

    def spawn(self, args: Iterable[str], *, cwd: Optional[Path] = None) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            list(args),
            cwd=str(cwd) if cwd else None,
            stdout=None,  # 부모 프로세스 stdout으로 리다이렉트
            stderr=None,  # 부모 프로세스 stderr로 리다이렉트
        )
        self._processes.append(process)
        return process

    def terminate_all(self) -> None:
        for process in self._processes:
            with suppress(ProcessLookupError):
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)

        deadline = time.monotonic() + 10
        for process in self._processes:
            if process.poll() is not None:
                continue
            remaining = deadline - time.monotonic()
            if remaining > 0:
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=remaining)
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    process.kill()


def ensure_directory(path_value: str, *, description: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{description} '{path}' does not exist")
    if not path.is_dir():
        raise NotADirectoryError(f"{description} '{path}' must be a directory")
    return path


def wait_for_http(url: str, *, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    last_error: Optional[Exception] = None

    with httpx.Client(follow_redirects=True) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(url, timeout=2)
            except Exception as exc:  # pragma: no cover - diagnostics only
                last_error = exc
                time.sleep(1)
                continue

            if response.status_code < 500:
                return

            last_error = RuntimeError(f"Unexpected status {response.status_code}")
            time.sleep(1)

    raise TimeoutError(f"Timed out waiting for {url}") from last_error


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    client_path_value = os.getenv("CLIENT_PATH")
    if not client_path_value:
        raise EnvironmentError("CLIENT_PATH environment variable is required")

    client_path = ensure_directory(client_path_value, description="CLIENT_PATH")

    process_manager = ProcessManager()

    try:
        import webview  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        webview = None

    api_cmd: List[str] = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        DEFAULT_API_HOST,
        "--port",
        str(DEFAULT_API_PORT),
        "--reload",
    ]

    next_cmd: List[str] = [
        "npm",
        "run",
        "dev",
    ]

    print("Starting FastAPI backend...")
    process_manager.spawn(api_cmd, cwd=project_root)
    wait_for_http(f"http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}/health")
    print("FastAPI is ready.")

    print("Starting Next.js frontend...")
    process_manager.spawn(next_cmd, cwd=client_path)
    wait_for_http(f"http://{DEFAULT_NEXT_HOST}:{DEFAULT_NEXT_PORT}")
    print("Next.js is ready.")

    window_url = f"http://{DEFAULT_NEXT_HOST}:{DEFAULT_NEXT_PORT}/file-manager"

    try:
        if webview is not None:
            print("Launching PyWebView...")
            window = webview.create_window("Nebula", window_url, width=1400, height=900)
            webview.start(debug=False)
        else:
            print("pywebview not installed. Opening in default browser instead.")
            webbrowser.open(window_url)
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down child processes...")
        process_manager.terminate_all()


if __name__ == "__main__":
    main()
