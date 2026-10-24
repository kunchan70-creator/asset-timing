# -*- coding: utf-8 -*-
"""경고등 방식 (2026-10-20): 자산마다 경제 원리로 '미리' 정한 경고등 여러 개, 켜진 개수로 관망 판단.
자료를 보고 고르는 단계가 없음(조합 탐색은 다음 기간에 무너짐: S&P 92%→6%, _oos 실측).
경고등 문턱 = 최근 20년 자기 역사 상위/하위 20% (curve_min12 만 0 기준 = 1년 안 장단기 역전).
py lights.py [--vault] -> logs/lights.txt
"""
import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
from pairs import P, T, rpct, pmask, runs
from panel import ASSETS

Q = rpct()
HI, LO = 0.8, 0.2

# 경고등: (이름, 지표, 방향) — 방향 hi = 높을수록 그 자산에 나쁨
L = {
    "equity": [  # 주식(S&P·나스닥·코스피)
        ("긴축(기준금리 1년 인상폭)", "d_ff12", "hi"),
        ("금리 급등(2년물 1년 변화)", "d_y2_12", "hi"),
        ("장단기 역전(1년 안)", "curve_min12", "inv"),
        ("고평가(CAPE)", "cape", "hi"),
        ("신용 악화(회사채 가산금리 6개월 확대)", "d_spr6", "hi"),
        ("고용 꺾임(실업수당 청구 바닥 대비)", "claims", "hi"),
        ("금융 여건 긴축(NFCI 6개월 변화)", "d_nfci6", "hi"),
        ("생산 둔화(산업생산 증가율 6개월 변화)", "d_ip_yoy6", "lo"),
        ("주택 인허가 감소", "permit_yoy", "lo"),
        ("유가 급등", "oil12", "hi"),
    ],
    "gold": [
        ("실질금리 상승", "d_real10_12", "hi"),
        ("달러 강세", "dxy12", "hi"),
        ("물가 둔화", "d_cpi12", "lo"),
        ("긴축(기준금리 1년 인상폭)", "d_ff12", "hi"),
        ("금 실질가격 높음", "gold_real", "hi"),
        ("위험 선호(신용 가산금리 축소)", "d_spr6", "lo"),
        ("실질 통화량 감소", "m2_real", "lo"),
    ],
    "bond": [
        ("물가 상승 가속", "d_cpi12", "hi"),
        ("근원물가 6개월 높음", "core6", "hi"),
        ("긴축(기준금리 1년 인상폭)", "d_ff12", "hi"),
        ("실질 기준금리 낮음(연준 뒤처짐)", "real_ff", "lo"),
        ("경기 과열(CFNAI)", "cfnai3", "hi"),
        ("유가 급등", "oil12", "hi"),
        ("실질 10년 금리 낮음(완충 없음)", "real10", "lo"),
    ],
    "comm": [
        ("달러 강세", "dxy12", "hi"),
        ("고용 꺾임(실업수당 청구)", "claims", "hi"),
        ("생산 둔화", "d_ip_yoy6", "lo"),
        ("경기 지수 약함(CFNAI)", "cfnai3", "lo"),
        ("긴축(기준금리 1년 인상폭)", "d_ff12", "hi"),
        ("원자재 실질가격 높음", "comm_real", "hi"),
        ("장단기 역전(1년 안)", "curve_min12", "inv"),
        ("신용 악화", "d_spr6", "hi"),
    ],
    "crypto": [
        ("긴축(기준금리 1년 인상폭)", "d_ff12", "hi"),
        ("금리 급등(2년물)", "d_y2_12", "hi"),
        ("연준 자산 축소", "fedbs_yoy", "lo"),
        ("통화량 증가 둔화", "m2_yoy", "lo"),
        ("달러 강세", "dxy12", "hi"),
        ("금융 여건 긴축", "d_nfci6", "hi"),
        ("실질금리 상승", "d_real10_12", "hi"),
    ],
    "usd": [  # 원화 투자자의 달러 예금
        ("미 금리 인하", "d_ff12", "lo"),
        ("달러 이미 강세(원화 약세 1년)", "krw12", "hi"),
        ("한국 수출 회복", "kr_exp_yoy", "hi"),
        ("위험 선호(금융 여건 완화)", "d_nfci6", "lo"),
        ("미 장단기 금리차 확대", "curve", "hi"),
    ],
}
GROUP = {"spx": "equity", "nasdaq": "equity", "kospi": "equity", "gold": "gold", "ust10": "bond",
         "comm": "comm", "oil": "comm", "copper": "comm", "btc": "crypto", "usd": "usd"}
# 코스피 전용 추가등
EXTRA = {"kospi": [("한국 수출 둔화", "kr_exp_yoy", "lo"), ("원화 약세", "krw12", "hi")]}


def lights_for(a):
    ls = L[GROUP[a]] + EXTRA.get(a, [])
    M = {}
    for nm, f, d in ls:
        if d == "inv":
            v = P[f] < 0; M[nm] = v.where(P[f].notna())
        else:
            q = Q[f] if f in Q else None
            v = (q >= HI) if d == "hi" else (q <= LO)
            M[nm] = v.where(q.notna())
    return pd.DataFrame(M)


def count(a):
    M = lights_for(a)
    avail = M.notna().sum(axis=1)
    c = M.fillna(False).astype(int).sum(axis=1)
    return c, avail, M


def table(a, pers=("A", "B")):
    c, avail, M = count(a)
    full = len(M.columns)
    ok = T[a + "_bad"].notna() & (avail >= full - 1)   # 경고등 대부분 잴 수 있는 달만
    out = []
    for k in range(1, full + 1):
        row = [k]
        for per in pers:
            m = ok & pmask(per)
            sg = (c >= k) & m
            n = int(sg.sum())
            hit = T[a + "_bad"][sg].mean() if n else np.nan
            ex = T[a + "_ex"][sg].mean() if n else np.nan
            row.append((n, runs(sg), hit, ex, T[a + "_bad"][m].mean(), int(m.sum())))
        out.append(row)
    return out


if __name__ == "__main__":
    vault = "--vault" in sys.argv
    pers = ("A", "B", "V") if vault else ("A", "B")
    lines = []
    for a in ASSETS:
        lines.append(f"\n=== {a} ({GROUP[a]}) 경고등 {len(lights_for(a).columns)}개")
        for row in table(a, pers):
            k = row[0]; s = f"  {k}개+ "
            for per, (n, ep, hit, ex, base, tot) in zip(pers, row[1:]):
                s += f"| {per} n{n:3d}/{tot} ep{ep:2d} hit {hit*100 if n else 0:5.1f} (base {base*100 if tot else 0:4.1f}) ex {ex if n else 0:6.1f} "
            lines.append(s)
    txt = "\n".join(lines)
    open(os.path.join(B, "logs", "lights" + ("_V" if vault else "") + ".txt"), "w", encoding="utf-8").write(txt)
    print(txt)
