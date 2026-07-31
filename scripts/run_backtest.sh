#!/bin/bash
# 백테스트 갱신 런처 (launchd에서 2시간마다 호출).
#
# 스크립트를 Documents 밖에 두는 이유:
# macOS TCC는 launchd/cron이 ~/Documents 안의 셸 스크립트를 읽거나 실행하는 것을
# 차단한다(Operation not permitted). 같은 조건에서 venv 파이썬 실행과 logs/ 쓰기는
# 허용되므로, 셸 스크립트만 홈 밖으로 옮기면 리포 안 데이터는 정상적으로 갱신된다.
#
# 원본은 scripts/backtest_update.sh 이고, 이 런처는 홈 밖에 복제된 사본을 호출한다.
exec /bin/bash "$HOME/.peer-cron/backtest_update.sh"
