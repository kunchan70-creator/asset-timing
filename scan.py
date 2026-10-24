# -*- coding: utf-8 -*-
"""지표 하나씩 훑기 (탐색 기간만: A=~1999, B=2000~2013. 금고 V=2014~ 는 보지 않음).
문턱 = 그때까지 자기 역사 상위/하위 q (걸어가며 백분위, 미래 안 씀).
py scan.py [자산...] -> logs/scan.txt
"""
import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(os.path.join(B, "data", "panel.pkl")); P, T = D["P"], D["T"]
from panel import ASSETS

FEATS = ["d_ff12", "d_y2_12", "d_y10_12", "curve", "curve_min12", "cpi_yoy", "core6", "d_cpi12", "real10", "d_real10_12",
         "tips", "d_tips12", "real_ff", "baa_spr", "d_spr6", "d_spr12", "nfci", "d_nfci6", "vix", "sahm", "d_un12", "claims",
         "ip_yoy", "d_ip_yoy6", "pay3", "permit_yoy", "cfnai3", "sent", "d_sent12", "m2_yoy", "m2_real", "credit_yoy",
         "fedbs_yoy", "dxy12", "dxy6", "krw12", "kr_exp_yoy", "kr_y3", "d_kr3_12", "oil12", "comm12", "d_cg12", "cape",
         "gold_real", "comm_real", "oil_real", "ff", "tb3"]


def exp_pct(x, minn=60):
    """그 달까지 자기 역사에서의 백분위(0~1)."""
    v = x.values; out = np.full(len(v), np.nan); hist = []
    for i, a in enumerate(v):
        if np.isnan(a): continue
        hist.append(a)
        if len(hist) >= minn:
            h = np.asarray(hist); out[i] = (h <= a).mean()
    return pd.Series(out, index=x.index)


PCT = None


def pct():
    global PCT
    if PCT is None:
        p = os.path.join(B, "data", "pct.pkl")
        if os.path.exists(p) and os.path.getmtime(p) > os.path.getmtime(os.path.join(B, "data", "panel.pkl")):
            PCT = pd.read_pickle(p)
        else:
            PCT = pd.DataFrame({f: exp_pct(P[f]) for f in FEATS}); PCT.to_pickle(p)
    return PCT


PER = {"A": ("1953-01", "1999-12"), "B": ("2000-01", "2013-12"), "V": ("2014-01", "2025-12")}


def runs(sig):
    """켜진 구간 수(6개월 넘게 꺼졌다 다시 켜지면 새 구간)."""
    on = sig[sig].index
    if len(on) == 0: return 0
    k = 1
    for a, b in zip(on[:-1], on[1:]):
        if (b - a).n > 6: k += 1
    return k


def stat(sig, a, per):
    lo, hi = PER[per]
    m = (sig.index >= pd.Period(lo, "M")) & (sig.index <= pd.Period(hi, "M"))
    bad = T[a + "_bad"]; ok = bad.notna() & m
    sg = sig.fillna(False).astype(bool) & ok
    n = int(sg.sum()); base = bad[ok].mean()
    if n == 0: return dict(n=0, base=base, hit=np.nan, cov=0, ex=np.nan, ep=0)
    return dict(n=n, base=base, hit=bad[sg].mean(), cov=n / ok.sum(), ex=T[a + "_ex"][sg].mean(), ep=runs(sg))


if __name__ == "__main__":
    os.makedirs(os.path.join(B, "logs"), exist_ok=True)
    Q = pct()
    assets = sys.argv[1:] or list(ASSETS)
    lines = []
    for a in assets:
        lines.append(f"\n=== {a} ===  (hit=관망 적중, base=평소, ex=켜진 달 뒤 12개월 평균 초과수익)")
        rows = []
        for f in FEATS:
            for side in ("hi", "lo"):
                for q in (0.8, 0.9):
                    sig = Q[f] >= q if side == "hi" else Q[f] <= 1 - q
                    sa, sb = stat(sig, a, "A"), stat(sig, a, "B")
                    if sa["n"] + sb["n"] < 12: continue
                    rows.append((f, side, q, sa, sb))
        def score(r):
            sa, sb = r[3], r[4]
            ha = sa["hit"] if sa["n"] >= 6 else np.nan; hb = sb["hit"] if sb["n"] >= 6 else np.nan
            v = [h for h in (ha, hb) if not np.isnan(h)]
            return min(v) if v else 0
        rows.sort(key=score, reverse=True)
        for f, side, q, sa, sb in rows[:25]:
            lines.append(f"{f:12s} {side} q{q:.1f} | A n{sa['n']:3d} ep{sa['ep']:2d} hit {sa['hit']*100 if sa['n'] else 0:5.1f} (base {sa['base']*100 if sa['base']==sa['base'] else 0:4.1f}) ex {sa['ex'] if sa['n'] else 0:6.1f}"
                         f" | B n{sb['n']:3d} ep{sb['ep']:2d} hit {sb['hit']*100 if sb['n'] else 0:5.1f} (base {sb['base']*100 if sb['base']==sb['base'] else 0:4.1f}) ex {sb['ex'] if sb['n'] else 0:6.1f}")
    open(os.path.join(B, "logs", "scan.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("ok", len(lines))
