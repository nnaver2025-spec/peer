#!/bin/bash
# 괴리 따라잡기 백테스트 데이터를 갱신한다. launchd가 2시간마다 호출한다.
#
# 사례 목록 맨 위의 "현재" 행이 이 스크립트로만 갱신된다. 크론이 없던 동안
# 검증 탭은 마지막 수동 실행 시점에 멈춰 있었고, 갭 탭(30분 주기)과 날짜가
# 하루 이상 어긋났다.
#
# 주기를 2시간으로 둔 이유: 6년치를 다시 계산하지만 확정된 과거 통계는 하루
# 사이에 거의 움직이지 않는다. 실제로 바뀌는 값은 마지막 거래일 기준의 현재
# 위치뿐이라 30분 간격으로 돌릴 이유가 없다.
set -uo pipefail

# 경로는 환경변수로 덮을 수 있다. 기본값은 기존 launchd 설정과 같다.
REPO="${PEER_REPO:-$HOME/Documents/peer}"
PYTHON="${PEER_PYTHON:-$REPO/.venv/bin/python}"
LOG_DIR="${PEER_LOG_DIR:-$HOME/.peer-cron/logs}"
LOG="$LOG_DIR/backtest.log"
LOCK="$LOG_DIR/backtest.lock"
LOG_MAX_LINES=5000

mkdir -p "$LOG_DIR"

stamp() { date "+%Y-%m-%d %H:%M:%S %Z"; }

# 6년치 재계산이라 한 회차가 30초 남짓 걸린다. 겹치면 이번 회차를 건너뛴다.
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "=== $(stamp) skipped (실행 중) ===" >>"$LOG"
    exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

{
    echo "=== $(stamp) backtest start ==="

    if [ ! -x "$PYTHON" ]; then
        echo "[error] venv python not found at $PYTHON"
        echo "=== $(stamp) backtest failed ==="
        exit 1
    fi

    cd "$REPO" || exit 1

    if "$PYTHON" catchup_backtest.py; then
        echo "=== $(stamp) backtest ok ==="
    else
        code=$?
        echo "=== $(stamp) backtest failed (exit $code) ==="
        exit "$code"
    fi
} >>"$LOG" 2>&1

if [ "$(wc -l <"$LOG")" -gt "$LOG_MAX_LINES" ]; then
    tail -n "$LOG_MAX_LINES" "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
