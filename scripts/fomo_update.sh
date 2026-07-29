#!/bin/bash
# 커뮤니티 여론(FOMO) 데이터를 갱신한다. launchd가 2시간마다 호출한다.
# 이 파일은 ~/.peer-cron/fomo_update.sh의 보관본이다. macOS TCC가 launchd에서
# ~/Documents 안 스크립트 실행과 로그 쓰기를 막으므로 스크립트와 로그를 홈 밖에
# 두고, 리포 안에는 fomo_data.json만 쓴다.
#
# 갱신 주기를 대시보드(30분)와 분리한 이유: 한 회차에 8개 게시판 x 30종목으로
# 500회 넘게 요청한다. 30분마다 두드리면 차단을 부르고, 여론은 주가만큼 빨리
# 변하지도 않는다.
set -uo pipefail

REPO="/Users/huisang/Documents/peer"
PYTHON="$REPO/.venv/bin/python"
LOG_DIR="/Users/huisang/.peer-cron/logs"
LOG="$LOG_DIR/fomo.log"
LOCK="$LOG_DIR/fomo.lock"
LOG_MAX_LINES=5000

mkdir -p "$LOG_DIR"

stamp() { date "+%Y-%m-%d %H:%M:%S %Z"; }

# 한 회차가 2분 넘게 걸릴 수 있다. 겹치면 이번 회차를 건너뛴다.
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "=== $(stamp) skipped (실행 중) ===" >>"$LOG"
    exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

{
    echo "=== $(stamp) fomo start ==="

    if [ ! -x "$PYTHON" ]; then
        echo "[error] venv python not found at $PYTHON"
        echo "=== $(stamp) fomo failed ==="
        exit 1
    fi

    cd "$REPO" || exit 1

    if "$PYTHON" fomo_watch.py; then
        echo "=== $(stamp) fomo ok ==="
    else
        code=$?
        echo "=== $(stamp) fomo failed (exit $code) ==="
        exit "$code"
    fi
} >>"$LOG" 2>&1

if [ "$(wc -l <"$LOG")" -gt "$LOG_MAX_LINES" ]; then
    tail -n "$LOG_MAX_LINES" "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
