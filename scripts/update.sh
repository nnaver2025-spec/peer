#!/bin/bash
# 대시보드 데이터를 갱신한다. launchd가 30분마다 호출한다.
# 이 파일은 scripts/update.sh의 복제본이다. macOS TCC가 launchd에서
# ~/Documents 안 스크립트 실행과 로그 쓰기를 막으므로 스크립트와 로그를
# 홈 밖에 두고, 리포 안에는 dashboard_data.json만 쓴다.
# 로그는 ~/.peer-cron/logs/update.log 에 누적된다.
set -uo pipefail

# 경로는 환경변수로 덮을 수 있다. 기본값은 기존 launchd 설정과 같다.
REPO="${PEER_REPO:-$HOME/Documents/peer}"
PYTHON="${PEER_PYTHON:-$REPO/.venv/bin/python}"
LOG_DIR="${PEER_LOG_DIR:-$HOME/.peer-cron/logs}"
LOG="$LOG_DIR/update.log"
LOCK="$LOG_DIR/update.lock"
LOG_MAX_LINES=5000

mkdir -p "$LOG_DIR"

stamp() { date "+%Y-%m-%d %H:%M:%S %Z"; }

# 30분 주기라 앞선 실행이 남아 있을 수 있다. 겹치면 이번 회차를 건너뛴다.
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "=== $(stamp) skipped (실행 중) ===" >>"$LOG"
    exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

{
    echo "=== $(stamp) update start ==="

    if [ ! -x "$PYTHON" ]; then
        echo "[error] venv python not found at $PYTHON"
        echo "=== $(stamp) update failed ==="
        exit 1
    fi

    cd "$REPO" || exit 1

    if "$PYTHON" peer_tracker.py; then
        echo "=== $(stamp) update ok ==="
    else
        code=$?
        echo "=== $(stamp) update failed (exit $code) ==="
        exit "$code"
    fi
} >>"$LOG" 2>&1

# 30분마다 쌓이므로 로그를 최근 분량만 남긴다.
if [ "$(wc -l <"$LOG")" -gt "$LOG_MAX_LINES" ]; then
    tail -n "$LOG_MAX_LINES" "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
