# Observability Stack

범용 Prometheus + Grafana + Loki 모니터링 및 로깅 스택입니다.

## 특징

- ✅ 환경 변수로 모든 설정 커스터마이징 가능
- ✅ 프로젝트 독립적인 범용 구성
- ✅ 기본값 제공으로 즉시 사용 가능
- ✅ 프로덕션 환경 대응 가능

## 빠른 시작

### 1. Observability 스택 실행

```bash
docker-compose -f docker-compose.observability.yml up -d
```

### 2. 서비스 접속

- **Grafana**: <http://localhost:3000>
  - Username: `admin`
  - Password: `admin`

- **Prometheus**: <http://localhost:9090>

- **Loki**: <http://localhost:3100>

## 커스터마이징

### 환경 변수 설정

`.env.observability` 파일을 생성하여 설정을 오버라이드:

```bash
# 포트 변경 예시
GRAFANA_PORT=3001
PROMETHEUS_PORT=9091
LOKI_PORT=3101

# 비밀번호 변경
GRAFANA_ADMIN_PASSWORD=secure-password

# 데이터 보존 기간
PROMETHEUS_RETENTION=30d
```

환경 변수와 함께 실행:

```bash
docker-compose -f docker-compose.observability.yml --env-file .env.observability up -d
```

### 애플리케이션 연동

#### Prometheus 메트릭 수집 설정

`observability/prometheus/prometheus.yml`에 scrape 설정 추가:

```yaml
scrape_configs:
  - job_name: 'my-app'
    scrape_interval: 10s
    static_configs:
      - targets: ['host.docker.internal:8000']
        labels:
          app: 'my-app'
          environment: 'development'
```

#### 애플리케이션에서 Loki 사용

Python 예시:

```python
import logging_loki

handler = logging_loki.LokiQueueHandler(
    Queue(-1),
    url="http://localhost:3100/loki/api/v1/push",
    tags={"app": "my-app", "environment": "dev"},
    version="1"
)
logger.addHandler(handler)
```

Node.js 예시:

```javascript
const winston = require('winston');
const LokiTransport = require('winston-loki');

const logger = winston.createLogger({
  transports: [
    new LokiTransport({
      host: 'http://localhost:3100',
      labels: { app: 'my-app' }
    })
  ]
});
```

## Grafana 대시보드 설정

### Prometheus 메트릭 확인

1. Grafana 접속 (http://localhost:3000)
2. Explore 메뉴 선택
3. Prometheus 데이터소스 선택
4. 쿼리 예시:
   ```promql
   # 요청 수
   rate(http_requests_total[5m])
   
   # 응답 시간
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
   
   # 에러율
   rate(http_requests_total{status=~"5.."}[5m])
   ```

### Loki 로그 확인

1. Grafana Explore 메뉴
2. Loki 데이터소스 선택
3. LogQL 쿼리 예시:
   ```logql
   # 모든 로그
   {app="meeting-stt"}
   
   # 에러 로그만
   {app="meeting-stt"} |= "ERROR"
   
   # 특정 경로 로그
   {app="meeting-stt"} |= "/meetings/record"
   ```

## 스택 중지

```bash
docker-compose -f docker-compose.observability.yml down
```

## 데이터 삭제 (볼륨 포함)

```bash
docker-compose -f docker-compose.observability.yml down -v
```

## 트러블슈팅

### Prometheus가 FastAPI 메트릭을 수집하지 못하는 경우

`observability/prometheus/prometheus.yml`에서 타겟 확인:
- macOS/Windows: `host.docker.internal:8000`
- Linux: `172.17.0.1:8000` 또는 `--network host` 사용

### Loki 연결 실패

FastAPI 앱이 Docker 외부에서 실행되는 경우:
```bash
LOKI_URL=http://localhost:3100/loki/api/v1/push
```

FastAPI 앱도 Docker에서 실행되는 경우:
```bash
LOKI_URL=http://loki:3100/loki/api/v1/push
```

## 프로덕션 배포 시 권장사항

1. **데이터 보존 기간 설정**: Loki `retention_period` 조정
2. **리소스 제한**: Docker Compose에 `mem_limit`, `cpus` 추가
3. **인증 활성화**: Grafana 기본 비밀번호 변경
4. **외부 스토리지**: S3, GCS 등 사용 (대용량 로그)
5. **알림 설정**: Prometheus Alertmanager 추가
