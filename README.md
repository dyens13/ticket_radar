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

## cron 운영 (Linux)

cron은 실행 시각만 결정합니다.
스크립트는 실행될 때마다 항상 아래 두 작업을 순서대로 모두 수행합니다.
- `new-alert-once`
- `preopen-alert-once`

- 스크립트: `scripts/cron_hourly.py`
- 로그: `logs/cron_hourly.log` (같은 날에는 누적, 날짜가 바뀌면 파일 삭제 후 새로 시작)

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

## Windows 스케줄러 (`schtasks`) 운영

윈도우에서는 `scripts/hourly_windows.py`를 작업 스케줄러로 실행하면 됩니다.
스크립트는 실행될 때마다 아래 2개를 순서대로 실행합니다.
- `new-alert-once`
- `preopen-alert-once`

`hourly_windows.py`는 내부에서 프로젝트 루트로 `chdir`하므로,
작업 스케줄러 시작 경로가 달라도 `./data/state.yaml` 경로가 깨지지 않습니다.

### 기본 변수
- 작업 이름: `ticket_radar_hourly`
- 실행 파일(권장): `C:\miniconda3\envs\py311\pythonw.exe` (콘솔 창 안 뜸)
- 스크립트: `D:\Research\ticket_radar\scripts\hourly_windows.py`
- 로그: `logs/hourly_windows.log` (같은 날 누적, 날짜 바뀌면 자동 초기화)

### 1) 작업 등록 (매시간 00분)
```powershell
schtasks /Create /TN "ticket_radar_hourly" /TR "C:\miniconda3\envs\py311\pythonw.exe D:\Research\ticket_radar\scripts\hourly_windows.py" /SC HOURLY /MO 1 /ST 00:00 /F
```

### 2) 작업 즉시 실행
```powershell
schtasks /Run /TN "ticket_radar_hourly"
```

### 3) 작업 상태/설정 조회
```powershell
schtasks /Query /TN "ticket_radar_hourly" /V /FO LIST
```

### 4) 작업 삭제
```powershell
schtasks /Delete /TN "ticket_radar_hourly" /F
```

### 5) 시간/주기 변경
`schtasks /Change`는 변경 가능한 항목이 제한적이라,
실무에서는 **삭제 후 재등록**이 가장 확실합니다.

- 예: 매시 30분으로 변경
```powershell
schtasks /Delete /TN "ticket_radar_hourly" /F
schtasks /Create /TN "ticket_radar_hourly" /TR "C:\miniconda3\envs\py311\pythonw.exe D:\Research\ticket_radar\scripts\hourly_windows.py" /SC HOURLY /MO 1 /ST 00:30 /F
```

- 예: 2시간마다 15분에 실행
```powershell
schtasks /Delete /TN "ticket_radar_hourly" /F
schtasks /Create /TN "ticket_radar_hourly" /TR "C:\miniconda3\envs\py311\pythonw.exe D:\Research\ticket_radar\scripts\hourly_windows.py" /SC HOURLY /MO 2 /ST 00:15 /F
```

### 6) 로그 확인
```powershell
Get-Content D:\Research\ticket_radar\logs\hourly_windows.log
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
