"""관심종목 시트의 표 구조를 그대로 옮긴 Peer 그룹 정의.

출처: "희상 관심종목" 스프레드시트 (반도체 / 조선·방산·기계·로봇 /
AI인프라·화학·정유 / (광)통신·우주 / 증권·지주 / 화장품·식품·IP 탭).

시트는 국내 표와 해외 표를 따로 두고, 일부 표 우측에 "해외 OO Peer"로
연결 대상을 적어두었다. 여기서는 그 매핑을 lead/lag 쌍으로 정규화한다.
시트에서 셀이 잘려 티커를 확인할 수 없던 종목은 넣지 않았다.
"""

from __future__ import annotations

# 시트 표 이름 -> (섹터, 표시명, 해외 lead, 국내 lag)
SHEET_GROUPS: dict[str, dict[str, object]] = {
    # ===== 반도체 탭 =====
    "SEMI_DramNand": {
        "sector": "반도체",
        "desc": "DRAM/NAND",
        "lead": ["MU", "WDC", "STX", "SNDK", "285A.T", "2408.TW", "2344.TW", "2337.TW", "6770.TW"],
        "lag": ["005930.KS", "000660.KS"],
    },
    "SEMI_HbmPkg": {
        "sector": "반도체",
        "desc": "HBM/패키징 장비",
        "lead": ["6857.T", "6146.T", "6315.T", "TER"],
        "lag": [
            "042700.KS", "089030.KQ", "039200.KQ", "039440.KQ", "053610.KQ",
            "232140.KQ", "003160.KS", "079370.KQ", "036810.KQ", "322310.KQ",
            "086390.KQ", "098460.KQ",
        ],
    },
    "SEMI_Pcb": {
        "sector": "반도체",
        "desc": "PCB/기판",
        "lead": [
            "6981.T", "4062.T", "2802.T", "6976.T", "6762.T", "6971.T",
            "3037.TW", "3189.TW", "8046.TW", "2327.TW", "4958.TW", "2492.TW",
        ],
        "lag": ["009150.KS", "011070.KS", "007660.KS", "058470.KQ", "356860.KQ", "222800.KQ", "007810.KS", "440110.KQ"],
    },
    "SEMI_GlassSub": {
        "sector": "반도체",
        "desc": "유리기판",
        "lead": ["GLW", "5201.T", "7912.T", "7741.T", "5214.T"],
        "lag": ["011790.KS", "161580.KQ", "078150.KQ"],
    },
    "SEMI_Material": {
        "sector": "반도체",
        "desc": "반도체 소재",
        "lead": ["4063.T", "3436.T"],
        "lag": [
            "058470.KQ", "095340.KQ", "357780.KQ", "005290.KQ", "101160.KQ",
            "074600.KQ", "064760.KQ", "272290.KQ", "140860.KQ",
        ],
    },
    "SEMI_FrontEnd": {
        "sector": "반도체",
        "desc": "전공정 장비",
        "lead": ["ASML", "AMAT", "LRCX", "8035.T", "KLAC", "7735.T"],
        "lag": [
            "403870.KQ", "036930.KQ", "084370.KQ", "240810.KQ", "319660.KQ",
            "079370.KQ", "281820.KQ", "039440.KQ",
        ],
    },
    "SEMI_Ip": {
        "sector": "반도체",
        "desc": "반도체 IP/디자인",
        "lead": ["ARM", "RMBS", "3443.TW", "3661.TW"],
        "lag": ["399720.KQ", "200710.KQ", "394280.KQ", "432720.KQ", "445090.KQ"],
    },
    "SEMI_Analog": {
        "sector": "반도체",
        "desc": "아날로그 반도체",
        "lead": [
            "TXN", "ADI", "MCHP", "ON", "MPWR", "CRUS", "NXPI", "SWKS",
            "QRVO", "SLAB", "6723.T", "6758.T", "6963.T",
        ],
        "lag": [],
    },
    "SEMI_Cpu": {
        "sector": "반도체",
        "desc": "CPU",
        "lead": ["INTC", "AMD", "ARM"],
        "lag": [],
    },
    "SEMI_Eda": {
        "sector": "반도체",
        "desc": "EDA",
        "lead": ["SNPS", "CDNS"],
        "lag": [],
    },
    # ===== 조선 / 방산 / 기계 / 로봇 탭 =====
    "SHIP_Yard": {
        "sector": "조선",
        "desc": "조선",
        "lead": ["600150.SS", "HII", "7003.T", "7011.T", "7014.T", "FCT.MI"],
        "lag": ["042660.KS", "010140.KS", "329180.KS", "009540.KS", "439260.KS", "097230.KS"],
    },
    "SHIP_Parts": {
        "sector": "조선",
        "desc": "조선 기자재",
        "lead": ["7003.T", "7011.T", "7014.T", "FCT.MI"],
        "lag": [
            "017960.KS", "006730.KQ", "101930.KQ", "033500.KQ", "092460.KQ",
            "013030.KQ", "443060.KS", "125490.KQ", "064820.KQ", "014940.KQ", "075580.KS",
        ],
    },
    "SHIP_Engine": {
        "sector": "조선",
        "desc": "조선 엔진",
        "lead": ["WRT1V.HE", "7003.T", "MTX.DE"],
        "lag": ["071970.KS", "077970.KS", "082740.KS"],
    },
    "DEF_Europe": {
        "sector": "방산",
        "desc": "방산 (유럽 Peer)",
        "lead": [
            "BA.L", "RHM.DE", "HO.PA", "AM.PA", "SAF.PA", "LDO.MI", "SAAB-B.ST",
            "KOG.OL", "RR.L", "HAG.DE", "R3NK.DE", "IDR.MC", "QQ.L", "BAB.L",
            "CHG.L", "MTX.DE",
        ],
        "lag": [
            "012450.KS", "064350.KS", "079550.KS", "047810.KS", "272210.KS",
            "103140.KS", "003570.KS", "484870.KS", "010820.KS", "003490.KS",
            "214430.KQ", "065450.KQ",
        ],
    },
    "DEF_US": {
        "sector": "방산",
        "desc": "방산 (미국 Peer)",
        "lead": [
            "LMT", "RTX", "NOC", "GD", "BA", "LHX", "HII", "LDOS", "PLTR",
            "AVAV", "KTOS", "BWXT", "CW", "PSN", "MRCY", "CACI", "SAIC", "BAH",
        ],
        "lag": [
            "012450.KS", "064350.KS", "079550.KS", "047810.KS", "272210.KS",
            "103140.KS", "003570.KS", "484870.KS", "010820.KS", "003490.KS",
            "214430.KQ", "065450.KQ",
        ],
    },
    "MACH_Construction": {
        "sector": "기계",
        "desc": "건설기계",
        "lead": ["CAT", "6301.T", "DE", "SAND.ST"],
        "lag": [
            "241560.KS", "267270.KS", "079900.KS", "000490.KS", "008830.KQ",
            "002900.KS", "043260.KQ", "019210.KQ", "452280.KQ",
        ],
    },
    "ROBO_Automation": {
        "sector": "로봇",
        "desc": "로봇",
        "lead": ["6954.T", "ABBN.SW", "6506.T"],
        "lag": [
            "277810.KQ", "108490.KQ", "319400.KQ", "160190.KQ", "098460.KQ",
            "454910.KS", "058610.KQ", "389500.KQ", "466100.KQ", "455900.KQ",
            "475400.KQ", "140670.KQ", "388720.KQ", "056080.KQ",
        ],
    },
    # ===== AI 인프라 / 화학 / 정유 탭 =====
    "POWR_Transformer": {
        "sector": "AI인프라",
        "desc": "변압기/전력기기",
        "lead": ["GEV", "ENR.DE"],
        "lag": [
            "267260.KS", "298040.KS", "010120.KS", "062040.KS", "103590.KS",
            "033100.KQ", "000500.KS", "001440.KS",
        ],
    },
    "POWR_Renewable": {
        "sector": "AI인프라",
        "desc": "신재생",
        "lead": ["BE"],
        "lag": [
            "126340.KQ", "089890.KQ", "322000.KS", "009830.KS", "100090.KS",
            "475150.KS", "112610.KS", "297090.KQ", "010060.KS", "005090.KS", "336260.KS",
        ],
    },
    "POWR_NuclearKr": {
        "sector": "AI인프라",
        "desc": "국내 원전",
        "lead": ["SMR", "OKLO", "NNE", "RR.L", "BWXT", "LTBR", "CEG", "VST", "PEG", "TLN", "NEE", "EXC"],
        "lag": [
            "034020.KS", "046120.KQ", "100840.KS", "126720.KS",
            "032820.KQ", "006910.KQ", "105840.KS", "019990.KQ", "094820.KQ",
            "052690.KS", "051600.KS", "015760.KS",
        ],
    },
    "POWR_Epc": {
        "sector": "AI인프라",
        "desc": "EPC",
        "lead": ["FLR"],
        "lag": ["000720.KS", "006360.KS", "047040.KS", "028050.KS", "375500.KS"],
    },
    "MAT_Uranium": {
        "sector": "AI인프라",
        "desc": "우라늄",
        "lead": ["CCJ", "KAP.IL", "LEU", "UEC", "UUUU", "NXE", "YCA.L", "UROY"],
        "lag": [],
    },
    "AUTO_Battery": {
        "sector": "화학",
        "desc": "2차전지",
        "lead": ["ALB", "SQM"],
        "lag": [
            "107640.KQ", "006400.KS", "373220.KS", "086520.KQ", "247540.KQ",
            "450080.KS", "066970.KS", "003670.KS", "005070.KS", "082920.KQ",
            "004490.KS", "078600.KQ", "020150.KS", "393890.KQ", "033790.KQ",
            "093370.KS", "457190.KS", "336370.KS", "278280.KQ", "348370.KQ",
        ],
    },
    "CHEM_Refining": {
        "sector": "화학",
        "desc": "화학/정유",
        "lead": ["BAS.DE", "DOW", "LYB", "4183.T", "VLO", "MPC", "PSX"],
        "lag": [
            "051910.KS", "002380.KS", "011170.KS", "011780.KS", "047050.KS",
            "120110.KS", "298020.KS", "004000.KS", "006650.KS", "298050.KS",
            "014830.KS", "096770.KS", "010950.KS", "187790.KQ",
        ],
    },
    # ===== (광)통신 / 우주 탭 =====
    "TELCO_Kr": {
        "sector": "광통신",
        "desc": "통신사",
        "lead": ["VZ", "T", "TMUS", "DTE.DE", "9432.T", "0941.HK", "NOK", "ERIC", "9434.T", "ORA.PA"],
        "lag": ["017670.KS", "030200.KS", "032640.KS"],
    },
    "TELCO_Parts": {
        "sector": "광통신",
        "desc": "통신 기자재",
        "lead": ["CSCO", "ANET", "APH", "ERIC", "NOK"],
        "lag": [
            "032500.KQ", "088800.KQ", "218410.KQ", "050890.KQ", "178320.KQ",
            "230240.KQ", "073490.KQ", "138080.KQ", "327260.KQ", "046970.KQ", "456010.KQ",
        ],
    },
    "OPTIC_Cpo": {
        "sector": "광통신",
        "desc": "CPO/광통신",
        "lead": [
            "AVGO", "MRVL", "ALAB", "GLW", "FN", "COHR", "LITE", "APH", "POET",
            "AXTI", "5802.T", "4203.T", "VIAV", "TSEM", "LASR", "SITM", "KEYS",
            "AAOI", "IPGP", "3443.TW", "3661.TW", "5801.T", "9069.T",
        ],
        "lag": ["138080.KQ", "069540.KQ", "327260.KQ", "046970.KQ"],
    },
    "SPACE_Aero": {
        "sector": "우주",
        "desc": "우주",
        "lead": [
            "RKLB", "ASTS", "LUNR", "PL", "IRDM", "VSAT", "GSAT", "SPIR",
            "BKSY", "VOYG", "RDW", "KTOS", "HEI", "KRMN", "SATL", "FLY", "MDA.TO",
        ],
        "lag": [
            "189300.KQ", "361390.KQ", "451760.KQ", "099320.KQ", "347700.KQ",
            "295310.KQ", "462350.KQ", "211270.KQ", "354320.KQ",
        ],
    },
    "INFRA_DataCenter": {
        "sector": "광통신",
        "desc": "통신 인프라/데이터센터",
        "lead": ["DY", "AMT", "CCI", "SBAC", "EQIX", "6702.T", "0763.HK"],
        "lag": [],
    },
    # ===== 증권 / 지주 탭 =====
    "FIN_Bank": {
        "sector": "증권",
        "desc": "은행지주",
        "lead": ["SCHW", "IBKR", "8604.T", "RJF"],
        "lag": [
            "105560.KS", "055550.KS", "086790.KS", "316140.KS", "024110.KS",
            "138930.KS", "175330.KS", "139130.KS", "138040.KS",
        ],
    },
    "FIN_Broker": {
        "sector": "증권",
        "desc": "증권",
        "lead": ["SCHW", "IBKR", "8604.T", "RJF"],
        "lag": [
            "006800.KS", "005940.KS", "016360.KS", "039490.KS", "001720.KS",
            "003530.KS", "003540.KS", "030610.KS",
        ],
    },
    "FIN_Insurance": {
        "sector": "증권",
        "desc": "보험",
        "lead": ["MET", "PRU", "ALV.DE", "8630.T"],
        "lag": [
            "032830.KS", "000810.KS", "005830.KS", "088350.KS", "001450.KS",
            "082640.KS", "085620.KS", "003690.KS",
        ],
    },
    "HOLD_Group": {
        "sector": "지주",
        "desc": "지주회사",
        "lead": ["9984.T", "BRK-B", "EXO.AS"],
        "lag": [
            "402340.KS", "034730.KS", "003550.KS", "267250.KS", "000150.KS",
            "000880.KS", "006260.KS", "078930.KS", "001040.KS",
        ],
    },
    # ===== 화장품 / 식품 / IP 탭 =====
    "BEAUTY_Mass": {
        "sector": "화장품",
        "desc": "화장품/ODM",
        "lead": ["OR.PA", "EL", "ELF"],
        "lag": [
            "257720.KQ", "161890.KS", "192820.KS", "241710.KQ", "018290.KQ",
            "483650.KS", "278470.KS", "123330.KQ", "251970.KS", "439090.KQ",
        ],
    },
    "BEAUTY_SkinBooster": {
        "sector": "화장품",
        "desc": "스킨부스터",
        "lead": ["OR.PA", "EL", "ELF"],
        "lag": [
            "214450.KQ", "145020.KQ", "200670.KQ", "290650.KQ", "042520.KQ",
            "340570.KQ", "214150.KQ",
        ],
    },
    "FOOD_Brand": {
        "sector": "식품",
        "desc": "식품",
        "lead": ["NESN.SW", "PEP", "MDLZ"],
        "lag": [
            "003230.KS", "260970.KQ", "271560.KS", "004370.KS", "194700.KQ",
            "222040.KQ", "200130.KQ",
        ],
    },
    "IP_Content": {
        "sector": "IP",
        "desc": "IP/엔터",
        "lead": ["LYV", "WMG", "SPOT"],
        "lag": [
            "352820.KS", "041510.KQ", "035900.KQ", "122870.KQ", "376300.KQ",
            "253450.KQ", "419530.KQ", "039830.KQ", "310200.KQ", "473980.KQ",
        ],
    },
}
