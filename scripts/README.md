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

## 백테스트 갱신 (launchd, 2시간 주기)

검증 탭 데이터는 에이전트 `com.peer.backtest.update`가 2시간마다 갱신한다.

이 에이전트가 없던 동안 검증 탭은 마지막 수동 실행 시점에 멈춰 있었다. 사례
목록 맨 위의 "현재" 행이 `catchup_backtest.py`로만 만들어지기 때문에, 갭
탭(30분 주기)과 날짜가 하루 이상 어긋났다.

주기를 2시간으로 둔 이유는 6년치를 다시 계산하지만 확정된 과거 통계가 하루
사이에 거의 움직이지 않기 때문이다. 실제로 바뀌는 값은 마지막 거래일 기준의
현재 위치뿐이라 30분 간격으로 돌릴 이유가 없다.

- `~/.peer-cron/run_backtest.sh` - launchd가 호출하는 런처
- `~/.peer-cron/backtest_update.sh` - 락/로그를 관리하고 `catchup_backtest.py`를 실행
- `~/.peer-cron/logs/backtest.log` - 실행 로그 (5000줄 초과 시 자동 트림)

```bash
mkdir -p ~/.peer-cron
cp scripts/backtest_update.sh scripts/run_backtest.sh ~/.peer-cron/
chmod +x ~/.peer-cron/backtest_update.sh ~/.peer-cron/run_backtest.sh
cp scripts/com.peer.backtest.update.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.peer.backtest.update.plist
```

한 회차는 약 30초 걸린다. 즉시 실행은
`launchctl kickstart -p gui/$(id -u)/com.peer.backtest.update`.

### 그룹마다 "현재" 날짜가 다른 이유

`current_state`는 그룹 시계열의 마지막 값(`rel.iloc[-1]`)을 쓴다. 해외 티커가
섞인 그룹은 시차와 휴일 때문에 국내보다 하루 이상 뒤처진다. 실측(2026-07-31
15:16 갱신)에서 25개 그룹은 당일, 6개는 전일, 유럽 방산 1개는 이틀 전이었다.
버그가 아니라 그 그룹에서 확보된 가장 최근 거래일이라는 뜻이다.
