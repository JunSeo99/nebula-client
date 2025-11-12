# nebula-client
[Nebula] Fast API

## 개발 환경 세팅

1) 가상환경 생성 및 활성화

```bash
/usr/bin/python3 -m venv .venv
source .venv/bin/activate
```

2) 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3) 개발 서버 실행

```bash
uvicorn app.main:app --reload
```

4) 헬스체크

```bash
curl http://127.0.0.1:8000/health
```

## 풀 스택 실행 (FastAPI + Next.js + PyWebView)

1) `.env` 또는 셸에 프론트엔드 경로를 지정합니다.

```bash
export CLIENT_PATH=/Users/jun/project/nebula-frontend
```

2) PyWebView를 아직 설치하지 않았다면 별도로 설치합니다.

```bash
pip install pywebview
```

3) 모든 서비스를 순차적으로 실행합니다.

```bash
python -m app.cli.run_stack
```

스크립트는 FastAPI 서버와 Next.js 개발 서버가 준비될 때까지 대기한 뒤 PyWebView 창을 띄웁니다. PyWebView 설치에 실패했다면 기본 브라우저가 대신 열리며, 터미널에서 `Ctrl+C`로 두 서버를 종료할 수 있습니다.
