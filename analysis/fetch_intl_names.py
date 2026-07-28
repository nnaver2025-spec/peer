"""해외 티커 종목명 수집 (일회성 유틸).

일본(.T) / 대만(.TW) / 홍콩(.HK) / 중국(.SS) 등은 티커가 숫자라 화면에서
`285A.T`처럼 보여 어떤 회사인지 알 수 없다. yfinance 조회명을 받아
intl_names.json으로 저장하고, 이미 손으로 확정한 이름은 그대로 유지한다.

미국/유럽 티커(AAPL, RHM.DE)는 티커 자체가 식별 가능하므로 건드리지 않는다.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from peer_tracker import INTL_NAMES  # noqa: E402
from sheet_groups import SHEET_GROUPS  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "intl_names.json"

# 숫자로 시작하는 아시아권 티커만 대상으로 한다. 알파벳 티커는 이미 읽을 수 있다.
TARGET = re.compile(r"^\d[\dA-Z]*\.(T|TW|HK|SS|SZ)$")

# 법인 형태 접미사. 카드/표에서 폭을 잡아먹고 식별에 도움이 되지 않는다.
# `Group`과 `Holdings`는 제거하지 않는다. SoftBank Corp.(통신)과
# SoftBank Group Corp.(지주)처럼 그 단어가 서로 다른 상장사를 가르기 때문이다.
SUFFIXES = re.compile(
    r",?\s*("
    r"Company Limited|Co\.,?\s*Ltd\.?|Co\.,?\s*Inc\.?|Co\.?\s*Limited|"
    r"Corporation|Incorporated|Limited|Corp\.?|Ltd\.?|Inc\.?|"
    r"PLC|S\.A\.|N\.V\.|AG|SE"
    r")$",
    re.IGNORECASE,
)


# 모음이 없는 짧은 토큰은 약어로 본다(NTT, CSSC, LG). 발음 가능한 단어는 Title Case로.
VOWELS = set("AEIOU")


def _is_acronym(token: str, solo: bool = False) -> bool:
    """대문자를 유지할 토큰인지 판단한다.

    모음이 없으면(NTT, CSSC) 확실한 약어다. 모음이 있어도 회사명이 그 토큰
    하나뿐이고 4글자 이하면(AGC, ZTE, TDK) 약어로 본다. Sony/Hoya 같은
    발음 가능한 사명은 5글자 이상이라 이 규칙에 걸리지 않는다.
    """
    letters = [c for c in token if c.isalpha()]
    if not letters:
        return True
    if len(letters) <= 2:
        return True
    if not (set(letters) & VOWELS):
        return len(letters) <= 5
    return solo and len(letters) <= 4


def tidy(name: str) -> str:
    """법인 접미사를 걷어내고 표시용으로 다듬는다.

    shortName은 전부 대문자로 오는 경우가 많아(KIOXIA HOLDINGS CORPORATION)
    Title Case로 낮춘다. 모음 없는 짧은 토큰(NTT, CSSC)은 약어로 보고 유지한다.
    """
    cleaned = name.strip()
    # 접미사가 겹쳐 붙는 경우가 있어 더 줄지 않을 때까지 반복한다.
    while True:
        stripped = SUFFIXES.sub("", cleaned).strip().rstrip(",")
        if stripped == cleaned or not stripped:
            break
        cleaned = stripped

    if cleaned.isupper():
        words = cleaned.split()
        solo = len(words) == 1
        cleaned = " ".join(
            w if _is_acronym(w, solo=solo) else w.capitalize() for w in words
        )
    return cleaned


def main() -> None:
    tickers: list[str] = []
    for cfg in SHEET_GROUPS.values():
        tickers += cfg["lead"] + cfg["lag"]
    targets = [t for t in dict.fromkeys(tickers) if TARGET.match(t)]
    print(f"대상 해외 티커 {len(targets)}개 (기존 매핑 {len(INTL_NAMES)}개)")

    names = dict(INTL_NAMES)
    fetched = 0
    for t in targets:
        if t in names:
            continue
        try:
            info = yf.Ticker(t).info
            # 285A.T처럼 longName이 비고 shortName만 오는 종목이 있다.
            raw = info.get("longName") or info.get("shortName")
        except Exception as exc:
            print(f"  [warn] {t} 조회 실패: {type(exc).__name__}")
            raw = None
        time.sleep(0.15)

        if raw and not raw.startswith(t):
            names[t] = tidy(raw)
            fetched += 1
            print(f"  {t:10} {names[t]}")
        else:
            print(f"  [warn] {t} 이름 조회 실패")

    OUT.write_text(
        json.dumps(names, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"\n신규 {fetched}개 수집, 총 {len(names)}개 -> {OUT}")


if __name__ == "__main__":
    main()
