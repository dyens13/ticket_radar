# ticket_radar

NOL Ticket + Melon Ticket 오픈 예정 공연을 수집하고,
`config.yaml`의 키워드에 매칭되는 항목을 텔레그램으로 전송하는 봇입니다.

## 저장 방식
- DB 미사용
- 상태는 YAML 파일 1개(`app.state_path`, 기본 `./data/state.yaml`)에 저장
- 저장 목적
  - 신규 알림 중복 방지
  - 리마인더(전날/당일아침/1시간전) 중복 방지
- 자동 정리
  - 오픈 시각이 지난 이벤트를 `app.retention_days` 기준으로 정리

## 대상 사이트
- NOL Ticket: `https://tickets.interpark.com/contents/notice`
- Melon Ticket: `https://ticket.melon.com/csoon/index.htm`

## 설치
```bash
python scripts/setup.py
```

## 설정
```bash
cp config.example.yaml config.yaml
```

필수 수정:
- `telegram.bot_token`
- `telegram.chat_id`
- `keywords`

중요 설정:
- `app.timezone`
- `app.state_path`
- `app.retention_days`

Melon 다중 페이지 기본값:
- `sources[].type == "melonticket"`는 기본 `max_pages: 10`까지 수집
- 필요 시 `config.yaml`에서 조정 가능

예시:
```yaml
sources:
  - type: "melonticket"
    enabled: true
    url: "https://ticket.melon.com/csoon/index.htm"
    max_pages: 10
```

## 실행 모드

### 1) 장기 실행 (`--mode run`)
```bash
python scripts/run.py
```

### 2) 단발 실행
- 신규(새 공연) 알림 1회 실행
```bash
python src/main.py --config config.yaml --mode new-alert-once
```
- 예매 직전 알림 1회 실행
```bash
python src/main.py --config config.yaml --mode preopen-alert-once
```

## cron 운영 (권장)

cron은 실행 시각만 결정합니다.
스크립트는 실행될 때마다 항상 아래 두 작업을 순서대로 모두 수행합니다.
- `new-alert-once`
- `preopen-alert-once`

- 스크립트: `scripts/cron_hourly.py`
- 로그: `logs/cron_hourly.log` (스크립트 내부에서 누적 기록)

### 1) 서버 파이썬 경로 설정
`scripts/cron_hourly.py`의 아래 상수를 서버 환경에 맞게 수정:

```python
TARGET_PYTHON = "/usr/bin/python3"
```

### 2) crontab 등록
원하는 시각은 crontab에서 결정:

```cron
0 * * * * cd /path/to/ticket_radar && python scripts/cron_hourly.py
# 예: 매시 30분이면
# 30 * * * * cd /path/to/ticket_radar && python scripts/cron_hourly.py
```

## 알림 규칙
- 신규 등록 알림: 키워드 매칭 + 신규 fingerprint만 전송
- 리마인더 알림
  - 전날 지정 시각
  - 당일 아침 지정 시각
  - 1시간 전
- 모든 알림은 중복 전송 방지

## 패키지명
코드 패키지명은 `ticket_alarm`입니다.

## 주의
- 사이트 DOM/API 변경 시 파서 업데이트 필요
- 사이트 이용약관/robots 정책 확인 후 사용
