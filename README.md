# ticker_radar

놀티켓(NOL Ticket) + 멜론티켓(Melon Ticket) 티켓 오픈 정보를 모니터링해서,
`config.yaml` 키워드가 포함된 공연만 텔레그램으로 알림 전송하는 Python 봇입니다.

## 저장 방식
- DB 사용 안 함
- 상태는 YAML 파일 1개(`app.state_path`, 기본 `./data/state.yaml`)에만 저장
- 저장 목적
  - 이미 보낸 신규 알림 중복 방지
  - 전날/당일아침/1시간전 리마인더 중복 방지
- 자동 정리
  - 예매 오픈 시각이 지난 이벤트는 `app.retention_days` 이후 자동 삭제
  - 삭제된 이벤트의 리마인더 전송 기록도 같이 삭제

## 대상 사이트
- NOL Ticket: `https://tickets.interpark.com/contents/notice`
- Melon Ticket: `https://ticket.melon.com/csoon/index.htm`

## 설치
```bash
python3 scripts/setup.py
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
- `app.timezone`: 알림 시간 계산 기준 타임존
- `app.state_path`: YAML 상태 파일 경로
- `app.retention_days`: 오래된 상태 자동 삭제 기준

## 실행 모드

### 1) 장기 실행 모드 (`--mode run`)
```bash
python3 scripts/run.py
```
또는
```bash
.venv/bin/python src/main.py --config config.yaml --mode run
```

동작:
- 프로세스가 계속 떠 있음
- 내부 스케줄러(APScheduler)가 아래 작업 실행
  - 하루 1회 신규 등록 체크
  - N분 간격 리마인더 체크

운영 방식:
- `tmux`/`screen`/`systemd` 중 하나 필요
- 단순 테스트는 tmux, 운영은 systemd 권장

### 2) 단발 실행 모드 (`--mode daily-once`, `--mode reminder-once`)
```bash
.venv/bin/python src/main.py --config config.yaml --mode daily-once
.venv/bin/python src/main.py --config config.yaml --mode reminder-once
```

동작:
- `daily-once`: 소스 수집 -> 키워드 필터 -> 신규 항목만 알림 -> 상태 파일 저장 -> 종료
- `reminder-once`: 상태 파일에서 리마인더 대상 확인 -> 조건 맞는 건만 알림 -> 전송 기록 저장 -> 종료

운영 방식:
- `crontab`으로 주기 실행 권장
- 프로세스를 계속 띄울 필요 없음

## UTC 서버에서 cron 운영 (권장)
서버 시스템 타임존이 UTC여도 문제 없습니다. `config.yaml`의 `app.timezone: Asia/Seoul` 기준으로
이벤트 시간/리마인더 시간을 계산합니다.

예시 크론(UTC 기준):
```cron
# 매일 00:00 UTC = 09:00 KST 신규 등록 체크
0 0 * * * cd /path/to/ticker_radar && /path/to/ticker_radar/.venv/bin/python src/main.py --config config.yaml --mode daily-once >> /path/to/ticker_radar/daily.log 2>&1

# 10분마다 리마인더 체크
*/10 * * * * cd /path/to/ticker_radar && /path/to/ticker_radar/.venv/bin/python src/main.py --config config.yaml --mode reminder-once >> /path/to/ticker_radar/reminder.log 2>&1
```

## 알림 규칙
- 신규 등록 알림: 하루 1회 수집 시점에 새로 발견된 항목만 전송
- 리마인더 알림
  - 전날 지정 시각
  - 당일 아침 지정 시각
  - 1시간 전
- 모든 알림은 중복 전송 방지

## 주의
- 사이트 DOM이 바뀌면 파서 업데이트 필요
- 사이트 이용약관/robots 정책 확인 후 사용
