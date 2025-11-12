# Spring 연동 구현 체크리스트

## Phase 1: 기초 설정 (1주)

### 1.1 의존성 추가
- [ ] `httpx` (이미 설치됨) 확인
- [ ] `aio-pika` 설치 (RabbitMQ용, 옵션)
- [ ] `tenacity` 설치 (재시도 로직)
- [ ] `pydantic-settings` 설치 (환경 변수 관리)

```bash
pip install tenacity pydantic-settings
```

### 1.2 파일 구조 생성
```
app/
├── routers/
│   └── organization.py          # 새로 생성
├── schemas/
│   └── organization.py          # 새로 생성
├── services/
│   ├── spring_integration.py     # 새로 생성
│   └── ml_extraction.py          # 새로 생성
└── middleware/
    └── logging.py               # 새로 생성
```

### 1.3 환경 변수 설정
- [ ] `.env.example` 업데이트
- [ ] `.env` 파일에 Spring 서버 정보 입력
- [ ] API 키 생성 (Spring 서버에서)

```bash
# .env.example에 추가
SPRING_SERVER_URL=http://localhost:8080
SPRING_API_KEY=your-secure-api-key
REDIS_URL=redis://localhost:6379
```

---

## Phase 2: Spring 연동 기본 (1주)

### 2.1 Schemas 구현
**파일**: `app/schemas/organization.py`

- [ ] `OrganizationStrategy` Enum 정의
- [ ] `FileEntry` 모델 정의
- [ ] `SnapshotBatchRequest` 모델 정의
- [ ] `SnapshotBatchResponse` 모델 정의
- [ ] `OrganizationRequest` 모델 정의

**테스트**:
```bash
pytest tests/test_schemas_organization.py -v
```

### 2.2 Spring 클라이언트 구현
**파일**: `app/services/spring_integration.py`

- [ ] `SpringIntegrationError` 예외 정의
- [ ] `SpringClient` 클래스 구현
  - [ ] `__init__` 메서드
  - [ ] `_build_headers` 메서드
  - [ ] `send_snapshot_batch` 메서드 (재시도 로직 포함)
  - [ ] `get_task_status` 메서드
  - [ ] `get_organization_result` 메서드
  - [ ] `report_execution_result` 메서드

**테스트**:
```bash
pytest tests/test_spring_integration.py -v
```

### 2.3 ML 추출 서비스 개선
**파일**: `app/services/ml_extraction.py` (새로 생성)

- [ ] 기존 추출 함수들을 통합
- [ ] 병렬 처리 지원 (asyncio)
- [ ] 에러 로깅 추가

---

## Phase 3: API 라우터 구현 (1주)

### 3.1 조직화 라우터 구현
**파일**: `app/routers/organization.py`

- [ ] `POST /api/organize` 엔드포인트
  - [ ] 경로 검증
  - [ ] 파일 수집
  - [ ] 메타데이터 추출
  - [ ] 배치 생성
  - [ ] Spring 전송 (백그라운드)

- [ ] `GET /api/organize/{task_id}` 엔드포인트
  - [ ] 로컬 상태 조회
  - [ ] Spring 상태 조회

- [ ] `POST /api/reorganize/execute` 엔드포인트
  - [ ] Spring 콜백 처리
  - [ ] 파일 이동 실행
  - [ ] 에러 처리

**테스트**:
```bash
pytest tests/test_routers_organization.py -v
```

### 3.2 main.py 업데이트
- [ ] 라우터 등록
- [ ] 미들웨어 추가
- [ ] 의존성 주입 설정

### 3.3 헬퍼 함수 구현
- [ ] `_collect_and_extract_files`
- [ ] `_get_file_type`
- [ ] `_chunk_files`
- [ ] `_get_batch_size`
- [ ] `_send_batches_to_spring`

---

## Phase 4: 고급 기능 (2주)

### 4.1 비동기 백그라운드 작업
- [ ] Celery + Redis 설정
- [ ] 작업 큐 구현
- [ ] 진행 상황 추적

**파일**: `app/tasks/extraction.py` (새로 생성)

```python
from celery import Celery

celery_app = Celery('nebula')

@celery_app.task
def extract_file_insights(file_path: str):
    # ML 추출 로직
    pass
```

### 4.2 메시지 큐 통합 (선택사항)
**파일**: `app/services/message_queue.py`

- [ ] `MessagePublisher` 추상 클래스
- [ ] `RabbitMQPublisher` 구현
- [ ] 이벤트 발행

### 4.3 비용 관리 시스템
**파일**: `app/services/cost_manager.py` (새로 생성)

- [ ] OpenAI API 비용 계산
- [ ] 예산 제한 체크
- [ ] 비용 로깅

### 4.4 재시도 정책
**파일**: `app/services/retry_policy.py` (새로 생성)

- [ ] 지수 백오프 구현
- [ ] 최대 재시도 횟수 설정
- [ ] 타임아웃 처리

---

## Phase 5: 테스트 (1주)

### 5.1 단위 테스트
- [ ] `tests/test_schemas_organization.py`
  - [ ] FileEntry 검증
  - [ ] SnapshotBatchRequest 검증

- [ ] `tests/test_spring_integration.py`
  - [ ] 성공 케이스
  - [ ] 네트워크 에러
  - [ ] 재시도 로직
  - [ ] 타임아웃

- [ ] `tests/test_routers_organization.py`
  - [ ] POST /api/organize 성공
  - [ ] GET /api/organize/{task_id}
  - [ ] 경로 검증 실패
  - [ ] 파일 수집 실패

### 5.2 통합 테스트
- [ ] Spring 서버 Mock 생성
- [ ] 엔드-투-엔드 시나리오
- [ ] 배치 전송 흐름
- [ ] 상태 조회 흐름

### 5.3 성능 테스트
- [ ] 1000개 파일 처리
- [ ] 동시 요청 처리
- [ ] 메모리 사용량 확인
- [ ] 배치 전송 시간

---

## Phase 6: 배포 준비 (1주)

### 6.1 로깅 및 모니터링
- [ ] Structured logging 구현
- [ ] 요청/응답 로깅
- [ ] 에러 추적 (Sentry 통합, 선택사항)

**파일**: `app/middleware/logging.py`

### 6.2 문서화
- [ ] API 문서 확인 (FastAPI Swagger)
- [ ] README.md 업데이트
- [ ] 환경 변수 문서화
- [ ] 트러블슈팅 가이드 작성

### 6.3 보안 점검
- [ ] API 키 검증
- [ ] 경로 검증
- [ ] 파일 접근 제어
- [ ] HTTPS 설정 (프로덕션)

### 6.4 Docker 설정
- [ ] `Dockerfile` 작성
- [ ] `docker-compose.yml` 작성
- [ ] 환경 변수 주입

---

## Phase 7: 프로덕션 배포 (1주)

### 7.1 환경 변수 검증
- [ ] Spring 서버 URL 확인
- [ ] API 키 안전 저장
- [ ] 데이터베이스 연결 확인

### 7.2 헬스 체크
- [ ] Spring 서버 연결 테스트
- [ ] 데이터베이스 연결 테스트
- [ ] Redis 연결 테스트 (사용시)

```python
@app.get("/health/spring")
async def health_spring(spring_client: SpringClient = Depends(get_spring_client)):
    try:
        await spring_client.get_task_status("test")
        return {"status": "ok"}
    except:
        return {"status": "error"}, 503
```

### 7.3 롤백 계획
- [ ] 버전 관리 전략
- [ ] 데이터베이스 마이그레이션 계획
- [ ] 롤백 스크립트 작성

### 7.4 모니터링
- [ ] 로그 수집 (ELK, Datadog 등)
- [ ] 메트릭 수집 (Prometheus)
- [ ] 알림 설정

---

## 구현 중 체크사항

### 코드 품질
```bash
# 린트 체크
flake8 app/

# 타입 체크
mypy app/

# 테스트 커버리지
pytest --cov=app tests/

# 코드 포매팅
black app/
```

### Git 커밋 메시지 가이드

```
feat: Spring 연동 기본 스키마 정의

- FileEntry, OrganizationStrategy 스키마 추가
- SnapshotBatchRequest/Response 모델 정의

Refs #123
```

### Pull Request 체크리스트
- [ ] 테스트 작성
- [ ] 문서 업데이트
- [ ] 코드 리뷰 요청
- [ ] CI 통과 확인

---

## 예상 일정

| Phase | 기간 | 주요 산출물 |
|-------|------|----------|
| 1 | 1주 | 프로젝트 구조, 환경 설정 |
| 2 | 1주 | Spring 클라이언트, 스키마 |
| 3 | 1주 | API 라우터, 배치 전송 |
| 4 | 2주 | Celery 통합, 비용 관리 |
| 5 | 1주 | 테스트 커버리지 >80% |
| 6 | 1주 | 문서, 보안, Docker |
| 7 | 1주 | 프로덕션 배포, 모니터링 |
| **합계** | **8주** | **프로덕션 준비 완료** |

---

## 위험 요소 및 대응

| 위험 | 영향 | 대응 방안 |
|------|------|----------|
| Spring 서버 다운 | 높음 | RabbitMQ를 통한 메시지 큐 분리 |
| OpenAI API 비용 초과 | 높음 | 배치 크기 동적 조정, 예산 제한 |
| 네트워크 지연 | 중간 | 재시도 로직, 타임아웃 설정 |
| 대용량 파일 처리 | 중간 | 스트리밍, 페이지네이션 |
| 권한 문제 | 낮음 | 에러 처리, 사용자 피드백 |

---

## 자주 묻는 질문

### Q: Spring 서버가 없으면?
A: Mock SpringClient를 만들어서 테스트할 수 있습니다.

### Q: 파일이 50개 이상이면?
A: 배치로 나눠서 순차 전송합니다. 병렬 처리는 추후 최적화.

### Q: 실패하면 어떻게?
A: 재시도 로직이 자동으로 처리합니다. 3회 실패시 로그에 기록됩니다.

### Q: 비용 관리는?
A: `max_cost_budget`으로 제한하고, 초과하면 요청을 거절합니다.

---

## 참고 자료

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Pydantic 문서](https://docs.pydantic.dev/)
- [httpx 문서](https://www.python-httpx.org/)
- [Tenacity 문서](https://tenacity.readthedocs.io/)

---

**작성자**: Claude Code
**최종 수정**: 2025-11-11
**버전**: 1.0
