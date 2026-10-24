# -*- coding: utf-8 -*-
"""환율 조사 2단계 자료(ECOS, 키 불필요 sample): 국제수지 금융계정(자금 흐름) 월별 + 한국 소비자물가 + 외환보유액. 2026-10-21"""
import sys
from fetch_fx import fetch, save
sys.stdout.reconfigure(encoding="utf-8")
ITEMS = {
    "bop_pi_asset": ("301Y013", "BOPF21000000", "198001"),   # 증권투자(자산): 내국인 해외증권 매입 = 유출
    "bop_pi_liab": ("301Y013", "BOPF22000000", "198001"),    # 증권투자(부채): 외국인 국내증권 매입 = 유입
    "bop_di_asset": ("301Y013", "BOPF11000000", "198001"),   # 직접투자(자산)
    "bop_di_liab": ("301Y013", "BOPF12000000", "198001"),    # 직접투자(부채)
    "bop_reserve": ("301Y013", "BOPF50000000", "198001"),    # 준비자산 증감(개입 흔적)
    "bop_oi_asset": ("301Y013", "BOPF41000000", "198001"),
    "bop_oi_liab": ("301Y013", "BOPF42000000", "198001"),
    "kr_cpi": ("901Y009", "0", "197501"),
}
for n, (st, it, frm) in ITEMS.items():
    d = fetch(st, it, frm)
    if d: save("ecos_" + n, d)   # 10-21: 빈 응답이면 기존 유지
    print(n, len(d), min(d) if d else "-", max(d) if d else "-", flush=True)
