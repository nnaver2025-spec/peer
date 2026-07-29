"""에펨코리아 통과용 쿠키 관리.

에펨은 Cloudflare가 아니라 자체 보안 시스템(openresty)을 쓴다. HTTP 430으로
보안 페이지를 주고, 그 안에서 WebAssembly 모듈(`/mc/mc.php`)이 서명을 만들어
`fm5`/`fm6` 쿠키를 심은 뒤 재요청해야 목록이 나온다. 쿠키 토큰은 HTML에 노출돼
있지만 그것만 심어도 통과하지 못한다(430 -> 429). wasm 실행이 실제 관문이다.

그래서 브라우저를 한 번만 띄워 쿠키를 받고, 이후 요청은 `requests`로 처리한다.
실측에서 이 쿠키로 68회 연속 요청이 전부 200이었다(1291건 수집, 64초).
브라우저는 쿠키가 없거나 만료됐을 때만 뜨므로 회차당 한 번, 3초 남짓이다.

Playwright가 설치돼 있지 않으면 조용히 포기하고 해당 소스만 건너뛴다.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote

_CACHE_PATH = Path(__file__).parent / ".cache" / "fmkorea_cookies.json"
# 쿠키 유효기간은 서버가 7일로 주지만 넉넉히 6시간마다 새로 받는다. 오래된 쿠키로
# 회차 중간에 막히면 그 회차 전체를 잃는다.
COOKIE_TTL_SEC = 6 * 60 * 60
# 쿠키 발급이 실패하면 이 시간 동안 브라우저를 다시 띄우지 않는다.
#
# IP가 차단되면(보안 페이지에 "차단 종류: 2") 브라우저로도 통과하지 못하고 5분 넘게
# 안 풀린다. 그 상태에서 종목마다 브라우저를 띄우면 회차가 몇 배로 늘어나기만 하고
# 차단을 더 길게 만든다. 실패를 기억해 그동안은 조용히 건너뛴다.
FAILURE_COOLDOWN_SEC = 30 * 60
_FAILURE_PATH = Path(__file__).parent / ".cache" / "fmkorea_blocked_at"
PROBE_KEYWORD = "삼성전자"
PROBE_URL = (
    "https://www.fmkorea.com/search.php?mid=stock&search_target=title"
    "&search_keyword={}&page=1"
)
ROW_SELECTOR = "td.title a.hx"
BROWSER_TIMEOUT_MS = 25_000


def _load_cached() -> dict[str, str] | None:
    if not _CACHE_PATH.exists():
        return None
    if time.time() - _CACHE_PATH.stat().st_mtime > COOKIE_TTL_SEC:
        return None
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _store(cookies: dict[str, str]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cookies), encoding="utf-8")
    except OSError:
        pass   # 캐시 쓰기 실패는 치명적이지 않다. 다음 회차에 다시 받는다.


def _in_cooldown() -> bool:
    if not _FAILURE_PATH.exists():
        return False
    return time.time() - _FAILURE_PATH.stat().st_mtime < FAILURE_COOLDOWN_SEC


def _mark_failure() -> None:
    try:
        _FAILURE_PATH.parent.mkdir(exist_ok=True)
        _FAILURE_PATH.touch()
    except OSError:
        pass


def _clear_failure() -> None:
    try:
        _FAILURE_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _fetch_with_browser(user_agent: str) -> dict[str, str] | None:
    """브라우저로 보안 검사를 통과하고 쿠키만 챙긴다."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    locale="ko-KR",
                    user_agent=user_agent,
                )
                page = context.new_page()
                page.goto(
                    PROBE_URL.format(quote(PROBE_KEYWORD)),
                    wait_until="domcontentloaded",
                )
                # 보안 페이지는 wasm 실행 후 스스로 재요청한다. 목록이 뜨면 통과다.
                page.wait_for_selector(ROW_SELECTOR, timeout=BROWSER_TIMEOUT_MS)
                return {c["name"]: c["value"] for c in context.cookies()}
            finally:
                browser.close()
    except Exception:
        return None


def get_cookies(user_agent: str, force: bool = False) -> dict[str, str] | None:
    """에펨 요청에 쓸 쿠키. 캐시가 살아 있으면 재사용한다."""
    if not force:
        cached = _load_cached()
        if cached:
            return cached

    # IP 차단 중이면 브라우저를 띄워도 소용없다.
    if _in_cooldown():
        return None

    cookies = _fetch_with_browser(user_agent)
    if cookies:
        _store(cookies)
        _clear_failure()
    else:
        _mark_failure()
    return cookies


def invalidate() -> None:
    """쿠키가 막히면 캐시를 버려 다음 시도에서 새로 받게 한다."""
    try:
        _CACHE_PATH.unlink(missing_ok=True)
    except OSError:
        pass
