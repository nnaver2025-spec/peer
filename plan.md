# Bellwether Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 각 그룹의 국내(Lag) 종목 중 RS 1등을 Bellwether(주도주)로, 시총 1등을 Top Pick(대장주)으로 각각 뽑고, Bellwether와 나머지 종목의 내부 괴리율(Z-Score)을 계산해 대시보드 카드에 표시한다.

**Architecture:** `peer_tracker.py`에 순수 계산 함수(`relative_strength`, `select_bellwether`, `select_top_pick`, `bellwether_split`)와 기존 Z-Score 계산의 공통 추출(`rolling_zscore`)을 더한다. Bellwether는 RS만으로, Top Pick은 시가총액만으로 뽑는 서로 독립적인 선정이고, 내부 괴리율 계산에는 Bellwether만 쓴다. 기존 `lead_index` / `lag_index` / `spread` / `zscore` 계산 경로는 건드리지 않고 `lag_frame`을 재사용해 내부 지표만 덧붙인다. 프론트는 `Sparkline.jsx` / `CouplingMeter.jsx`와 같은 방식으로 `Bellwether.jsx` 단일 컴포넌트를 추가하고 `GroupCard`에서 한 줄 렌더한다.

**Tech Stack:** Python 3 + pandas 3.0.5 + yfinance 1.5.2, pytest(신규 dev 의존성), React 19 + Vite 8 + Tailwind 4.

## Global Constraints

- 그룹 정의 단일 출처는 `sheet_groups.py`다. 이 파일은 수정하지 않는다.
- 기존 출력 필드(`lead_index`, `lag_index`, `spread`, `zscore`, `alert`, `z_extreme`, `coupling`, `history`)의 값과 의미를 바꾸지 않는다. 신규 필드만 추가한다.
- 새 임계값을 만들지 않고 기존 `ALERT_THRESHOLD = 1.5`를 재사용한다 (스펙의 `|1.5|`와 같은 값).
- 주석과 로그는 한국어, 기존 톤(간결한 서술형)을 따른다. 코드 식별자는 ASCII.
- 네트워크 호출은 `SLEEP_SEC` 간격을 지키고 실패해도 그룹 전체를 죽이지 않는다 (기존 `fetch_close` 정책과 동일).
- 테스트는 네트워크를 타지 않는다. 합성 DataFrame으로만 검증한다.
- 프론트 색상은 기존 토큰만 쓴다: `text-warn`(#d92d4b), `text-accent`(#3d5afe), `text-zinc-400`.
- `peer_tracker_backup.py`와 `frontend/src_backup/`은 손대지 않는다.

---

## 검토 필요 결정사항 (구현 전 확인)

### D1. `internal_spread` 부호와 색상 규칙이 스펙 안에서 충돌한다 - 확인 필요

스펙 3번: `internal_spread = rest_index - bellwether_index` = "나머지가 주도주를 따라잡지 못하는 정도".
스펙 5번: "양수(+)면 빨강(주도주 혼자 감), 음수(-)면 파랑(주도주도 같이 빠짐)".

이 둘이 맞지 않는다. 주어진 수식에서 주도주 혼자 오르면 `rest_index < bellwether_index`이므로 `internal_spread`는 음수다. 즉 "주도주 혼자 감"은 음수 구간이고, 스펙 5번의 양수 설명과 반대다.

Option A (이 계획이 채택한 안): 수식은 스펙 3번 그대로 두고 의미 라벨을 수식에 맞춰 교정한다. 기존 `spread = lag - lead`와 부호 방향이 같아(뒤처지는 쪽이 음수) 카드 안에서 색 규칙이 일관된다.

- `internal Z >= +1.5` (빨강): 나머지가 주도주보다 앞섬 = 순환매 확산, 주도주 소외
- `internal Z <= -1.5` (파랑): 주도주만 오르고 나머지가 덜 오름 = 추격 매수 기회
- 스펙 5번의 툴팁 문구 "주도주보다 나머지 종목이 덜 오름 = 추격 매수 기회"는 지표 전체 설명으로 상시 노출한다.

Option B: 수식을 `bellwether_index - rest_index`로 뒤집는다. 스펙 5번의 "양수 = 주도주 혼자 감 = 빨강"이 문자 그대로 맞지만, 필드명 `internal_spread = rest - bellwether`라는 스펙 3번과 어긋나고 기존 `spread` 부호 관례와도 반대가 된다.

Option B를 원하면 Task 5의 `internal = rest_index - bell_index` 한 줄과 Task 6의 라벨 문구만 뒤집으면 된다.

### D2. `lag_index`에서 주도주를 빼지 않는다

스펙 2번의 "bellwether 인덱스를 그룹 평균에서 분리"를 기존 `lag_index` 자체를 주도주 제외 평균으로 바꾸라는 뜻으로 읽지 않았다. 그렇게 하면 32개 그룹 전부의 `spread` / `zscore` / `alert`와 커플링 해석이 한 번에 바뀐다. 이 계획은 `lag_index`(전체 평균)를 그대로 두고 `bellwether_index` / `rest_index`를 추가 산출물로 둔다.

### D3. 신규 alert는 별도 필드다

스펙 4번의 alert를 기존 `alert` 필드에 합치지 않고 `bellwether_alert`로 분리한다. 기존 `alert`는 헤더의 경고 카운트와 "경고" 필터에 쓰이고 커플링 등급으로 게이팅된다. 내부 괴리는 국내 종목끼리의 관계라 해외-국내 커플링과 무관하므로 게이팅 조건이 다르다. 따라서 `bellwether_alert = abs(bellwether_z_score) >= 1.5`이고 커플링 조건을 걸지 않는다.

### D4. 시가총액 조회 비용

`yf.Ticker(t).fast_info["marketCap"]` 실측치는 티커당 약 0.4~0.6초다(삼성전자 1.18초, SK하이닉스 0.42초, 한미반도체 0.54초로 확인). 국내 lag 티커는 중복 제외 260개이므로 기존 실행 시간에 2~3분이 더해진다. 이미 480여 건을 다운로드하는 배치이므로 수용 가능하다고 보고 디스크 캐시는 넣지 않는다. 일일 cron(`scripts/update_daily.sh`)이 느려지는 게 문제라면 `market_caps.json` 캐시를 별도 작업으로 추가하면 된다.

시총이 Top Pick 표시 전용이 된 뒤로 이 비용의 성격이 바뀌었다. 조회가 전부 실패해도 Bellwether와 `internal Z`는 RS만으로 정상 산출되고, 카드에서 Top Pick 줄만 사라진다. 즉 2~3분이 아깝다고 판단되면 시총 조회를 나중에 캐시로 돌려도 핵심 신호는 영향받지 않는다.

### D5. Bellwether와 Top Pick이 같은 종목일 수 있다

두 기준을 독립적으로 뽑으므로 삼성전자처럼 RS도 1등이고 시총도 1등인 경우 두 라벨이 같은 종목을 가리킨다. 이걸 막지 않는다. "대장주가 주도까지 하고 있다"는 것 자체가 읽을 가치가 있는 상태이고, 억지로 2등을 Top Pick으로 밀어내면 "시총 1등"이라는 정의가 깨진다. Task 5 Step 9에서 32개 그룹 전부가 동일하게 나오지는 않는지 확인해 RS 선정이 실제로 동작하는지 검증한다.

---

## 파일 구조

| 파일 | 역할 | 변경 |
|---|---|---|
| `peer_tracker.py` | 수집 + 계산 + JSON 출력 | 수정: 함수 6개 추가, `analyze_group` 확장 (신규 상수 없음) |
| `tests/test_bellwether.py` | 신규 순수 함수 단위 테스트 | 생성 |
| `requirements-dev.txt` | pytest 핀 | 생성 |
| `frontend/src/Bellwether.jsx` | Bellwether/Top Pick 표시 + 색/툴팁 규칙 | 생성 |
| `frontend/src/App.jsx` | `GroupCard`에서 `Bellwether` 렌더 | 수정: import 1줄 + JSX 1줄 |
| `README.md` | 계산 방식 문서에 내부 괴리율 항목 | 수정: 절 2개 추가 |

`Bellwether.jsx`를 따로 두는 이유는 색 규칙 + 툴팁 문구 + 결측 처리가 30줄쯤 되고, 이미 `Sparkline.jsx` / `CouplingMeter.jsx`가 같은 방식으로 분리돼 있기 때문이다.

---

## Task 1: 테스트 환경 준비

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py` (빈 파일)

**Interfaces:**
- Consumes: 없음
- Produces: pytest 실행 가능. 이후 모든 Task가 `.venv/bin/python -m pytest tests/ -v`로 검증한다.

- [ ] **Step 1: dev 의존성 파일 생성**

`requirements-dev.txt`:

```
-r requirements.txt
pytest==9.1.1
```

- [ ] **Step 2: 테스트 패키지 디렉터리 생성**

```bash
mkdir -p tests && touch tests/__init__.py
```

- [ ] **Step 3: 설치하고 pytest가 도는지 확인**

Run: `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest --version`
Expected: `pytest 9.1.1`

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt tests/__init__.py
git commit -m "test: add pytest dev dependency"
```

---

## Task 2: `rolling_zscore` 공통 추출

기존 `analyze_group` 안에 인라인으로 있는 20일 Z-Score 계산을 함수로 뽑는다. 내부 괴리율에도 같은 계산이 필요하므로 중복을 만들지 않기 위한 것이다.

한 가지 의도적 차이가 있다. 원래 코드는 `.dropna()`만 하므로 표준편차가 0이면서 분자가 0이 아닐 때 `inf`가 살아남아 `zscore.empty` 검사를 통과해 버린다. 새 함수는 `inf`를 NaN으로 바꿔 함께 떨어뜨린다. 기존 주석 `[skip] Z-Score 산출 실패 (표준편차 0)`의 의도와 맞고, 실제 32개 그룹에서는 발생하지 않아 산출값은 바뀌지 않는다 (Step 5에서 확인한다).

**Files:**
- Modify: `peer_tracker.py:176-178`(`normalize_to_100`) 아래에 함수 추가, `peer_tracker.py:215-217` 치환
- Test: `tests/test_bellwether.py`

**Interfaces:**
- Produces: `rolling_zscore(series: pd.Series) -> pd.Series` - NaN을 제거한 Z-Score 시리즈. 표본 부족이거나 표준편차가 0이면 빈 시리즈.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_bellwether.py`:

```python
import pandas as pd
import pytest

from peer_tracker import Z_WINDOW, rolling_zscore


def _dates(n):
    return pd.bdate_range("2026-01-01", periods=n)


def test_rolling_zscore_drops_warmup_rows():
    n = Z_WINDOW + 5
    series = pd.Series(range(n), index=_dates(n), dtype=float)
    z = rolling_zscore(series)
    assert len(z) == n - Z_WINDOW + 1
    assert z.notna().all()


def test_rolling_zscore_last_value_matches_manual_calc():
    n = Z_WINDOW + 3
    series = pd.Series([100.0] * (n - 1) + [130.0], index=_dates(n))
    window = series.tail(Z_WINDOW)
    expected = (series.iloc[-1] - window.mean()) / window.std()
    assert rolling_zscore(series).iloc[-1] == pytest.approx(expected)


def test_rolling_zscore_returns_empty_when_flat():
    n = Z_WINDOW + 3
    series = pd.Series([50.0] * n, index=_dates(n))
    assert rolling_zscore(series).empty
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_bellwether.py -v`
Expected: FAIL - `ImportError: cannot import name 'rolling_zscore'`

- [ ] **Step 3: 함수 추가**

`peer_tracker.py`의 `normalize_to_100` 바로 아래에 삽입:

```python
def rolling_zscore(series: pd.Series) -> pd.Series:
    """20일 이동 평균/표준편차 기준 Z-Score. 표본 부족이나 표준편차 0이면 빈 시리즈."""
    rolling = series.rolling(Z_WINDOW)
    z = (series - rolling.mean()) / rolling.std()
    return z.replace([float("inf"), float("-inf")], float("nan")).dropna()
```

- [ ] **Step 4: 기존 호출부 치환**

`analyze_group` 안의

```python
    spread = lag_index - lead_index
    rolling = spread.rolling(Z_WINDOW)
    zscore = ((spread - rolling.mean()) / rolling.std()).dropna()
```

를 다음으로 바꾼다:

```python
    spread = lag_index - lead_index
    zscore = rolling_zscore(spread)
```

- [ ] **Step 5: 테스트 통과 확인 + 기존 동작 회귀 확인**

Run: `.venv/bin/python -m pytest tests/test_bellwether.py -v`
Expected: 3 passed

회귀 확인은 실행 전 JSON을 떠 두고 값이 그대로인지 본다:

```bash
cp frontend/public/dashboard_data.json /tmp/before.json
.venv/bin/python peer_tracker.py
.venv/bin/python - <<'PY'
import json
before = {g["key"]: g["zscore"] for g in json.load(open("/tmp/before.json"))["groups"]}
after = {g["key"]: g["zscore"] for g in json.load(open("frontend/public/dashboard_data.json"))["groups"]}
diff = {k: (before[k], after[k]) for k in before if k in after and abs(before[k] - after[k]) > 0.05}
print("zscore 변동 그룹:", diff or "없음")
PY
```

Expected: `없음`. 시세가 하루 이상 갱신된 뒤라면 작은 차이는 정상이다. 부호가 뒤집히거나 크게 튀는 그룹이 있으면 멈추고 원인을 본다.

- [ ] **Step 6: Commit**

```bash
git add peer_tracker.py tests/test_bellwether.py
git commit -m "refactor: extract rolling_zscore helper"
```

---

## Task 3: Bellwether(RS 1등)와 Top Pick(시총 1등) 선정

두 기준을 합성하지 않는다. Bellwether는 RS 1등, Top Pick은 시총 1등이고 서로 독립적으로 뽑는다. 같은 종목이 둘 다 될 수 있고 그건 정상이다 (예: 삼성전자가 RS도 1등이면 Bellwether = Top Pick).

**Files:**
- Modify: `peer_tracker.py` (함수 3개 추가, 상수 추가 없음)
- Test: `tests/test_bellwether.py`

**Interfaces:**
- Consumes: 없음 (순수 함수)
- Produces:
  - `relative_strength(frame: pd.DataFrame) -> dict[str, float]` - 티커별 RS 값
  - `select_bellwether(frame: pd.DataFrame) -> str | None` - RS 1등 티커. 프레임이 비면 None.
  - `select_top_pick(caps: dict[str, float | None]) -> str | None` - 시총 1등 티커. 시총을 하나도 못 받으면 None.

선정 규칙은 다음으로 확정한다.

- RS는 최근 6개월 정규화 지수의 마지막 값이다. 전 종목이 같은 기준일에 100으로 출발하므로 이 값이 곧 구간 상대강도다. 별도 가중치나 합성 점수는 쓰지 않는다.
- Bellwether = RS 최댓값 종목. 동점이면 프레임 컬럼 순서로 끊어 실행마다 같은 결과가 나오게 한다.
- Top Pick = `market_cap` 최댓값 종목. 시총 조회에 성공한 종목만 후보다. 전부 실패하면 None이고 이때 카드에는 Top Pick을 표시하지 않는다.
- Top Pick은 표시 전용이다. `bellwether_index` / `rest_index` / `internal_spread` 계산에는 관여하지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_bellwether.py`에 추가)**

```python
from peer_tracker import relative_strength, select_bellwether, select_top_pick


def _frame(last_prices, base=100.0):
    """기준일 base에서 출발해 마지막 날 last_prices가 되는 3행 프레임."""
    return pd.DataFrame(
        {t: [base, base, p] for t, p in last_prices.items()}, index=_dates(3)
    )


def test_rs_is_normalized_level_at_last_date():
    rs = relative_strength(_frame({"A": 120.0, "B": 90.0}))
    assert rs["A"] == pytest.approx(120.0)
    assert rs["B"] == pytest.approx(90.0)


def test_rs_is_scale_free_across_price_levels():
    # 절대 주가가 달라도 상승률이 같으면 RS가 같아야 한다.
    frame = pd.DataFrame(
        {"A": [10.0, 10.0, 12.0], "B": [500.0, 500.0, 600.0]}, index=_dates(3)
    )
    rs = relative_strength(frame)
    assert rs["A"] == pytest.approx(120.0)
    assert rs["B"] == pytest.approx(120.0)


def test_bellwether_is_highest_rs_regardless_of_cap():
    # A가 RS 1등이고 시총은 최하위여도 Bellwether는 A다.
    frame = _frame({"A": 140.0, "B": 120.0, "C": 100.0})
    assert select_bellwether(frame) == "A"


def test_bellwether_tie_breaks_on_column_order():
    frame = _frame({"A": 110.0, "B": 110.0})
    assert select_bellwether(frame) == "A"


def test_bellwether_single_ticker_group():
    assert select_bellwether(_frame({"A": 111.0})) == "A"


def test_bellwether_empty_frame_returns_none():
    assert select_bellwether(pd.DataFrame()) is None


def test_top_pick_is_largest_market_cap():
    assert select_top_pick({"A": 1e11, "B": 9e12, "C": 5e12}) == "B"


def test_top_pick_ignores_missing_caps():
    assert select_top_pick({"A": None, "B": 5e12, "C": None}) == "B"


def test_top_pick_returns_none_when_all_caps_missing():
    assert select_top_pick({"A": None, "B": None}) is None


def test_bellwether_and_top_pick_can_be_the_same_ticker():
    frame = _frame({"A": 140.0, "B": 100.0})
    caps = {"A": 9e12, "B": 1e11}
    assert select_bellwether(frame) == "A"
    assert select_top_pick(caps) == "A"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_bellwether.py -v`
Expected: FAIL - `ImportError: cannot import name 'relative_strength'`

- [ ] **Step 3: 함수 구현 (`normalize_to_100` 아래, `rolling_zscore` 위)**

```python
def relative_strength(frame: pd.DataFrame) -> dict[str, float]:
    """티커별 구간 상대강도.

    기준일 100 정규화 지수의 마지막 값이다. 전 종목이 같은 날 100에서
    출발하므로 이 값이 그대로 6개월 상대강도가 되고, 절대 주가 수준과 무관하다.
    """
    if frame.empty:
        return {}

    normalized = frame / frame.iloc[0] * 100
    return {t: float(normalized[t].iloc[-1]) for t in frame.columns}


def select_bellwether(frame: pd.DataFrame) -> str | None:
    """RS 1등 종목 = 주도주. 동점은 컬럼 순서로 끊어 결과를 고정한다."""
    rs = relative_strength(frame)
    if not rs:
        return None

    order = {t: i for i, t in enumerate(frame.columns)}
    return min(rs, key=lambda t: (-rs[t], order[t]))


def select_top_pick(caps: dict[str, float | None]) -> str | None:
    """시가총액 1등 종목 = 대장주. 표시 전용이고 인덱스 계산에는 쓰지 않는다."""
    known = {t: cap for t, cap in caps.items() if cap}
    return max(known, key=lambda t: known[t]) if known else None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_bellwether.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add peer_tracker.py tests/test_bellwether.py
git commit -m "feat: select bellwether by RS and top pick by market cap"
```

---

## Task 4: 시가총액 조회

시가총액은 Top Pick 선정에만 쓴다. 조회가 전부 실패해도 Bellwether와 내부 괴리율은 RS만으로 정상 산출된다.

**Files:**
- Modify: `peer_tracker.py` (`fetch_close` 아래에 함수 추가)

**Interfaces:**
- Consumes: 없음
- Produces: `fetch_market_cap(ticker: str) -> float | None` - 조회 실패 시 None. 프로세스 내 캐시로 같은 티커를 두 번 조회하지 않는다 (lag 슬롯 279개 중 고유 티커 260개).

- [ ] **Step 1: 함수 구현**

`fetch_close` 아래에 삽입:

```python
_CAP_CACHE: dict[str, float | None] = {}


def fetch_market_cap(ticker: str) -> float | None:
    """시가총액. 조회 실패나 미제공이면 None.

    같은 티커가 여러 그룹에 들어가므로 프로세스 안에서 한 번만 조회한다.
    """
    if ticker in _CAP_CACHE:
        return _CAP_CACHE[ticker]

    try:
        cap = yf.Ticker(ticker).fast_info.get("marketCap")
    except Exception:  # 시총은 보조 기준이라 실패해도 RS로 계속 간다
        cap = None
    finally:
        time.sleep(SLEEP_SEC)

    if not cap:
        print(f"  [warn] {ticker} 시가총액 조회 실패 (Top Pick 후보 제외)")

    _CAP_CACHE[ticker] = float(cap) if cap else None
    return _CAP_CACHE[ticker]
```

- [ ] **Step 2: 실제 조회 동작 확인 (네트워크)**

Run:

```bash
.venv/bin/python -c "
from peer_tracker import fetch_market_cap
for t in ['005930.KS', '000660.KS', '042700.KS', 'NOPE.KS']:
    print(t, fetch_market_cap(t))
print('캐시 재조회:', fetch_market_cap('005930.KS'))
"
```

Expected: 삼성전자/SK하이닉스/한미반도체는 1e13 이상의 값(실측 기준 각각 약 1.5e15, 1.2e15, 1.8e13), `NOPE.KS`는 경고 후 `None`, 캐시 재조회는 즉시 같은 값.

- [ ] **Step 3: Commit**

```bash
git add peer_tracker.py
git commit -m "feat: fetch market cap for bellwether scoring"
```

---

## Task 5: 내부 괴리율 계산과 JSON 출력

**Files:**
- Modify: `peer_tracker.py` (`bellwether_split` 추가, `analyze_group` 확장, `main` 요약 로그)
- Test: `tests/test_bellwether.py`

**Interfaces:**
- Consumes: `select_bellwether`, `select_top_pick`, `relative_strength`, `rolling_zscore`, `fetch_market_cap`
- Produces:
  - `bellwether_split(frame: pd.DataFrame, ticker: str) -> tuple[pd.Series, pd.Series | None]` - `(bellwether_index, rest_index)`. 주도주 외 종목이 없으면 두 번째가 None.
  - JSON 그룹 신규 필드: `bellwether_ticker`, `bellwether_name`, `bellwether_rs`, `bellwether_index`, `top_pick_ticker`, `top_pick_name`, `rest_index`, `internal_spread`, `bellwether_z_score`, `bellwether_alert`. 계산 불가 그룹은 `rest_index` / `internal_spread` / `bellwether_z_score`가 `null`이고 `bellwether_alert`는 `false`. 시총을 전부 못 받은 그룹은 `top_pick_ticker` / `top_pick_name`이 `null`.

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_bellwether.py`에 추가)**

```python
from peer_tracker import bellwether_split


def test_split_normalizes_bellwether_alone_to_100():
    bell, _ = bellwether_split(_frame({"A": 130.0, "B": 110.0, "C": 90.0}), "A")
    assert bell.iloc[0] == pytest.approx(100.0)
    assert bell.iloc[-1] == pytest.approx(130.0)


def test_split_rest_is_mean_of_remaining_tickers():
    _, rest = bellwether_split(_frame({"A": 130.0, "B": 110.0, "C": 90.0}), "A")
    assert rest.iloc[0] == pytest.approx(100.0)
    assert rest.iloc[-1] == pytest.approx(100.0)  # (110 + 90) / 2


def test_internal_spread_is_negative_when_bellwether_leads():
    # D1 Option A: rest - bellwether. 주도주만 오르면 음수다.
    bell, rest = bellwether_split(_frame({"A": 140.0, "B": 100.0}), "A")
    assert (rest - bell).iloc[-1] == pytest.approx(-40.0)


def test_split_returns_none_rest_for_single_ticker_group():
    bell, rest = bellwether_split(_frame({"A": 120.0}), "A")
    assert rest is None
    assert bell.iloc[-1] == pytest.approx(120.0)
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_bellwether.py -v`
Expected: FAIL - `ImportError: cannot import name 'bellwether_split'`

- [ ] **Step 3: `bellwether_split` 구현 (`select_bellwether` 아래)**

```python
def bellwether_split(
    frame: pd.DataFrame, ticker: str
) -> tuple[pd.Series, pd.Series | None]:
    """주도주 단독 인덱스와 나머지 평균 인덱스. 나머지가 없으면 두 번째는 None."""
    normalized = frame / frame.iloc[0] * 100
    others = normalized.drop(columns=[ticker])
    return normalized[ticker], (others.mean(axis=1) if not others.empty else None)
```

- [ ] **Step 4: `analyze_group`에서 내부 괴리율 계산**

`lag_index = normalize_to_100(lag_frame.loc[common])` 다음, `spread = lag_index - lead_index` 앞에 삽입:

```python
    # 주도주(RS 1등)와 대장주(시총 1등)는 국내 종목 중에서만 뽑는다.
    # 내부 괴리율은 국내끼리의 관계라 해외-국내 커플링 등급과 무관하게 계산한다.
    lag_recent = lag_frame.loc[common]
    bellwether = select_bellwether(lag_recent)
    top_pick = select_top_pick({t: fetch_market_cap(t) for t in lag_recent.columns})
    bell_rs = relative_strength(lag_recent).get(bellwether) if bellwether else None
    bell_index, rest_index = (
        bellwether_split(lag_recent, bellwether) if bellwether else (None, None)
    )

    internal_spread = None
    internal_z = None
    if rest_index is not None:
        internal = rest_index - bell_index
        internal_zscore = rolling_zscore(internal)
        if not internal_zscore.empty:
            internal_spread = round(float(internal.iloc[-1]), 2)
            internal_z = round(float(internal_zscore.iloc[-1]), 2)
```

- [ ] **Step 5: 로그 한 줄 추가**

기존 `print(f"  lead=...")` 블록 바로 다음에:

```python
    if bellwether:
        z_text = f"{internal_z:+.2f}" if internal_z is not None else "n/a"
        pick_text = label_of(top_pick) if top_pick else "n/a"
        print(
            f"  bellwether={label_of(bellwether)} rs={bell_rs:.1f} "
            f"internal_z={z_text} top_pick={pick_text}"
        )
```

- [ ] **Step 6: 반환 dict에 필드 추가**

`"zscore": round(latest_z, 2),` 아래에 삽입:

```python
        # Bellwether = RS 1등, Top Pick = 시총 1등. 서로 독립이고 같을 수도 있다.
        "bellwether_ticker": bellwether,
        "bellwether_name": label_of(bellwether) if bellwether else None,
        "bellwether_rs": round(bell_rs, 2) if bell_rs is not None else None,
        "bellwether_index": (
            round(float(bell_index.iloc[-1]), 2) if bell_index is not None else None
        ),
        "top_pick_ticker": top_pick,
        "top_pick_name": label_of(top_pick) if top_pick else None,
        "rest_index": (
            round(float(rest_index.iloc[-1]), 2) if rest_index is not None else None
        ),
        "internal_spread": internal_spread,
        "bellwether_z_score": internal_z,
        # 국내 내부 관계라 커플링 등급으로 게이팅하지 않는다 (기존 alert와 별개).
        "bellwether_alert": internal_z is not None and abs(internal_z) >= ALERT_THRESHOLD,
```

- [ ] **Step 7: `main` 요약 로그에 한 줄 추가**

`print(f"커플링 약해 보류된 극단 Z: {muted}개")` 아래:

```python
    bell_alerts = sum(g["bellwether_alert"] for g in groups)
    print(f"주도주 내부 괴리 경고: {bell_alerts}개 (|internal Z| >= {ALERT_THRESHOLD})")
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_bellwether.py -v`
Expected: 17 passed

- [ ] **Step 9: 실제 실행 후 JSON 검증**

Run:

```bash
.venv/bin/python peer_tracker.py
.venv/bin/python - <<'PY'
import json
groups = json.load(open("frontend/public/dashboard_data.json"))["groups"]
print("필드 누락:", [g["key"] for g in groups if "bellwether_name" not in g] or "없음")
print("주도주 미선정:", [g["key"] for g in groups if g["bellwether_name"] is None] or "없음")
print("Top Pick 미선정:", [g["key"] for g in groups if g["top_pick_name"] is None] or "없음")
print("internal Z 없음:", [g["key"] for g in groups if g["bellwether_z_score"] is None] or "없음")
same = [g["key"] for g in groups if g["bellwether_ticker"] == g["top_pick_ticker"]]
print(f"Bellwether == Top Pick: {len(same)}개 / {len(groups)}개")
ranked = sorted(
    (g for g in groups if g["bellwether_z_score"] is not None),
    key=lambda g: -abs(g["bellwether_z_score"]),
)
for g in ranked[:5]:
    print(f"  {g['desc']} / bell={g['bellwether_name']}(RS {g['bellwether_rs']}) "
          f"top={g['top_pick_name']} z={g['bellwether_z_score']:+.2f} "
          f"spread={g['internal_spread']:+.2f} alert={g['bellwether_alert']}")
PY
```

Expected: 필드 누락 없음. 32개 그룹 모두 `bellwether_name`이 채워지고, `internal Z 없음`은 lag 종목이 1개인 그룹만 나온다. 현재 `sheet_groups.py`에는 lag가 1개인 그룹이 없으므로(최소 2개, `SEMI_DramNand`) "없음"이 정상이다.

검증 포인트 두 개를 눈으로 확인한다. 첫째, `SEMI_DramNand`의 `top_pick_name`은 삼성전자여야 한다(국내 시총 1위). 둘째, `Bellwether == Top Pick` 개수가 32개 전부는 아니어야 한다. 전부 같게 나오면 RS와 시총을 분리한 의미가 없다는 뜻이니 `select_bellwether`가 RS를 제대로 쓰는지 다시 본다.

- [ ] **Step 10: Commit**

```bash
git add peer_tracker.py tests/test_bellwether.py
git commit -m "feat: compute internal bellwether spread and z-score"
```

---

## Task 6: 프론트엔드 표시

**Files:**
- Create: `frontend/src/Bellwether.jsx`
- Modify: `frontend/src/App.jsx:4`(import 추가), `frontend/src/App.jsx:143-148`(`Lag 국내` TickerRow 뒤)

**Interfaces:**
- Consumes: JSON 필드 `bellwether_name`, `bellwether_z_score`, `internal_spread` (Task 5)
- Produces: `<Bellwether group={group} />`

표시 규칙은 D1 Option A를 따른다.

- 문구: `Bellwether: 삼성전자 Z -0.23` (스펙 형식 그대로)
- 색: `bellwether_z_score > 0`이면 `text-warn`(빨강), `< 0`이면 `text-accent`(파랑), `null`이면 `text-zinc-300`
- 툴팁(`title`): 지표 설명 문구 + 현재 상태 한 줄
- 위치: `Lag 국내` 티커 행 바로 아래. 국내 종목 내부 관계를 설명하는 값이라 그 옆에 두는 게 읽는 순서에 맞다.

- [ ] **Step 1: 컴포넌트 생성**

`frontend/src/Bellwether.jsx`:

```jsx
// Bellwether(RS 1등)와 나머지 평균의 괴리(internal Z), 그리고 Top Pick(시총 1등).
// internal_spread = rest_index - bellwether_index 이므로 음수일수록 주도주만 앞서간 상태다.
// 색은 카드 상단 Z-Score와 같은 규칙(양수 빨강 / 음수 파랑)을 쓴다.
const TOOLTIP = '주도주보다 나머지 종목이 덜 오름 = 추격 매수 기회'
const THRESHOLD = 1.5

function toneOf(z) {
  if (z === null || z === undefined) return 'text-zinc-300'
  return z > 0 ? 'text-warn' : 'text-accent'
}

function stateOf(z) {
  if (z === null || z === undefined) return '내부 괴리 산출 불가'
  if (z <= -THRESHOLD) return '주도주만 앞서감, 나머지 따라잡기 여지'
  if (z >= THRESHOLD) return '나머지가 주도주보다 앞섬, 순환매 확산'
  return '내부 괴리 정상 범위'
}

export default function Bellwether({ group }) {
  const {
    bellwether_name: name,
    bellwether_rs: rs,
    bellwether_z_score: z,
    internal_spread: spread,
    top_pick_name: topPick,
  } = group
  if (!name) return null

  const hasZ = z !== null && z !== undefined
  const hasSpread = spread !== null && spread !== undefined
  const detail = hasSpread
    ? `${TOOLTIP} · internal spread ${spread > 0 ? '+' : ''}${spread.toFixed(2)} · ${stateOf(z)}`
    : TOOLTIP

  return (
    <div className="tnum flex flex-wrap gap-x-3 gap-y-1 text-xs leading-5 text-zinc-400">
      <p title={detail}>
        Bellwether: <span className="text-zinc-600">{name}</span>{' '}
        <span className={toneOf(z)}>
          {hasZ ? `Z ${z > 0 ? '+' : ''}${z.toFixed(2)}` : 'Z n/a'}
        </span>
      </p>
      {topPick && (
        <p title={`시가총액 1위 종목 · RS 1위(Bellwether) 기준과 별개`}>
          Top Pick: <span className="text-zinc-600">{topPick}</span>
        </p>
      )}
      {rs !== null && rs !== undefined && (
        <p className="text-zinc-300" title="Bellwether의 최근 6개월 상대강도 (기준일 100)">
          RS {rs.toFixed(1)}
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: `App.jsx`에 연결**

`import CouplingMeter from './CouplingMeter.jsx'` 아래에 추가:

```jsx
import Bellwether from './Bellwether.jsx'
```

`GroupCard`의 `Lag 국내` `TickerRow` 바로 뒤(같은 `flex flex-col gap-5` div 안)에 추가:

```jsx
        <Bellwether group={group} />
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 `dist/` 생성

- [ ] **Step 4: 브라우저 확인**

Run: `cd frontend && npm run dev` 후 `http://localhost:5173`

확인할 것:

1. 카드마다 `Lag 국내` 아래에 `Bellwether: <종목명> Z <값>`과 `Top Pick: <종목명>`이 보인다
2. 양수 Z는 빨강, 음수 Z는 파랑
3. Bellwether 줄에 마우스를 올리면 툴팁에 "주도주보다 나머지 종목이 덜 오름 = 추격 매수 기회"가 뜨고, Top Pick 줄에는 "시가총액 1위 종목"이 뜬다
4. Bellwether와 Top Pick이 같은 그룹에서도 두 줄이 각각 정상 표시된다 (같은 이름이 두 번 나오는 것은 의도된 동작)
5. 폭 375px로 줄이면 세 항목이 줄바꿈되고, 카드 밖으로 넘치거나 다른 요소와 겹치지 않는다

- [ ] **Step 5: Commit**

```bash
git add frontend/src/Bellwether.jsx frontend/src/App.jsx
git commit -m "feat(ui): show bellwether internal z-score on group cards"
```

---

## Task 7: README 문서화

**Files:**
- Modify: `README.md` ("계산 방식" 절, "1. 파이썬 데이터 수집" 절)

- [ ] **Step 1: 계산 방식에 항목 추가**

"계산 방식" 절의 4번 항목 다음에 추가:

```markdown
5. 국내(lag) 종목에서 두 종목을 따로 뽑는다. 최근 6개월 상대강도(RS) 1등이
   `bellwether_ticker`(주도주), 시가총액 1등이 `top_pick_ticker`(대장주)다.
   두 선정은 서로 독립이라 같은 종목일 수도 있다. `bellwether_index`는 RS 1등
   종목만 100 정규화한 지수, `rest_index`는 그 종목을 뺀 나머지 평균이다.
   Top Pick은 표시 전용이고 인덱스 계산에는 관여하지 않는다.
6. `internal_spread = rest_index - bellwether_index`이고 같은 20일 Z-Score로
   `bellwether_z_score`를 낸다. 음수일수록 주도주만 앞서간 상태이고,
   `|internal Z| >= 1.5`이면 `bellwether_alert: true`.
   국내 종목끼리의 관계이므로 해외-국내 커플링 등급으로 게이팅하지 않는다.
```

- [ ] **Step 2: 테스트 실행 방법 문서화**

"## 1. 파이썬 데이터 수집" 절 끝에 추가:

```markdown
계산 로직 단위 테스트는 네트워크 없이 돈다.

    pip install -r requirements-dev.txt
    python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document bellwether signal"
```

---

## 최종 검증

- [ ] `.venv/bin/python -m pytest tests/ -v` -> 17 passed
- [ ] `.venv/bin/python peer_tracker.py` -> 32개 그룹 전부 `bellwether_name` 채워짐, `top_pick_name`도 채워짐, 기존 `zscore`는 실행 전과 동일
- [ ] `cd frontend && npm run build` -> 성공
- [ ] `git status` -> 계획에 없는 파일 변경 없음 (`peer_tracker_backup.py`, `frontend/src_backup/`은 그대로)

## 자기 검토 결과

스펙 커버리지

- 1번 Bellwether = RS 1등 -> Task 3 (`select_bellwether`)
- 1번 Top Pick = 시총 1등, 따로 표시 -> Task 3 (`select_top_pick`) + Task 4(시총 조회) + Task 6(카드 표시)
- 2번 `bellwether_index`(RS 1등 단독 100 정규화) / `rest_index`(나머지 평균) -> Task 5 (`bellwether_split`)
- 3번 `internal_spread` + 20일 Z-Score -> Task 5 (부호는 D1에서 결정)
- 4번 JSON 필드 + alert -> Task 5 (D3에 따라 `bellwether_alert` 별도 필드)
- 5번 프론트 표시 + 색 + 툴팁 -> Task 6

미결 사항

- D1(부호와 색 의미 충돌)은 승인이 필요하다. Option B를 고르면 Task 5의 `internal = rest_index - bell_index` 한 줄과 Task 6의 라벨만 뒤집는다.
- D2(`lag_index`를 주도주 제외로 바꾸지 않음), D3(alert 필드 분리), D4(시총 조회로 실행 시간 2~3분 증가), D5(두 라벨이 같은 종목일 수 있음)는 이 계획의 기본값이다. 다르게 원하면 알려주면 된다.

타입 일관성

- `relative_strength` / `select_bellwether` / `bellwether_split`은 `lag_frame.loc[common]`(컬럼=티커, 인덱스=거래일)만 받는다. `select_top_pick`은 프레임이 아니라 `dict[str, float | None]`만 받는다. Task 5의 호출부가 각각 이 형태를 넘긴다.
- `rolling_zscore`는 Task 2에서 정의되고 Task 5에서 그대로 재사용된다.
- JSON 필드명은 스펙의 `bellwether_name`, `bellwether_z_score`, `internal_spread`를 그대로 쓰고, 추가 필드는 `bellwether_rs` / `top_pick_ticker` / `top_pick_name`이다. `Bellwether.jsx`가 같은 이름으로 읽는다.
