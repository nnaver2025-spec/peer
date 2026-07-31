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

## 여론(FOMO) 갱신 (launchd, 2시간 주기)

커뮤니티 여론 데이터는 별도 에이전트 `com.peer.fomo.update`가 2시간마다 갱신한다.
주기를 대시보드(30분)와 분리한 이유는 한 회차에 8개 게시판 x 30종목으로 500회 넘게
요청하기 때문이다. 30분마다 두드리면 차단을 부르고, 여론은 주가만큼 빨리 변하지도 않는다.

구성은 대시보드 쪽과 같은 형태다.

- `~/.peer-cron/run_fomo.sh` - launchd가 호출하는 런처
- `~/.peer-cron/fomo_update.sh` - 락/로그를 관리하고 `fomo_watch.py`를 실행
- `~/.peer-cron/logs/fomo.log` - 실행 로그 (5000줄 초과 시 자동 트림)

plist에 `SoftResourceLimits.NumberOfFiles = 4096`을 둔다. launchd 기본 한도가
256이라 병렬 수집(소스 8개 x 지수 별칭)에서 파일 디스크립터가 고갈된다. 실측에서
지수 소스가 `[Errno 24] Too many open files`로 빠져 나스닥 표본이 줄었다. 로그인
셸은 1048575인데 launchd는 그 값을 물려받지 않는다.

```bash
mkdir -p ~/.peer-cron
cp scripts/fomo_update.sh scripts/run_fomo.sh ~/.peer-cron/
chmod +x ~/.peer-cron/fomo_update.sh ~/.peer-cron/run_fomo.sh
cp scripts/com.peer.fomo.update.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.peer.fomo.update.plist
```

한 회차는 약 2분 걸린다. 즉시 실행은
`launchctl kickstart -p gui/$(id -u)/com.peer.fomo.update`.
