"""해외 종목명 정리(tidy) 테스트.

법인 접미사를 걷어내되 회사 식별에 필요한 부분은 남겨야 한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from fetch_intl_names import tidy


def test_strips_corporation_suffix():
    assert tidy("Tokyo Electron Limited") == "Tokyo Electron"


def test_strips_company_limited():
    assert tidy("Macronix International Co., Ltd.") == "Macronix International"


def test_titlecases_all_caps_shortname():
    assert tidy("KIOXIA HOLDINGS CORPORATION") == "Kioxia Holdings"


def test_keeps_acronyms_uppercase():
    # 모음 없는 짧은 토큰은 약어로 보고 대문자를 유지한다.
    assert tidy("NTT DATA GROUP CORPORATION") == "NTT Data Group"
    assert tidy("AGC INC") == "AGC"
    assert tidy("ZTE") == "ZTE"


def test_keeps_group_to_distinguish_listed_entities():
    # SoftBank Corp.(통신)과 SoftBank Group Corp.(지주)는 다른 상장사다.
    assert tidy("SoftBank Corp.") == "SoftBank"
    assert tidy("SoftBank Group Corp.") == "SoftBank Group"


def test_handles_stacked_suffixes():
    assert tidy("China CSSC Holdings Limited") == "China CSSC Holdings"


def test_strips_suffix_after_group():
    assert tidy("Sony Group Corporation") == "Sony Group"


def test_strips_comma_less_co_ltd():
    assert tidy("Ibiden Co.,Ltd.") == "Ibiden"


def test_strips_co_inc():
    assert tidy("Ajinomoto Co., Inc.") == "Ajinomoto"


def test_does_not_empty_out_suffix_only_name():
    # 접미사만 남는 경우 원문을 지키는 편이 빈 라벨보다 낫다.
    assert tidy("Limited") == "Limited"


def test_trims_whitespace():
    assert tidy("  Advantest Corporation  ") == "Advantest"


def test_long_name_stays_readable():
    got = tidy("Taiwan Semiconductor Manufacturing Company Limited")
    assert got == "Taiwan Semiconductor Manufacturing"
