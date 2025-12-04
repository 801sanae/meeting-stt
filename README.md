
# Meeting STT Web App

회의를 브라우저에서 녹음하고, Azure Speech/OpenAI 를 사용해 **STT + 요약**까지 한 번에 처리하는 웹 애플리케이션입니다.

좌측에는 회의 리스트(타임스탬프 기반)가, 우측에는 선택한 회의의 **STT 전체 텍스트 / 요약**이 탭으로 표시됩니다.

---

## Screenshots

> 실제 레이아웃 예시는 아래 스크린샷을 참고하세요.

![Meeting STT 메인 화면](app/static/img/ui_sample.png)

---

## 기술 스택

- **Backend**
  - Python 3.12
  - FastAPI
  - SQLAlchemy + PostgreSQL (Docker Compose)
  - Pydantic Settings (환경변수 관리)
  - Azure Speech Service (REST STT)
  - Azure OpenAI (Chat Completions 요약)

- **Frontend**
  - 순수 HTML + Tailwind CSS (CDN)
  - Vanilla JS (`MediaRecorder`, `getUserMedia`) 로 브라우저 녹음

---

## 주요 기능

- 브라우저에서 **녹음 시작 / 완료** 버튼으로 음성 녹음
- 서버로 업로드 후 Azure Speech 로 STT 처리
- STT 텍스트를 Azure OpenAI 에 보내 회의 요약 생성
- 결과를 PostgreSQL 에 저장하고 목록/상세 조회
- 좌측 네비에 회의 리스트, 우측에 STT/SUMMARY 탭으로 보기
- 각 회의 항목 우측의 **X 버튼**으로 기록 삭제

---

## 아키텍처 레이어

- **Router (`app/routers/meetings.py`)**
  - HTTP 엔드포인트 정의 (`/meetings/record`, `/meetings`, `/meetings/{id}` 등)
  - FastAPI DI 로 `MeetingService` 주입

- **Service (`app/service/meeting_service.py`)**
  - 비즈니스 로직
    - STT 호출 (`stt_service.transcribe`)
    - 요약 호출 (`summary_service.summarize_meeting`)
    - 빈 transcript 처리 문구 등
  - Repository 를 통해 DB 접근

- **Repository (`app/repository/meeting_respository.py`)**
  - 순수 SQLAlchemy CRUD (`Meeting` 모델 전담)
  - `create_meeting`, `list_meetings`, `get_meeting`, `delete_meeting`

- **DB & 모델**
  - `app/config/db.py` : 엔진, 세션, Base, `get_db`
  - `app/models/models.py` : `Meeting`, `SttUsage` ORM
  - `app/models/meeting.py` : Pydantic 응답 모델들

---

## 개발 환경 설정

1. **의존성 설치 (uv 사용 예시)**

```bash
uv sync
```

2. **PostgreSQL (Docker Compose)**

```bash
docker compose up -d
```

3. **환경 변수 설정**

- `.env.example` 를 참고해 `.env` 를 로컬에만 생성합니다.
- 이 파일은 git 에 커밋하지 않습니다. (이미 `.gitignore` 에 추가됨)

필수 변수 예시:

```env
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_SUMMARY=...
AZURE_OPENAI_API_VERSION=2024-05-01-preview

AZURE_SPEECH_ENDPOINT=...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=eastus
AZURE_SPEECH_LANGUAGE=ko-KR
USE_SPEECH_SERVICE=true

USE_WHISPER_API=false
WHISPER_API_BASE_URL=...
```

---

## 서버 실행 방법

프로젝트 루트에서:

```bash
uv run python main.py
```

실행 후 브라우저에서 `http://localhost:8000` 접속.

- 정적 프론트: `app/static/html/index.html`
  - Tailwind + 커스텀 CSS (`app/static/css/main.css`)
  - 녹음/업로드 JS: `app/static/js/recorder.js`

---

## 주요 API

- `POST /meetings/record`
  - Form-data: `audio` (UploadFile, `audio/webm`), `duration_seconds` (float)
  - 처리: STT → 요약 → DB 저장
  - 응답: `MeetingRecordResponse { id, transcript, summary }`

- `GET /meetings/`
  - 최근 회의 리스트 (`MeetingListItem[]`)

- `GET /meetings/{id}`
  - 단일 회의 상세 (`MeetingDetailResponse`)

- `DELETE /meetings/{id}`
  - 회의 기록 삭제 (204 No Content)

---

## 프론트엔드 동작 요약

- 페이지 로드시:
  - 브라우저 녹음 지원 여부 검사
  - `/meetings` 호출해 좌측 리스트 렌더링
- `녹음 시작` 버튼:
  - `getUserMedia` + `MediaRecorder` 로 오디오 캡처
- `완료` 버튼:
  - Blob(`audio/webm`) 생성 후 `/meetings/record` 로 업로드
  - 응답의 transcript/summary 를 우측 STT/SUMMARY 탭에 표시
  - 리스트 재조회
- LEFT NAV 항목 클릭:
  - `/meetings/{id}` 호출해 해당 회의 내용 표시
- X 버튼 클릭:
  - `DELETE /meetings/{id}` 후 리스트/상세 갱신

---

## 주의사항

- 실제 Azure 키, 기타 민감한 값은 **절대 git 에 커밋하지 않습니다.**
  - `.env` 는 로컬 전용 파일로 사용하고, 예시는 `env.example` 로 관리합니다.
- Azure 키를 교체한 경우 GitHub Push Protection 에서 해당 시크릿을
  "rotated/allow" 처리해 주어야 이전 커밋도 푸시 가능합니다.

