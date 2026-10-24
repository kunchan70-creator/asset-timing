# -*- coding: utf-8 -*-
"""자산 시황 판단 (2026-10-20) — 지금 상태 + 비슷했던 과거 + (금고 통과한 자산만) 관망 판정.
① 관망 규칙 = 경고등 K개 이상. K 는 탐색 기간(A ~1999, B 2000~2013)만 보고 미리 정함:
   A+B 합쳐 켜진 달 24+ · 사건 4+ 중 적중 최대.  ② 금고(V 2014~)로 한 번 채점: 적중 75%+ 이고 평소+15%p 이상이면 통과.
③ 비슷한 과거 = 경고등 지표 백분위 거리로 가장 가까운 과거 달(그 달 기준 12개월 전까지 자료만) — 걸어가며 검증해 '설명용/참고' 표시.
py judge.py -> data/judge.json , logs/judge.txt
"""
import os, sys, json
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
from pairs import P, T, rpct, pmask, runs
from panel import ASSETS
from lights import lights_for, GROUP, L, EXTRA, HI, LO

Q = rpct()
SHOW = ["nasdaq", "spx", "kospi", "gold", "comm", "ust10", "btc", "usd"]
VAULT_HIT, VAULT_LIFT = 0.75, 0.15


def feats_for(a):
    ls = L[GROUP[a]] + EXTRA.get(a, [])
    return [(nm, f, d) for nm, f, d in ls]


def light_df(a):
    M = lights_for(a)
    # 지금 판정용: 늦게 나오는 지표는 최대 3개월 앞 값으로 채움
    return M.ffill(limit=3)


def pick_k(a):
    M = light_df(a); full = M.shape[1]
    c = M.fillna(False).astype(int).sum(axis=1); avail = M.notna().sum(axis=1)
    ok = T[a + "_bad"].notna() & (avail >= full - 1)
    m = ok & (pmask("A") | pmask("B"))
    best = None
    for k in range(2, full + 1):
        sg = (c >= k) & m; n = int(sg.sum())
        if n < 24 or runs(sg) < 4: continue
        hit = T[a + "_bad"][sg].mean()
        if best is None or hit > best[1]: best = (k, hit, n)
    return best, c, ok


def per_stat(a, sig, ok, per):
    m = ok & pmask(per); sg = sig & m; n = int(sg.sum())
    return dict(n=n, ep=runs(sg), hit=float(T[a + "_bad"][sg].mean()) if n else None,
                base=float(T[a + "_bad"][m].mean()) if m.sum() else None,
                ex=float(T[a + "_ex"][sg].median()) if n else None, months=int(m.sum()))


def analog_vec(a):
    fs = feats_for(a)
    X = pd.DataFrame({f: Q[f] if d != "inv" else (P[f] < 0).astype(float).where(P[f].notna()) for nm, f, d in fs})
    return X.ffill(limit=3)


def nearest(X, t, k=30, gap=12, picks=5):
    """t 시점에서, t-12 까지의 과거 달 중 가까운 순."""
    x = X.loc[t]
    if x.isna().sum() > len(x) * 0.4: return None, None
    past = X.loc[:t - 12]
    w = x.notna()
    d = ((past.loc[:, w] - x[w]) ** 2).mean(axis=1, skipna=True) ** 0.5
    cnt = past.loc[:, w].notna().sum(axis=1)
    d = d[cnt >= w.sum() * 0.6].dropna().sort_values()
    if len(d) < k: return None, None
    top = d.index[:k]
    sel = []
    for i in d.index:
        if all(abs((i - j).n) >= gap for j in sel): sel.append(i)
        if len(sel) >= picks: break
    return top, sel


def analog_validate(a, X):
    """걸어가며: 비슷한 과거 30달 중 '관망이 나았던' 비율 → 실제와 비교(AUC·상위 적중)."""
    bad = T[a + "_bad"]
    rows = []
    for t in X.index:
        if pd.isna(bad.get(t)) or t < pd.Period("1975-01", "M"): continue
        top, _ = nearest(X, t)
        if top is None: continue
        p = bad.reindex(top).mean()
        if pd.isna(p): continue
        rows.append((t, p, bad[t]))
    if not rows: return None
    D = pd.DataFrame(rows, columns=["t", "p", "y"]).set_index("t")
    out = {}
    for per in ("A", "B", "V"):
        lo, hi = {"A": ("1953-01", "1999-12"), "B": ("2000-01", "2013-12"), "V": ("2014-01", "2025-12")}[per]
        d = D[(D.index >= pd.Period(lo, "M")) & (D.index <= pd.Period(hi, "M"))]
        if len(d) < 24 or d["y"].nunique() < 2: continue
        from sklearn.metrics import roc_auc_score
        hi_ = d[d["p"] >= 0.6]
        out[per] = dict(n=len(d), auc=float(roc_auc_score(d["y"], d["p"])),
                        hi_n=len(hi_), hi_hit=float(hi_["y"].mean()) if len(hi_) else None, base=float(d["y"].mean()))
    return out


def main():
    rep = {"asof": str(P.index[-1]), "assets": {}}
    lines = []
    for a in SHOW:
        col, cash, name = ASSETS[a]
        M = light_df(a); full = M.shape[1]
        now = M.index[-1]
        lit = {nm: (None if pd.isna(M.loc[now, nm]) else bool(M.loc[now, nm])) for nm in M.columns}
        cnow = sum(1 for v in lit.values() if v)
        r = {"name": name, "lights": lit, "count": cnow, "full": full}
        best, c, ok = pick_k(a)
        if best:
            k = best[0]; sig = c >= k
            r["rule"] = {"k": k, "A": per_stat(a, sig, ok, "A"), "B": per_stat(a, sig, ok, "B"), "V": per_stat(a, sig, ok, "V")}
            v = r["rule"]["V"]
            r["rule"]["pass"] = bool(v["n"] >= 6 and v["hit"] is not None and v["hit"] >= VAULT_HIT and v["hit"] >= v["base"] + VAULT_LIFT)
        else:
            r["rule"] = None
        X = analog_vec(a)
        top, sel = nearest(X, now)
        if top is not None:
            bad = T[a + "_bad"]; ex = T[a + "_ex"]
            r["analog"] = {"n": int(bad.reindex(top).notna().sum()), "bad": float(bad.reindex(top).mean()),
                           "ex_med": float(ex.reindex(top).median()), "ex_p10": float(ex.reindex(top).quantile(.1)),
                           "ex_p90": float(ex.reindex(top).quantile(.9)),
                           "picks": [{"m": str(i), "ex": float(ex[i]), "bad": bool(bad[i])} for i in sel if not pd.isna(bad.get(i))]}
        r["analog_val"] = analog_validate(a, X)
        # 평소(전체 기간) 1년 초과수익 분포
        exa = T[a + "_ex"].dropna()
        r["base_all"] = {"bad": float(T[a + "_bad"].dropna().mean()), "ex_med": float(exa.median()), "n": int(len(exa)),
                         "from": str(exa.index[0])}
        rep["assets"][a] = r
        rl = r["rule"]
        lines.append(f"\n== {a} {name}: 지금 경고등 {cnow}/{full} " + " ".join(f"[{'O' if v else ('-' if v is None else 'x')}]{nm}" for nm, v in lit.items()))
        if rl:
            for per in ("A", "B", "V"):
                s = rl[per]
                lines.append(f"   규칙 {rl['k']}개+ {per}: n{s['n']} ep{s['ep']} hit {s['hit']*100 if s['hit'] is not None else 0:.0f}% base {s['base']*100 if s['base'] is not None else 0:.0f}%")
            lines.append(f"   금고 통과: {rl['pass']}")
        if "analog" in r:
            an = r["analog"]
            lines.append(f"   비슷한 과거 30달: 현금이 나았던 {an['bad']*100:.0f}% · 1년 초과 중앙 {an['ex_med']:+.1f}% · 대표 " + ", ".join(f"{p['m']}({p['ex']:+.0f}%)" for p in an["picks"]))
        lines.append(f"   비슷한 과거 검증: {r['analog_val']}")
    json.dump(rep, open(os.path.join(B, "data", "judge.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    txt = "\n".join(lines)
    open(os.path.join(B, "logs", "judge.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
