# -*- coding: utf-8 -*-
"""환율 신호 (2026-10-21. 같은 날 '외국인 유출' 신호는 사건 단위 10번 중 6번이라 폐기, 아래 '환전 미루기'로 교체, 사용자: '환율 표기 없이 포지션 정하면 안 됨').
원화 강세 신호 = 외국인 증권투자 유입 6개월 합(ECOS BOPF22000000, 발표 시차 2달)이 최근 10년 중 하위 20%
              + 코스피 6개월 수익 < 0  →  그 뒤 9개월 원화가 반등한 경우가 많음(외국인이 공포에 판 뒤 돌아옴).
판정은 '사건' 단위: 신호가 처음 켜진 달에 달러로 바꿨다면 9개월 뒤 원화 예금보다 나빴나.
wk_board.py 가 불러 씀. 단독 실행하면 점검 출력.
"""
import os, sys, calendar
import numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
H = 9


def _rp(s, win=120, minn=36):
    v = s.values; out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]): continue
        h = v[max(0, i - win + 1):i + 1]; h = h[~np.isnan(h)]
        if len(h) >= minn: out[i] = (h <= v[i]).mean()
    return pd.Series(out, index=s.index)


def monthly():
    P = pd.read_pickle(os.path.join(B, "data", "panel.pkl"))["P"]; idx = P.index
    x = pd.read_csv(os.path.join(B, "data", "raw", "ecos_bop_pi_liab.csv"))
    pil = pd.Series(pd.to_numeric(x.iloc[:, 1], errors="coerce").values, index=pd.PeriodIndex(x.iloc[:, 0].astype(str).str[:7], freq="M"))
    pil = pil.groupby(level=0).last().reindex(idx)
    flow = pil.shift(2).rolling(6).sum(); pct = _rp(flow)
    ks6 = P["kospi"] / P["kospi"].shift(6) - 1
    sig = ((pct <= 0.2) & (ks6 < 0)).fillna(False)
    usd = P["cash_us"] * P["usdkrw"]; ck = P["cash_kr"]
    return P, sig, usd, ck, pct, ks6


def episodes(P, sig, usd, ck, since="1995-01"):
    s = sig & (P.index >= pd.Period(since, "M")); on = np.where(s.values)[0]; eps = []
    for i in on:
        if eps and i - eps[-1][1] <= 3: eps[-1][1] = i
        else: eps.append([i, i])
    out = []
    for a, b in eps:
        e = a + H
        if e >= len(P) or np.isnan(usd.iloc[e]) or np.isnan(ck.iloc[e]):
            out.append({"start": str(P.index[a]), "done": False}); continue
        u = usd.iloc[e] / usd.iloc[a]; k = ck.iloc[e] / ck.iloc[a]
        out.append({"start": str(P.index[a]), "done": True, "hit": bool(k > u), "fx": round((P["usdkrw"].iloc[e] / P["usdkrw"].iloc[a] - 1) * 100, 1)})
    return out


AVOID = 0.15; MAXW = 39


def weekly(W):
    """10-21 사용자: '환전을 기본으로 두고, 적어도 이럴 땐 피해야 한다'.
    환전 미루기 = 환율이 5년(260주) 평균보다 15% 넘게 높음. 미룬 돈은 원화 예금에 두었다가 신호가 꺼지면(최대 39주) 환전.
    채점: 그 사건 동안 매주 바꿨을 때 받은 달러(+달러 이자) vs 미뤘다가 받은 달러(원화 이자 포함)."""
    fx = W["usdkrw"]; cu = W["cash_us"]; ck = W["cash_kr"]
    dev = fx / fx.rolling(260).mean() - 1
    on = (dev >= AVOID).fillna(False) & fx.notna()
    s = on.values; n = len(s); eps = []; i = 0
    while i < n:
        if not s[i]: i += 1; continue
        a = i; j = i
        while j < n and (s[j] or j == a) and j - a < MAXW: j += 1
        if j >= n or np.isnan(fx.iloc[j]):
            eps.append({"a": a, "j": None, "done": False}); break
        now = sum((cu.iloc[j] / cu.iloc[t]) / fx.iloc[t] for t in range(a, j))
        later = sum((ck.iloc[j] / ck.iloc[t]) / fx.iloc[j] for t in range(a, j))
        avg_now = (j - a) / sum(1 / fx.iloc[t] for t in range(a, j))
        eps.append({"a": a, "j": j, "done": True, "hit": bool(later > now), "gain": round((later / now - 1) * 100, 1),
                    "fx_a": round(float(avg_now)), "fx_j": round(float(fx.iloc[j]))})
        i = j + 1
    zone = pd.Series(False, index=W.index)
    for e in eps:
        zone.iloc[e["a"]:(e["j"] if e["j"] is not None else n)] = True
    return {"on": on, "zone": zone, "dev": dev, "eps": eps, "fx": float(fx.dropna().iloc[-1]), "dev_now": float(dev.dropna().iloc[-1])}


INV_DEV = 0.10; INV_DROP = 0.05; INV_EXIT = 0.05


def inverse(W):
    """10-21 사용자: '인버스는 더 보수적인 신호로'. 비쌀 때(5년 평균 +10%) 바로가 아니라 13주 고점에서 5% 꺾인 뒤에만.
    청산: 5년 평균 +5% 아래로 내려오면, 최대 39주. 1990~ 7번 중 7번 이익(평균 +10%), 그러나 위기 3번(97·08·22)뿐이고 중간에 최대 21% 손실."""
    fx = W["usdkrw"]; ck = W["cash_kr"]; cu = W["cash_us"]; T = W.index
    dev = fx / fx.rolling(260).mean() - 1; hi13 = fx.rolling(13).max()
    ent = ((dev >= INV_DEV) & (fx <= hi13 * (1 - INV_DROP))).fillna(False).values; n = len(fx); i = 0; eps = []
    while i < n:
        if not ent[i]: i += 1; continue
        a = i; j = a + 1
        while j < n and not (dev.iloc[j] < INV_EXIT) and j - a < 39: j += 1
        if j >= n:
            eps.append({"a": a, "j": None, "done": False}); break
        r = (ck.iloc[j] / ck.iloc[a]) / ((cu.iloc[j] / cu.iloc[a]) * (fx.iloc[j] / fx.iloc[a])) - 1
        eps.append({"a": a, "j": j, "done": True, "r": round(r * 100, 1), "worst": round((fx.iloc[a:j + 1].max() / fx.iloc[a] - 1) * 100, 1)})
        i = j + 1
    live = bool(eps and not eps[-1]["done"])
    return {"eps": eps, "on": live, "entry_now": bool(ent[-1])}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    W = pd.read_pickle(os.path.join(B, "data", "weekly.pkl"))["W"]; f = weekly(W); d = [e for e in f["eps"] if e["done"]]
    print(f"환전 미루기 {len(d)}번 중 이득 {sum(e['hit'] for e in d)}번, 평균 {np.mean([e['gain'] for e in d]):+.1f}%")
    for e in f["eps"]: print(str(W.index[e["a"]])[:10], e)
    print("지금 환율", round(f["fx"]), "5년 평균 대비", round(f["dev_now"] * 100, 1), "%")
