# 자동 갱신 (launchd, 30분 주기)

대시보드 데이터는 launchd 에이전트 `com.peer.tracker.update`가 30분마다 갱신한다.

## 왜 스크립트가 리포 밖에서 도는가

macOS TCC는 launchd/cron이 `~/Documents` 안의 셸 스크립트를 읽거나 실행하는 것을
차단한다(`Operation not permitted`). 같은 조건에서 `.venv` 파이썬 실행과
`frontend/public/` 쓰기는 허용된다. 그래서 셸 스크립트와 로그만 `~/.peer-cron/`에
두고, 리포 안에는 `dashboard_data.json`만 쓴다.

이 폴더의 `update.sh`와 `run_update.sh`는 버전 관리용 보관본이다.
실제로 실행되는 파일은 `~/.peer-cron/` 쪽이다.

## 구성

- `~/.peer-cron/run_update.sh` - launchd가 호출하는 런처
- `~/.peer-cron/update.sh` - 락/로그를 관리하고 `peer_tracker.py`를 실행
- `~/.peer-cron/logs/update.log` - 실행 로그 (5000줄 초과 시 자동 트림)
- `~/Library/LaunchAgents/com.peer.tracker.update.plist` - 등록된 에이전트

## 설치 / 재설치

```bash
mkdir -p ~/.peer-cron
cp scripts/update.sh scripts/run_update.sh ~/.peer-cron/
chmod +x ~/.peer-cron/update.sh ~/.peer-cron/run_update.sh
cp scripts/com.peer.tracker.update.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.peer.tracker.update.plist
```

보관본을 수정하면 `~/.peer-cron/`으로 다시 복사해야 반영된다.

## 상태 확인

```bash
launchctl list | grep peer          # 등록 여부
tail -5 ~/.peer-cron/logs/update.log  # 마지막 실행 결과
launchctl kickstart -p gui/$(id -u)/com.peer.tracker.update  # 즉시 실행
```

로그 마지막 줄은 `update ok`, `update failed (exit N)`, `skipped (실행 중)` 중 하나다.
한 회차는 약 25초 걸린다.
