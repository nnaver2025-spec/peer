# 통합 공포탐욕(FOMO) 지표 — 구현 계획

**Goal:** 8개 주식 커뮤니티에서 게시글 제목을 모아 종목별 FOMO 점수(0~100)를 계산하고, ①CLI 단발 조회와 ②대시보드의 새 탭 두 경로로 볼 수 있게 한다.

**Tech Stack:** Python 3.14(리포 `.venv`), `requests` + `cloudscraper`, `beautifulsoup4` + `lxml`, `FinanceDataReader`(종목명 -> 6자리 티커), `ThreadPoolExecutor`. 프론트는 기존 React 19 + Vite 8 + Tailwind 4.

> 검토용 문서다. 승인 전에는 코드를 쓰지 않는다.

---

## 0. 사전 실측 (2026-07-28, 실제 요청으로 확인)

8개 소스를 직접 호출해 응답 코드, 인코딩, 셀렉터, 페이지 파라미터를 확인했다. "제목 수"는 검색어 `삼성전자` 1페이지 파싱 결과다.

| 소스 | URL 패턴 | 페이지 | 셀렉터 | 인코딩 | 실측 |
|---|---|---|---|---|---|
| 네이버 종목토론실 | `finance.naver.com/item/board.naver?code=005930&page=N` | `page` | `td.title a[href*="board_read.naver"]` 의 `title` 속성 | UTF-8 | 200, 20개 |
| 디시 한국 주식 | `gall.dcinside.com/mgallery/board/lists/?id=krstock&s_type=search_subject&s_keyword=..&page=N` | `page` | `td.gall_tit.ub-word a[href*="no="]` | UTF-8 | 200, 19개 |
| 디시 미국 주식 | 위와 동일, `id=stockus` | `page` | 동일 | UTF-8 | 200, 15개 |
| 디시 주식 | `gall.dcinside.com/board/lists/?id=neostock&..` (일반 갤러리) | `page` | 동일 | UTF-8 | 200, 8개 |
| 디시 실전주식투자 | `mgallery`, `id=jusik` | `page` | 동일 | UTF-8 | 200, 9개 |
| 아카라이브 주식 | `arca.live/b/stock?target=title&keyword=..&p=N` | `p` | `div.list-table a.vrow` 에서 `notice` 제외 -> `span.vcol.col-title` | UTF-8 | 200, 45개 |
| 에펨코리아 주식 | `www.fmkorea.com/search.php?mid=stock&search_target=title&search_keyword=..&page=N` | `page` | `td.title a.hx` | UTF-8 | 200, 20개 |
| 뽐뿌 증권포럼 | `www.ppomppu.co.kr/zboard/zboard.php?id=stock&page=N&divpage=1&search_type=sub_memo&keyword=..` | `page` | `a.baseList-title span` | **EUC-KR** | 200, 20개 |

검증된 사실 몇 가지.

- `cloudscraper.create_scraper(browser={'browser':'chrome','platform':'darwin'})` 로 디시/아카/에펨/뽐뿌 4개 도메인 모두 200. Selenium 불필요
- 에펨은 `index.php?mid=stock&search_keyword=..` 요청 시 `search.php`로 302 리다이렉트된다. 처음부터 `search.php`를 호출한다
- 종목 1개를 8소스 병렬 수집하는 데 **2.3초** 걸렸다(워커 8). 30종목이면 순차로 약 80초
- 검색 필터는 정상 작동한다. 무의미한 문자열로 검색하면 에펨/뽐뿌 모두 0건을 돌려준다
- `FinanceDataReader==0.9.202`가 `pandas 3.0.5`에서 동작하고 `삼성전자 -> 005930`, `한화에어로스페이스 -> 012450` 변환된다

---

## 1. 두 개의 진입점

대시보드 탭에서 보려면 브라우저가 읽을 JSON이 필요하다. 브라우저는 파이썬을 실행할 수 없으니, 기존 `peer_tracker.py` -> `dashboard_data.json` -> React 와 같은 파이프라인을 그대로 따른다.

```
                         fomo_core.py  (수집 + 파싱 + 점수)
                          /                        \
          fomo_scanner.py                          fomo_watch.py
     python fomo_scanner.py 삼성전자          크론이 30분마다 호출
          -> 콘솔 출력                    -> frontend/public/fomo_data.json
                                                       |
                                              대시보드 "여론" 탭
```

감시 대상은 **각 그룹의 Bellwether(주도주)** 다. 현재 32개 그룹에서 중복 제거하면 30종목이다.
Z-Score 탭이 이미 주도주를 뽑아두었으니 같은 종목의 여론을 옆에 두는 게 자연스럽고, 대상 목록을 따로 관리할 필요도 없다.

검색형(입력창에 종목을 치면 즉시 스캔)을 택하지 않은 이유는 로컬 API 서버가 필요해서다. 지금 리포는 정적 JSON + Vite뿐이고, 인증 없는 로컬 포트를 여는 선택도 따라온다. 단발 조회는 CLI가 담당한다.

---

## 검토 필요 결정사항

### D1. 요청받은 디시 갤러리 ID 4개 중 3개가 존재하지 않는다 — **승인 필요**

스펙의 ID를 그대로 호출한 결과:

| 요청 ID | 결과 |
|---|---|
| `stock_new` | 200이지만 **"201305~201505 주식 갤러리"** 아카이브. 최신 글이 `2015-05-29` |
| `us_stock` | 404 |
| `stocks` | 404 |
| `stock_invest` | 404 |

`search.dcinside.com` 갤러리 검색으로 살아있는 갤러리를 찾아 최신 글 날짜까지 확인했다.

Option A (채택): 의도한 4개 성격에 대응하는 활동 갤러리로 교체한다.

| 대체 ID | 갤러리명 | 타입 | 검색 결과 최신 글 |
|---|---|---|---|
| `krstock` | 한국 주식 | 마이너 | `2026-07-28 17:22` |
| `stockus` | 미국 주식 | 마이너 | `2026-07-28 16:40` |
| `neostock` | 주식 | 일반(`board`) | `2026-07-27 19:16` |
| `jusik` | 실전주식투자 | 마이너 | `2026-06-26 09:51` |

`neostock`만 일반 갤러리라 `board/lists`를 쓴다. `mgallery`로 잘못 호출하면 디시는 `location.replace` 스크립트만 돌려주므로 타입을 소스 정의에 하드코딩하고, 응답에 `location.replace`가 있으면 실패로 처리한다.

Option B: 요청 ID 유지. 4개 중 3개가 항상 실패로 찍히고 `stock_new`은 11년 전 글로 지표를 오염시킨다. 권하지 않는다.

### D2. `+2점 / -2점` 표기는 점수식과 맞지 않는다 — 수식을 따른다

스펙에 탐욕 `+2점`, 공포 `-2점`이라 적혀 있지만 실제 계산식은 `50 + ((greed - fear) / total) * 50` 으로 가중치 2가 등장하지 않는다. 둘을 동시에 만족시킬 수 없어 **명시된 수식을 그대로 구현**하고 `+2/-2`는 방향 표시로 읽는다. 가중치를 실제로 곱하면 스펙 4번 구간표의 스케일과 어긋난다.

### D3. 네이버 종목토론실은 제목 검색이 없다

이미 종목별 게시판이므로 검색어를 URL에 넣지 않고 최신 3페이지를 통째로 받는다. 검색어는 티커 변환에만 쓴다. 스펙과 같은 동작이다.

### D4. 티커 변환 실패 시 네이버만 skip

정확 일치 -> 공백 제거 후 일치 순으로 찾고, 없으면 실패로 본다. 부분 일치 추측은 하지 않는다(엉뚱한 종목의 토론실을 긁는 게 더 나쁘다). 이 경우 `[실패] 네이버 증권 종목토론실 - 티커 변환 실패`를 찍고 나머지 7개는 진행한다.

### D5. 뽐뿌는 본문 검색이라 정확도가 낮다 — 그대로 쓰되 표시한다

뽐뿌의 `search_type=sub_memo`는 제목+본문을 검색한다. 실측에서 `주성엔지니어링`으로 검색했을 때 제목에 종목명이 없는 글(`코스닥 900을 찍을려면 어떻게 해야 할까요??`)이 섞였다. 제목만 검색하는 파라미터가 없어 그대로 쓰고, 대신 **제목에 검색어가 없는 글은 집계에서 제외**한다. 다른 소스는 이미 제목 검색이라 이 필터가 무해하다. 네이버는 종목 전용 게시판이므로 필터를 적용하지 않는다.

### D6. 키워드 카운팅 단위: 제목당 총 출현 횟수

`str.count()`로 센다. 한 제목에 `가즈아 가즈아`면 2회다. 스펙의 "출현 빈도"를 그대로 읽었다. 제목당 1회로 바꾸려면 `count` -> `in` 한 줄 차이다.

### D7. 제목 정규화

세 가지만 정리하고 그 이상 손대지 않는다.
- 아카라이브: 말머리 이모지(`💬`, `📰뉴스`)와 댓글 수 접미(`[5]`) 제거
- 에펨: 검색어가 `<strong>`으로 감싸져 있어 `get_text('')`로 붙여 읽고 공백 축약
- 공통: 앞뒤 공백 제거, 연속 공백 1칸, HTML 엔티티는 bs4가 처리

### D8. 중복 제거는 소스 안에서만

페이지 간 중복(글이 밀리면 2페이지 첫 글이 1페이지 마지막과 겹침)은 제거한다. 소스 간 중복은 제거하지 않는다. 서로 다른 커뮤니티의 같은 제목은 별개 여론이다.

### D9. 병렬 구조와 크론 부하 — **부하가 커지는 지점이라 확인 부탁**

CLI(종목 1개)는 `ThreadPoolExecutor(max_workers=8)`에 소스 단위로 넘긴다. 한 소스의 2~3페이지는 같은 도메인 연속 호출이라 스레드 안에서 순차 처리하고 사이에 0.3초 간격을 둔다. 실측 2.3초.

감시 모드(30종목)는 **종목을 순차로, 소스만 병렬**로 돈다. 종목 사이에 2초를 둔다. 30종목 x (2.3초 + 2초) = 약 130초, 요청 수는 30 x 17 = 510회다. 종목까지 병렬로 돌리면 같은 도메인에 초당 수십 건이 몰려 차단을 부른다.

`cloudscraper` 세션은 스레드 안전을 보장하지 않으므로 스레드마다 새 스크레이퍼를 만든다.

### D10. 크론은 기존 30분 주기에 얹지 않고 별도 2시간 주기로 둔다

`peer_tracker.py`는 25초에 끝나지만 FOMO 감시는 130초가 걸리고 커뮤니티 서버를 두드린다. 30분마다 510회 요청은 과하다. 여론은 주가만큼 빨리 변하지 않으니 **2시간 주기 별도 launchd 에이전트**(`com.peer.fomo.update`)로 분리한다. 기존 `update.sh`와 plist는 건드리지 않는다.

### D11. 점수 이력은 최근 60포인트만 남긴다

`peer_tracker.py`의 `HISTORY_POINTS = 60`과 같은 방식이다. 실행할 때 기존 `fomo_data.json`을 읽어 종목별 `history`에 `{ts, score}`를 append하고 60개로 자른다. 2시간 주기면 5일치다. 이력이 있어야 탭에서 스파크라인으로 여론 변화를 볼 수 있다. 첫 실행은 이력 1개로 시작한다.

---

## 파일 구조

| 파일 | 역할 | 변경 | 대략 |
|---|---|---|---|
| `fomo_core.py` | 소스 8개 정의, 요청/파싱, 티커 변환, 키워드 카운트, 점수 계산 | 생성 | 260줄 |
| `fomo_scanner.py` | CLI 진입점. 종목 1개 스캔 후 콘솔 출력 | 생성 | 120줄 |
| `fomo_watch.py` | 감시 모드. Bellwether 30종목 스캔 -> `fomo_data.json` | 생성 | 90줄 |
| `tests/test_fomo.py` | 네트워크 없는 단위 테스트 | 생성 | 130줄 |
| `frontend/src/FomoTab.jsx` | 여론 탭 본문(종목 테이블) | 생성 | 130줄 |
| `frontend/src/FomoGauge.jsx` | 0~100 게이지 바 + 구간 색 | 생성 | 50줄 |
| `frontend/src/fomo.js` | 구간 판정, 색 토큰, 라벨 (`zone.js`와 같은 역할) | 생성 | 45줄 |
| `frontend/src/App.jsx` | 탭 전환 상태 + 상단 탭 UI + 조건 렌더 | 수정: 약 40줄 | |
| `requirements.txt` | 의존성 4개 핀 추가 | 수정 | |
| `scripts/fomo_update.sh`, `scripts/com.peer.fomo.update.plist` | 2시간 주기 갱신 | 생성 | |
| `README.md`, `scripts/README.md` | 실행법과 설치법 | 수정 | |

파이썬을 3개로 나누는 이유는 경계가 다르기 때문이다. `fomo_core.py`가 유일하게 사이트 구조를 아는 파일이고(사이트가 바뀌면 여기만 고친다), `fomo_scanner.py`와 `fomo_watch.py`는 출력 형태만 다른 얇은 껍데기다. 프론트는 `Sparkline.jsx` / `CouplingMeter.jsx` / `zone.js`가 이미 같은 방식으로 분리돼 있어 그 관례를 따랐다.

`peer_tracker.py`, `sheet_groups.py`, 기존 `dashboard_data.json` 생성 경로는 건드리지 않는다.

---

## `fomo_data.json` 스키마

```json
{
  "generated_at": "2026-07-28 18:40:12",
  "interval_hours": 2,
  "sources": [
    { "key": "naver", "label": "네이버 증권 종목토론실" }
  ],
  "stocks": [
    {
      "key": "036930.KQ",
      "name": "주성엔지니어링",
      "ticker": "036930",
      "group_desc": "전공정 장비",
      "sector": "반도체",
      "score": 57.6,
      "zone": "neutral",
      "total_posts": 79,
      "greed_total": 23,
      "fear_total": 11,
      "greed_counts": { "가즈아": 8, "진입": 5 },
      "fear_counts": { "고점": 4, "손절": 3 },
      "per_source": [
        { "key": "naver", "count": 32, "error": null },
        { "key": "jusik", "count": 0, "error": "차단됨" }
      ],
      "history": [{ "ts": "2026-07-28 16:40", "score": 55.2 }]
    }
  ]
}
```

`key`는 Bellwether 티커를 그대로 쓴다. Z-Score 탭의 `bellwether_ticker`와 같은 값이라 두 탭을 연결할 때 조인 키가 된다.

---

## Task 1: 의존성과 티커 변환

**Files:** `requirements.txt`, `.gitignore`, `fomo_core.py`

- `requirements.txt`에 `cloudscraper==1.2.71`, `beautifulsoup4==4.15.0`, `lxml==6.1.1`, `finance-datareader==0.9.202` 추가
- `resolve_ticker(name) -> str | None`
  - KRX 목록을 `Path(__file__).parent / ".cache" / "krx_listing.json"` 에 캐시. 24시간 이내면 재사용. 크론이 매번 2873행을 내려받지 않게 한다
  - `.gitignore`에 `.cache/` 추가
  - 정확 일치 -> 공백 제거 일치 순. 실패 시 `None`
  - FDR import 자체가 실패해도 `None`을 돌려주고 프로그램은 계속 진행

**verify:** `.venv/bin/python -c "from fomo_core import resolve_ticker as r; print(r('삼성전자'), r('한화에어로스페이스'), r('없는종목'))"` -> `005930 012450 None`

## Task 2: 점수 계산 순수 함수

**Files:** `fomo_core.py`, `tests/test_fomo.py`

- `GREED_KEYWORDS` / `FEAR_KEYWORDS` 튜플 (스펙의 10개씩 그대로)
- `count_keywords(titles) -> KeywordStats(greed_total, fear_total, greed_counts, fear_counts)`. dict는 출현 내림차순, 0회 제외
- `fomo_score(greed, fear, total) -> float` : 스펙 수식 + 0~100 클램프. `total=0`이면 50.0
- `interpret(score) -> (zone_key, label)` : 5구간
- `gauge(score) -> str` : CLI용 눈금 막대. 폭 고정

**verify:** `pytest tests/test_fomo.py -v`. 케이스:
- 빈 리스트 -> 50.0 중립
- 탐욕만 -> 100.0 클램프 / 공포만 -> 0.0 클램프
- 탐욕 23 / 공포 11 / 79개 -> `50 + (12/79)*50 = 57.59...` (스펙 예시 57.6과 일치)
- 구간 경계 20/21/40/41/60/61/80/81 라벨
- `가즈아 가즈아` -> 2회 (D6)
- 게이지 길이가 점수와 무관하게 고정
- 정규화: 아카 말머리/댓글수 제거, 공백 축약, 제목 필터(D5)

## Task 3: 소스 정의와 파싱

**Files:** `fomo_core.py`

- `Source` dataclass: `key, label, url_template, page_param, pages, selector, encoding, use_cloudscraper, needs_ticker, kind`
- 소스 8개를 `SOURCES` 상수로 선언. 0절 표의 값을 그대로 넣는다
- `fetch_titles(source, keyword, ticker) -> list[str]`
  - 세션: `use_cloudscraper`면 스크레이퍼, 아니면 `requests.Session()`. 스레드마다 새로 만든다
  - 헤더: 크롬 데스크톱 `User-Agent`, `Accept-Language: ko-KR`, 소스별 `Referer`
  - 뽐뿌는 검색어를 `quote(kw.encode('euc-kr'))`, 응답 `encoding='euc-kr'`
  - `raise_for_status()` -> 파싱 -> D7 정규화 -> D5 제목 필터 -> D8 중복 제거
  - 페이지 사이 0.3초. 디시 응답에 `location.replace`면 `잘못된 갤러리 타입` 예외
  - 파싱 0건은 예외가 아니라 빈 리스트다(검색 결과 없음은 실패가 아니다)
- 추출 함수 4개: `_titles_naver`(title 속성), `_titles_dcinside`, `_titles_arca`, `_titles_css`(에펨/뽐뿌 공용)
- `scan(keyword, ticker) -> ScanResult(titles, per_source)` : 소스 8개 병렬 + 오류 매핑
  - `HTTPError 403/503` -> `차단됨`, `Timeout` -> `응답 없음`, `ConnectionError` -> `연결 실패`, 그 외 예외 클래스명
  - `SOURCES` 순서로 결과를 정렬해 출력 순서가 실행마다 바뀌지 않게 한다
  - 소스당 타임아웃 15초

**verify:** 8개 소스를 하나씩 호출해 제목 3건과 개수를 출력하고 0절 실측치와 자릿수를 비교

## Task 4: CLI

**Files:** `fomo_scanner.py`

- `sys.argv[1]` 없으면 사용법 출력 후 `exit(2)`
- 전 소스 실패면 실패 목록만 찍고 `exit(1)`. 1개라도 성공하면 정상 출력 후 `exit(0)`
- 출력은 스펙 형식 그대로. 헤더 `═`, 구분선 `─`
- 한글 정렬은 `unicodedata.east_asian_width`로 표시 폭을 계산해 패딩한다. `len()`으로는 개수 열이 어긋난다
- 성공 `✅ 이름  N개`, 실패 `⚠️ 이름  사유 (skip)`
- 키워드는 출현 순 상위 6개까지 `가즈아(8) 진입(5)` 한 줄
- 표준 라이브러리만 쓴다. `rich`가 venv에 있지만 출력 형식이 스펙에 고정돼 이득이 없다
- 경로는 전부 `Path(__file__).parent` 기준

**verify:**
- `.venv/bin/python fomo_scanner.py 삼성전자` -> 8소스 결과 + 점수
- `cd / && <절대경로>/.venv/bin/python <절대경로>/fomo_scanner.py 삼성전자` -> 동일 동작 (크론 조건)
- 인자 없음 -> 사용법 + exit 2
- `AAPL` -> 네이버만 `티커 변환 실패`, 나머지 진행

## Task 5: 감시 모드와 JSON 출력

**Files:** `fomo_watch.py`

- `dashboard_data.json`을 읽어 `bellwether_ticker` / `bellwether_name` / `desc` / `sector`를 뽑고 티커로 중복 제거 -> 30종목
- 파일이 없으면 `peer_tracker.py를 먼저 실행하세요` 안내 후 `exit(1)`
- 종목 순차 + 소스 병렬(D9), 종목 사이 2초
- 기존 `fomo_data.json`을 읽어 종목별 `history` append 후 60개로 자름(D11). 파일이 깨져 있으면 이력 없이 새로 시작
- 쓰기는 임시 파일에 쓴 뒤 `os.replace`로 원자적 교체. 프론트가 반쯤 쓰인 JSON을 읽는 것을 막는다
- 진행 로그는 한 줄씩(`[12/30] 주성엔지니어링 57.6`). 크론 로그에서 어디까지 갔는지 보이게

**verify:**
- `.venv/bin/python fomo_watch.py --limit 3` -> 3종목만 스캔, JSON 생성 확인
- 전체 실행 -> 30종목, 130초 내외, `python -c "import json;json.load(...)"` 로 스키마 확인
- 두 번 실행 -> `history` 길이가 1에서 2로 늘어남

## Task 6: 대시보드 탭

**Files:** `frontend/src/App.jsx`, `FomoTab.jsx`, `FomoGauge.jsx`, `fomo.js`

- `App.jsx`에 `tab` 상태 추가(`'spread' | 'fomo'`). URL 쿼리 `?tab=fomo`와 `localStorage('peer:tab')`에 유지한다. 기존 `?view=`/`#해시` 관례를 그대로 따른다
- 헤더 아래에 탭 두 개(`괴리`, `여론`). 기존 사이드바 필터/섹터와 검색 바는 `spread` 탭에서만 보인다. FOMO 탭은 자체 정렬 + 검색을 쓴다
- `fomo_data.json`은 FOMO 탭을 처음 열 때 fetch한다(초기 로딩에 두 파일을 동시에 받지 않게)
- `FomoTab.jsx` 테이블 열: 종목 / 그룹 / 점수(게이지 포함) / 구간 / 수집 수 / 탐욕:공포 / 추이. `GroupTable.jsx`의 `COLUMNS` + `HeaderCell` 정렬 패턴을 그대로 재사용
- 추이는 기존 `Sparkline.jsx`를 쓴다. 다만 지금은 `points[].spread`를 하드코딩해 읽으므로, `valueKey` prop을 기본값 `'spread'`로 추가해 FOMO는 `'score'`를 넘긴다. 기존 호출부는 안 바뀐다
- `fomo.js`는 5구간 -> 색 토큰 매핑. 기존 팔레트만 쓴다: 극단 공포/공포는 `text-accent`(파랑, 언더슈팅=기회와 같은 의미), 중립은 `text-ink`, 탐욕/극단 탐욕은 `text-warn`(빨강). 새 색을 만들지 않는다
- `fomo_data.json`이 없으면 탭에 `python fomo_watch.py` 안내를 띄운다. Z-Score 탭의 에러 화면과 같은 형태
- 카드 안에 카드를 넣지 않고, 테이블은 기존 표와 같은 밀도로 둔다

**verify:** `cd frontend && npm run build` 성공. `npm run dev`로 탭 전환, 정렬, `?tab=fomo` 직접 접속, JSON 없을 때 안내 표시를 확인

## Task 7: 크론 연동

**Files:** `scripts/fomo_update.sh`, `scripts/com.peer.fomo.update.plist`, `scripts/README.md`

- `update.sh`의 구조(락 디렉터리, 로그 트림, `set -uo pipefail`, 절대경로 `PYTHON`)를 그대로 따르되 로그는 `~/.peer-cron/logs/fomo.log`, 락은 `fomo.lock`으로 분리
- plist는 `StartInterval` 7200, 라벨 `com.peer.fomo.update`. 기존 plist와 로그 파일을 공유하지 않는다
- macOS TCC 제약(Documents 안 스크립트를 launchd가 실행 못 함)이 그대로 적용되므로 `~/.peer-cron/`에 복사하는 방식도 동일하다. `scripts/README.md`에 절 추가
- **설치(`launchctl bootstrap`)는 실행하지 않는다.** 사용자 계정에 상시 에이전트를 등록하는 일이라 명령만 문서에 적어두고 실행은 맡긴다

**verify:** `bash -n scripts/fomo_update.sh`, `plutil -lint scripts/com.peer.fomo.update.plist`

## Task 8: 문서화

**Files:** `README.md`

- `## 3. FOMO 여론 지표` 절 추가: CLI 실행법, 감시 모드, 8개 소스, 점수 구간, 디시 갤러리 ID를 바꾼 이유(D1) 한 줄
- 기존 절 번호 체계(`## 1. 파이썬 데이터 수집`, `## 2. 프론트엔드 실행`)를 따른다

**verify:** `rg -n "FOMO" README.md`

---

## 최종 검증

- `.venv/bin/python -m pytest tests/ -v` -> 기존 17개 + 신규 FOMO 테스트 전부 통과
- `.venv/bin/python fomo_scanner.py 삼성전자` -> 8소스 중 6개 이상 성공, 점수 0~100
- `.venv/bin/python fomo_scanner.py 한화에어로스페이스` -> 티커 `012450` 변환, 정상 출력
- 리포 밖 cwd에서 절대경로 실행 -> 동일 동작
- `.venv/bin/python fomo_watch.py` -> 30종목, `fomo_data.json` 생성. 재실행 시 `history` 증가
- `cd frontend && npm run build` -> 성공
- `peer_tracker.py`는 실행하지 않는다(무관하고 2~3분 걸린다). `git status`로 `dashboard_data.json`이 안 건드려졌는지만 확인
- `git status` -> 계획에 없는 변경 없음. `peer_tracker_backup.py`, `frontend/src_backup/`은 그대로

## 자기 검토

스펙 커버리지

- 8개 소스 -> Task 3. 디시 ID는 D1 승인 필요
- 티커 변환 필수 사용 -> Task 1. pykrx가 아닌 FDR을 고른 이유: `pandas 3.0.5`에서 동작을 실측했고 HTTP 1회로 전체 목록을 받아 캐시하기 쉽다
- Selenium 미사용 -> `cloudscraper`만. 실측에서 4개 도메인 전부 200
- ThreadPoolExecutor -> Task 3(`scan`). 스레드별 세션 분리(D9)
- 페이지 수 -> 네이버 3, 나머지 2
- 점수식/구간/클램프 -> Task 2. `+2/-2`는 D2에서 수식 우선
- 사이트별 예외 처리, 1개만 성공해도 출력 -> Task 3 오류 매핑 + Task 4
- 출력 형식 -> Task 4 (한글 폭 보정 포함)
- 크론 견고성 -> Task 1(캐시), Task 4(절대경로/종료코드), Task 7(락/로그)
- 대시보드 탭 -> Task 5(JSON) + Task 6(UI)

미결 사항

- **D1(디시 갤러리 ID 교체)이 유일한 실질 승인 항목이다.** Option B를 고르면 Task 3의 `SOURCES` 4줄만 되돌린다
- D9/D10(크론 요청 부하와 2시간 주기)은 외부 서버를 두드리는 결정이라 짚어둔다. 주기를 늘리거나 감시 종목을 줄이길 원하면 알려주면 된다
- D2~D8, D11은 이 계획의 기본값이다
- 파일명을 `plan.md`가 아니라 `fomo_plan.md`로 둔 이유: 리포의 `plan.md`는 이미 완료된 Bellwether 계획이고 git에 추적 중이다. 덮어쓰길 원하면 그렇게 하겠다
