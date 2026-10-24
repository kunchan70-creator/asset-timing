# -*- coding: utf-8 -*-
"""자산별 관망 신호 검증 그림 (2026-10-21): 같은 시간축에 자산을 쌓아, 신호(주황)와 실제로 현금이 나았던 때(회색)를 겹쳐 봄.
규칙은 자산 하나씩 조사한 결과(사용자와 10-21 대화). 실패한 자산도 '가장 그럴듯했던 규칙'을 그대로 보여 줌.
py build_history.py -> history.html
"""
import os, sys, json, datetime
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
from pairs import P, T, rpct, roll_pct, runs
from panel import ASSETS

Q = rpct().copy()


def dev5(a):
    px = P[ASSETS[a][0]]
    return roll_pct(px / px.rolling(60).mean())


def jp_hike():
    jp = pd.read_csv(os.path.join(B, "data/raw/f_IRSTCI01JPM156N.csv")); jp.index = pd.PeriodIndex(jp.date, freq="M")
    jd = pd.read_csv(os.path.join(B, "data/raw/f_INTDSRJPM193N.csv")); jd.index = pd.PeriodIndex(jd.date, freq="M")
    j = jp["value"].combine_first(jd["value"]).reindex(P.index).ffill()
    return roll_pct(j - j.shift(12))


def btc_mult():
    px = P["btc"]; return px / px.rolling(24, min_periods=12).mean()


RULES = [  # (자산, 규칙 이름, 신호 함수, 판정 여부) — 10-21: 자산마다 그 자산을 움직이는 원인으로 따로 찾음(_redo.py)
    ("kospi", "과열 + 한국 수출 증가율 정점", lambda: (dev5("kospi") >= 0.7) & (Q["kr_exp_yoy"] >= 0.7), True),
    ("nasdaq", "과열 + 미 2년물 금리 급등", lambda: (dev5("nasdaq") >= 0.8) & (Q["d_y2_12"] >= 0.7), True),
    ("oil", "과열 + 달러 강세", lambda: (dev5("oil") >= 0.7) & (Q["dxy12"] >= 0.7), True),
    ("copper", "과열 + 미 산업생산 둔화", lambda: (dev5("copper") >= 0.7) & (Q["d_ip_yoy6"] <= 0.3), True),
    ("ust10", "물가 가속 + 연준 금리 인상", lambda: (Q["d_cpi12"] >= 0.7) & (Q["d_ff12"] >= 0.7), True),
    ("sox", "과열 + 한국 수출 증가율 정점(3번뿐)", lambda: (dev5("sox") >= 0.7) & (Q["kr_exp_yoy"] >= 0.8), False),
    ("spx", "미 주식 고평가 + 물가 가속", lambda: (Q["cape"] >= 0.8) & (Q["d_cpi12"] >= 0.7), False),
    ("dji", "과열 + 미 산업생산 둔화", lambda: (dev5("dji") >= 0.7) & (Q["d_ip_yoy6"] <= 0.3), False),
    ("rut", "신용 악화 + 연준 긴축", lambda: (Q["d_spr6"] >= 0.7) & (Q["d_ff12"] >= 0.6), False),
    ("schd", "10년 금리 급등 + 과열(1번뿐)", lambda: (Q["d_y10_12"] >= 0.7) & (dev5("schd") >= 0.7), False),
    ("ust30", "물가 가속 + 연준 금리 인상", lambda: (Q["d_cpi12"] >= 0.7) & (Q["d_ff12"] >= 0.7), False),
    ("comm", "과열 + 고용 꺾임", lambda: (dev5("comm") >= 0.8) & (Q["claims"] >= 0.6), False),
    ("em", "미 주식 고평가 + 미 2년물 급등", lambda: (Q["cape"] >= 0.8) & (Q["d_y2_12"] >= 0.7), False),
    ("hy", "금융 여건 긴축", lambda: Q["d_nfci6"] >= 0.8, False),
    ("reit", "10년 금리 급등", lambda: Q["d_y10_12"] >= 0.8, False),
    ("nikkei", "과열 + 일본 금리 인상", lambda: (dev5("nikkei") >= 0.7) & (jp_hike() >= 0.7), False),
    ("gold", "과열 + 실질금리 상승", lambda: (dev5("gold") >= 0.7) & (Q["d_real10_12"] >= 0.6), False),
    ("silver", "과열 + 고용 꺾임", lambda: (dev5("silver") >= 0.7) & (Q["claims"] >= 0.6), False),
    ("usd", "원화 크게 약세(5년 평균 대비)", lambda: dev5("usd") >= 0.8, False),
    ("btc", "2년 평균의 2배 이상", lambda: btc_mult() >= 2.0, False),
]


def buy_sig(a):
    """매수 신호(10-21): 1년 안 고점 대비 -20% 이상 빠진 뒤 10개월 평균 위로 회복, 아직 고점보다 10%+ 아래.
    미국 주식(S&P 50/51달·나스닥 57/63달)에서만 통함, 다른 시장은 참고."""
    px = P[ASSETS[a][0]]
    up = px > px.rolling(10).mean()
    dd12 = (px / px.rolling(12).max() - 1).rolling(12).min()
    return ((dd12 <= -0.2) & up & (px / px.cummax() - 1 <= -0.1)).fillna(False)


BUY_OK = {"spx", "nasdaq"}

# 10-21 사용자: 세로축은 % 말고 실제 값 → 화면용 가격(신호 계산은 총수익 지수 그대로)
RAW = {"spx": "y_spx", "nasdaq": "y_nasdaq", "dji": "y_dji", "sox": "y_sox", "rut": "y_rut", "nikkei": "y_nikkei",
       "schd": "y_schd", "em": "y_em_f", "hy": "y_hy_f", "reit": "y_reit_f"}
UNIT = {"spx": "pt", "nasdaq": "pt", "dji": "pt", "sox": "pt", "rut": "pt", "nikkei": "엔", "kospi": "pt", "schd": "$", "em": "$", "hy": "$",
        "reit": "$", "gold": "$/온스", "silver": "$/온스", "oil": "$/배럴", "copper": "$/파운드", "comm": "지수", "btc": "$",
        "ust10": "총수익지수", "ust30": "총수익지수", "usd": "원/달러"}
GROUP = {"미국 주식": ["nasdaq", "spx", "dji", "rut", "sox", "schd"], "한국·해외 주식": ["kospi", "nikkei", "em"],
         "채권·리츠": ["ust10", "ust30", "hy", "reit"], "원자재·금속": ["oil", "copper", "comm", "gold", "silver"], "달러·코인": ["usd", "btc"]}


def _raw(name):
    x = pd.read_csv(os.path.join(B, "data", "raw", name + ".csv")); v = x["value"].astype(float); v.index = pd.PeriodIndex(x["date"], freq="M")
    return v.reindex(P.index)


def disp(a):
    from panel import splice_pref
    if a in RAW: return _raw(RAW[a])
    if a == "kospi":
        return splice_pref(_raw("f_SPASTT01KRM661N").dropna()[:"1996-12"], _raw("y_kospi").dropna()).reindex(P.index)
    if a == "usd": return P["usdkrw"]
    return P[ASSETS[a][0]]


def ranges(s):
    s = s.fillna(False); out = []; st = prev = None
    for d, v in s.items():
        if v and st is None: st = d
        if not v and st is not None:
            out.append([round(st.year + (st.month - 1) / 12, 3), round(prev.year + prev.month / 12, 3)]); st = None
        prev = d
    if st is not None: out.append([round(st.year + (st.month - 1) / 12, 3), round(prev.year + prev.month / 12, 3)])
    return out


def main():
    out = []
    for a, rname, fn, verdict in RULES:
        col, cash, name = ASSETS[a]
        px = P[col].dropna()
        sig = fn().reindex(P.index).fillna(False) & P[col].notna()
        bad = T[a + "_bad"]
        known = sig & bad.notna()
        n = int(known.sum())
        hit = float(bad[known].mean()) if n else None
        valid = P[col].notna() & bad.notna()
        bs = buy_sig(a) & P[col].notna()
        bk = bs & bad.notna()
        dv = disp(a).where(P[col].notna()).dropna()
        pts = [[round(d.year + (d.month - 1) / 12, 3), float(f"{v:.4g}")] for d, v in dv.items() if v > 0]
        out.append({
            "id": a, "name": name, "rule": rname, "verdict": verdict, "unit": UNIT.get(a, ""),
            "grp": next(k for k, v in GROUP.items() if a in v),
            "hit": None if hit is None else round(hit * 100), "n": n, "ep": runs(known),
            "base": round(float(bad[valid].mean()) * 100), "share": round(float(sig[P[col].notna()].mean()) * 100),
            "now": bool(sig.iloc[-1]), "p": pts, "bad": ranges(bad == 1), "on": ranges(sig),
            "hold": ranges(sig.astype(int).rolling(12, min_periods=1).max().astype(bool) & ~sig & ~(buy_sig(a) & P[col].notna())),
            "buy": ranges(bs), "bhit": round(float((bad[bk] == 0).mean()) * 100) if bk.sum() else None, "bn": int(bk.sum()),
            "bbase": round(float((bad[valid] == 0).mean()) * 100), "bok": a in BUY_OK, "bnow": bool(bs.iloc[-1]),
            "known": round(bad.last_valid_index().year + bad.last_valid_index().month / 12, 3),
        })
        print(a, rname, "hit", out[-1]["hit"], "n", n, "base", out[-1]["base"], "share", out[-1]["share"], "now", out[-1]["now"])
    tpl = open(os.path.join(B, "history_tpl.html"), encoding="utf-8").read()
    html = tpl.replace("__CHART_JS__", open(os.path.join(B, "chart_core.js"), encoding="utf-8").read()).replace("__JIPSEM_CSS__", open(os.path.join(B, "jipsem_style.css"), encoding="utf-8").read()) \
              .replace("__GROUPS__", json.dumps(list(GROUP), ensure_ascii=False)) \
              .replace("__DATA__", json.dumps(out, ensure_ascii=False, separators=(",", ":"))) \
              .replace("__ASOF__", datetime.date.today().strftime("%Y.%m.%d"))
    open(os.path.join(B, "history.html"), "w", encoding="utf-8").write(html)
    print("ok", len(html))


if __name__ == "__main__":
    main()
