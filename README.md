# Peer Spread Tracker

해외 선행(Lead) Peer 그룹과 국내 후행(Lag) Peer 그룹의 주가 괴리를 섹터별로 추적한다.

- `sheet_groups.py` - 관심종목 시트의 표 구조를 옮긴 Peer 그룹 정의 (단일 출처)
- `peer_tracker.py` - yfinance로 2020년 이후 종가 수집 → 최근 6개월 스프레드 Z-Score + 장기 커플링 강도 → `frontend/public/dashboard_data.json`
- `kr_names.json` - 국내 티커 표시명 275개
- `frontend/` - React + Vite + Tailwind 대시보드 (라이트 미니멀, 카드 그리드)
- `analysis/` - 일회성 검증 스크립트 (커플링, 신호 백테스트, 데이터 커버리지)
- `scripts/` - 30분 주기 자동 갱신 설정 (launchd). 설치는 `scripts/README.md` 참고

## 그룹 구성

그룹 정의는 `sheet_groups.py`가 단일 출처다. 관심종목 시트의 표를 그대로 옮겼고,
국내(lag) 종목이 없는 표(아날로그 반도체, CPU, EDA, 우라늄, 데이터센터)는
스프레드를 계산할 수 없어 대시보드에서 제외한다. 현재 32개 그룹 470여 종목.

티커를 추가할 때는 `analysis/verify_sheet_tickers.py`로 가격 조회가 되는지 먼저 확인하고,
`analysis/validate_sheet_groups.py`로 그룹 응집도와 커플링을 검증한다.

## 1. 파이썬 데이터 수집

```bash
git clone https://github.com/nnaver2025-spec/peer.git
cd peer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python peer_tracker.py
```

실행하면 그룹별 인덱스/스프레드/Z-Score가 콘솔에 찍히고 `frontend/public/dashboard_data.json`이 갱신된다.
데이터가 없는 티커는 경고만 남기고 그룹 계산에서 제외한다.

국내 종목은 티커 대신 종목명으로 표시한다. 매핑은 `kr_names.json`에 있고,
JSON에는 `{"ticker": "005930.KS", "label": "삼성전자", "missing": false}` 형태로 담긴다.
매핑에 없는 티커(해외 종목)는 티커를 그대로 쓴다.

계산 로직 단위 테스트는 네트워크 없이 돈다.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## 2. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` 접속. 데이터만 갱신하려면 파이썬 스크립트를 다시 실행하면 되고, 프론트 재빌드는 필요 없다.

프로덕션 빌드는 `npm run build`, 확인은 `npm run preview`.

## 계산 방식

1. 티커별 수정 종가를 날짜 union으로 합치고 `ffill` - 미국/독일/스위스/한국 휴장일 차이로 스프레드가 튀는 것을 막는다.
2. 그룹 내 전 종목 데이터가 갖춰진 첫 거래일을 100으로 정규화한 뒤 종목 평균 = 그룹 인덱스.
3. `spread = lag_index - lead_index`, 20일 rolling 평균/표준편차로 Z-Score.
4. `|Z| >= 1.5`이고 커플링이 `strong` 또는 `moderate`이면 `alert: true`.
   임계는 넘었지만 커플링이 약한 경우는 `z_extreme: true, alert: false`로 구분한다.
   양수는 오버슈팅(국내 과열), 음수는 언더슈팅(국내 갭 확대).
5. 국내(lag) 종목에서 두 종목을 따로 뽑는다. 최근 6개월 상대강도(RS) 1등이
   `bellwether_ticker`(주도주), 시가총액 1등이 `top_pick_ticker`(대장주)다.
   두 선정은 서로 독립이라 같은 종목일 수도 있다. `bellwether_index`는 RS 1등
   종목만 100 정규화한 지수, `rest_index`는 그 종목을 뺀 나머지 평균이다.
   Top Pick은 표시 전용이고 인덱스 계산에는 관여하지 않는다.
6. `internal_spread = rest_index - bellwether_index`이고 같은 20일 Z-Score로
   `bellwether_z_score`를 낸다. 음수일수록 주도주만 앞서간 상태(나머지가 덜 오름,
   추격 매수 여지)이고 양수는 나머지가 주도주보다 앞선 순환매 확산이다.
   `|internal Z| >= 1.5`이면 `bellwether_alert: true`.
   국내 종목끼리의 관계이므로 해외-국내 커플링 등급으로 게이팅하지 않는다.

## 커플링 강도

스프레드가 좁혀진다는 가정은 두 그룹이 실제로 동행할 때만 성립한다.
2020년 이후 일간 수익률로 그룹별 커플링을 측정해 등급을 매긴다.

등급은 동행 상관(`corr`)과 시차 1일 상관(`corr_lag1`) 중 강한 쪽(`strength`)으로 정한다.

- `strong` (strength >= 0.30)
- `moderate` (>= 0.15)
- `weak` (< 0.15)

미국 장이 먼저 닫히는 그룹은 전달이 다음 거래일에 나타나므로 동행 상관만 보면
실제 연결을 놓친다. 예를 들어 미국 방산은 `corr` 0.13이지만 `corr_lag1`은 0.28이다.
`lead_channel`이 `same_day`인지 `next_day`인지로 어느 채널이 지배적인지 구분하고,
카드에는 그 채널을 강조해 표시한다.

방산은 시트가 유럽/미국 표를 따로 두었으므로 두 카드를 유지한다.
같은 국내 그룹을 양쪽 lead에 각각 연결해 어느 지역이 더 강하게 선행하는지 비교한다.

티커 상장 시점이 다르므로(GEV 2024-03, CEG/SMR 2022, 실리콘투 2021-10, RKLB 2020-11)
커플링 계산에는 `chain_index()`를 쓴다. 각 날짜에 존재하는 종목의 수익률만 평균해
누적하므로 신규 편입 시 인덱스 점프가 생기지 않는다.
스프레드 계산은 기존 교집합 방식(`build_group_frame`)을 그대로 쓴다.

### 검증 결과

`analysis/signal_backtest.py`로 2년 구간 `|Z| >= 1.5` 신호 1,290건을 확인한 결과,
스프레드 축소 비율은 5일 후 47.9%, 10일 후 46.1%, 20일 후 44.6%였다.
공적분 검정도 11개 그룹 전부 `p > 0.05`로 평균회귀를 지지하지 않았다.
따라서 Z-Score는 단독 매매 신호가 아니라 커플링 등급과 함께 읽어야 한다.

상수는 `peer_tracker.py` 상단(`LOOKBACK_DAYS`, `Z_WINDOW`, `ALERT_THRESHOLD`, `SLEEP_SEC`)에서 조정한다.
