# -*- coding: utf-8 -*-
"""두 지표 겹침(원인 AND 행동) 조합 찾기 — 탐색 기간 A(~1999)·B(2000~2013)만 봄. 금고 V(2014~)는 --vault 일 때만.
문턱 = 최근 20년(240개월, 최소 60) 자기 역사 백분위. 자기 가격 추세 지표 없음.
고르는 기준 = A·B 각각 켜진 달 12개월+, 적중의 작은 쪽(min) 최대.
py pairs.py [자산...] [--vault] -> logs/pairs_<자산>.txt
"""
import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(os.path.join(B, "data", "panel.pkl")); P, T = D["P"], D["T"]
from panel import ASSETS
from scan import FEATS, PER, runs

WIN = 240


def roll_pct(x, win=WIN, minn=60):
    v = x.values; out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]): continue
        h = v[max(0, i - win + 1):i + 1]; h = h[~np.isnan(h)]
        if len(h) >= minn: out[i] = (h <= v[i]).mean()
    return pd.Series(out, index=x.index)


def rpct():
    p = os.path.join(B, "data", "rpct.pkl")
    if os.path.exists(p) and os.path.getmtime(p) > os.path.getmtime(os.path.join(B, "data", "panel.pkl")):
        return pd.read_pickle(p)
    Q = pd.DataFrame({f: roll_pct(P[f]) for f in FEATS}); Q.to_pickle(p); return Q


QS = (0.7, 0.8, 0.9)


def singles(Q):
    names, cols = [], []
    for f in FEATS:
        for side in ("hi", "lo"):
            for q in QS:
                sig = (Q[f] >= q) if side == "hi" else (Q[f] <= 1 - q)
                names.append((f, side, q)); cols.append(sig.fillna(False).values)
    return names, np.array(cols).T.astype(np.float32)   # months x K


def pmask(per):
    lo, hi = PER[per]
    return (P.index >= pd.Period(lo, "M")) & (P.index <= pd.Period(hi, "M"))


def label(nm):
    f, side, q = nm
    return f"{f}{'>=' if side == 'hi' else '<='}{int(q*100) if side == 'hi' else int((1-q)*100)}%"


EPA, EPB = 3, 2


def search(a, S, names, top=40, minn=12):
    bad = T[a + "_bad"]; okall = bad.notna().values
    res = {}
    for per in ("A", "B", "V"):
        m = pmask(per) & okall
        b = (bad.fillna(0).values > 0) & m
        Sm = S * m[:, None]; Sb = S * b[:, None]
        res[per] = (Sm.T @ S, Sb.T @ S, m.sum(), b.sum())
    nA, hA = res["A"][0], res["A"][1]; nB, hB = res["B"][0], res["B"][1]
    with np.errstate(invalid="ignore", divide="ignore"):
        rA = hA / nA; rB = hB / nB
    ok = (nA >= minn) & (nB >= minn)
    sc = np.where(ok, np.minimum(rA, rB), -1)
    iu = np.triu_indices(len(names))
    flat = sc[iu]; order = np.argsort(-flat)
    out = []
    seen = set()
    mA = pmask("A") & okall; mB = pmask("B") & okall
    for k in order[:20000]:
        if flat[k] <= 0: break
        i, j = iu[0][k], iu[1][k]
        sig = pd.Series((S[:, i] * S[:, j]) > 0, index=P.index)
        if runs(sig & mA) < EPA or runs(sig & mB) < EPB: continue
        fi, fj = names[i][0], names[j][0]
        key = tuple(sorted((fi + names[i][1], fj + names[j][1])))
        if key in seen: continue      # 같은 지표 쌍은 가장 좋은 문턱 하나만
        seen.add(key)
        out.append((i, j))
        if len(out) >= top: break
    return out, res


def describe(a, i, j, S, names, res, vault=False):
    sig = pd.Series((S[:, i] * S[:, j]) > 0, index=P.index)
    parts = []
    for per in (("A", "B", "V") if vault else ("A", "B")):
        n = res[per][0][i, j]; h = res[per][1][i, j]; base = res[per][3] / max(res[per][2], 1)
        m = pmask(per) & T[a + "_bad"].notna().values
        ep = runs(sig & m)
        ex = T[a + "_ex"][sig & m].mean() if n else np.nan
        parts.append(f"{per} n{int(n):3d} ep{ep:2d} hit {h/n*100 if n else 0:5.1f}(base {base*100:4.1f}) ex{ex:6.1f}")
    return f"{label(names[i])} & {label(names[j])}  | " + " | ".join(parts)


if __name__ == "__main__":
    vault = "--vault" in sys.argv
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    Q = rpct(); names, S = singles(Q)
    os.makedirs(os.path.join(B, "logs"), exist_ok=True)
    for a in (args or list(ASSETS)):
        if a == "btc" or a == "kospi":
            pass
        top, res = search(a, S, names)
        lines = [describe(a, i, j, S, names, res, vault) for i, j in top]
        open(os.path.join(B, "logs", f"pairs_{a}{'_V' if vault else ''}.txt"), "w", encoding="utf-8").write("\n".join(lines))
        print(f"== {a}"); print("\n".join(lines[:12]))
