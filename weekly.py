# -*- coding: utf-8 -*-
"""주 단위 판정 (2026-10-21, 사용자: '달 단위를 주 단위까지 줄일 수 있나').
매주 금요일 기준. 시장 자료(가격·금리·달러·실업수당 청구·금융여건)는 그 주 값, 월간 거시(물가·산업생산·한국 수출·CAPE)는
월 패널(panel.py, 이미 발표 시차 반영)의 그 주까지 나온 마지막 달 값.
정답 = 앞으로 52주 자산 수익 < 같은 기간 현금(3개월 국채). 규칙 문턱은 월 판정과 같음(새로 고르지 않음).
py weekly.py -> data/weekly.pkl , logs/weekly.txt
"""
import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
DD = os.path.join(B, "data", "daily")
M = pd.read_pickle(os.path.join(B, "data", "panel.pkl"))["P"]


def d(name):
    x = pd.read_csv(os.path.join(DD, name + ".csv")); x.index = pd.to_datetime(x["date"]); return x["value"].astype(float)


IDX = pd.date_range("1954-01-08", pd.Timestamp.today(), freq="W-FRI")


def wk(s):
    """일별 → 매주 금요일까지의 마지막 값(14일 넘게 값이 없으면 빈칸).
    10-21: pandas resample 이 이 PC 에서 access violation 으로 죽어 searchsorted 로 직접."""
    s = s.dropna().sort_index()
    t = s.index.values; v = s.values
    pos = np.searchsorted(t, IDX.values, side="right") - 1
    out = np.full(len(IDX), np.nan)
    ok = pos >= 0
    out[ok] = v[pos[ok]]
    age = np.full(len(IDX), np.inf)
    age[ok] = (IDX.values[ok] - t[pos[ok]]) / np.timedelta64(1, "D")
    out[age > 14] = np.nan
    return pd.Series(out, index=IDX)


def despike(s, thr=0.08, agree=0.05):
    """10-21 감사: FRED 일별 값 하루짜리 오류(예: WTI 2026-09-25 85.23, 앞뒤 95.9·99.4) 제거.
    앞날·다음날이 서로 비슷한데(5% 안) 그날만 둘 다에서 8% 넘게 벗어나면 빈칸. 마지막 날은 판단 못 해 그대로."""
    s = s.dropna().sort_index(); v = s.values.copy()
    prv, nxt = np.r_[np.nan, v[:-1]], np.r_[v[1:], np.nan]
    bad = (np.abs(v / prv - 1) > thr) & (np.abs(v / nxt - 1) > thr) & (np.abs(nxt / prv - 1) < agree)
    return s[~bad]


def _month_end(pidx):
    """PeriodIndex → 그 달 마지막 날(to_timestamp 가 이 PC 에서 access violation 으로 죽어 직접 계산)."""
    import calendar
    return pd.to_datetime([f"{p.year:04d}-{p.month:02d}-{calendar.monthrange(p.year, p.month)[1]:02d}" for p in pidx])


def from_month(col, max_age=120):
    """월 패널 값을 그 달 말 이후 주에 붙임(월말 기준으로 알 수 있던 값). 10-21: 120일 넘게 새 값이 없으면 빈칸(끊긴 자료를 영원히 끌고 가지 않게)."""
    s = M[col].dropna().copy(); s.index = _month_end(s.index)
    t = s.index.values; pos = np.searchsorted(t, IDX.values, side="right") - 1
    out = np.full(len(IDX), np.nan); ok = pos >= 0; out[ok] = s.values[pos[ok]]
    age = np.full(len(IDX), np.inf); age[ok] = (IDX.values[ok] - t[pos[ok]]) / np.timedelta64(1, "D"); out[age > max_age] = np.nan
    return pd.Series(out, index=IDX)


def roll_pct(x, win=1040, minn=260):
    v = x.values; out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]): continue
        h = v[max(0, i - win + 1):i + 1]; h = h[~np.isnan(h)]
        if len(h) >= minn: out[i] = (h <= v[i]).mean()
    return pd.Series(out, index=x.index)


def tr_from_price(px, div_yield_annual=0.0):
    r = px.pct_change() + (div_yield_annual / 52 if np.isscalar(div_yield_annual) else div_yield_annual / 52)
    return (1 + r.fillna(0)).cumprod().where(px.notna())


def bond_tr(ye, years):
    y0 = ye.shift(1); n = years * 52 - 1; c = y0 / 2
    price = c / (ye / 2) * (1 - (1 + ye / 2) ** (-n / 26)) + (1 + ye / 2) ** (-n / 26)
    return (1 + (price - 1 + y0 / 52).fillna(0)).cumprod().where(ye.notna())


def build():
    W = pd.DataFrame(index=IDX)
    tb = wk(d("f_DTB3"))
    W["cash_us"] = (1 + tb.fillna(0) / 100 / 52).cumprod()
    for c in ("cash_kr", "cash_jp"):
        W[c] = from_month(c)   # 월 지수를 주에 붙임(한 달 안에서는 평평 — 52주 수익엔 영향 작음)
    shd = pd.read_csv(os.path.join(B, "data/raw/sh_div.csv")); shp = pd.read_csv(os.path.join(B, "data/raw/sh_price.csv"))
    shd.index = pd.PeriodIndex(shd["date"], freq="M"); shp.index = pd.PeriodIndex(shp["date"], freq="M")
    sdy = (shd["value"] / shp["value"]).dropna()
    sdy = sdy.dropna(); sdy.index = _month_end(sdy.index)
    pos = np.searchsorted(sdy.index.values, IDX.values, side="right") - 1
    sdy = pd.Series(np.where(pos >= 0, sdy.values[np.clip(pos, 0, None)], np.nan), index=IDX)
    W["spx"] = tr_from_price(wk(d("y_spx")), sdy)
    W["nasdaq"] = tr_from_price(wk(d("y_nasdaq")), 0.01)
    W["kospi"] = tr_from_price(wk(d("y_kospi")), 0.015)
    W["dji"] = tr_from_price(wk(d("y_dji")), 0.02)
    W["rut"] = tr_from_price(wk(d("y_rut")), 0.013)
    W["sox"] = tr_from_price(wk(d("y_sox")), 0.01)
    W["nikkei"] = tr_from_price(wk(d("y_nikkei")), 0.015)
    for k in ("schd", "btc", "gold_f", "silver_f", "copper_f", "gsci", "em_f", "hy_f", "reit_f"):
        W[k] = wk(d("y_" + k))
    W["oil"] = wk(despike(d("f_DCOILWTICO").where(lambda x: x > 0)))   # WTI 현물 1986~ (2020-04 음수 하루 제외)
    W["ust10"] = bond_tr(wk(d("f_DGS10")) / 100, 10)
    W["ust30"] = bond_tr(wk(d("f_DGS30")) / 100, 30)
    fx = wk(d("f_DEXKOUS")); W["usdkrw"] = fx; W["usd"] = W["cash_us"] * fx
    # ---- 지표 ----
    y2 = wk(d("f_DGS2")).combine_first(tb)
    W["d_y2_12"] = y2 - y2.shift(52)
    ff = wk(d("f_DFF")); W["d_ff12"] = ff - ff.shift(52)
    y10w = wk(d("f_DGS10")); W["d_y10_12"] = y10w - y10w.shift(52)          # 10-21 강한 관망용
    W["oil12"] = ((W["oil"] / W["oil"].shift(52) - 1) * 100).combine_first(from_month("oil12"))   # 10-21: 1992 이전은 월 자료로(없으면 강한 관망이 '3개 중 3개'가 됨)
    dxy = wk(d("y_dxy")); W["dxy12"] = (dxy / dxy.shift(52) - 1) * 100
    ic = wk(d("f_ICSA")).rolling(4).mean(); W["claims"] = (ic / ic.rolling(52).min() - 1) * 100
    nf = wk(d("f_NFCI")); W["d_nfci6"] = nf - nf.shift(26)
    baa = wk(d("f_BAA10Y")).combine_first(from_month("baa_spr")); W["d_spr6"] = baa - baa.shift(26); W["baa_spr"] = baa
    for c in ("d_cpi12", "d_ip_yoy6", "kr_exp_yoy", "cape", "d_real10_12", "core6", "cpi_yoy"):
        W[c] = from_month(c)
    return W


ASSETS = {"spx": "cash_us", "nasdaq": "cash_us", "kospi": "cash_kr", "dji": "cash_us", "rut": "cash_us", "sox": "cash_us",
          "nikkei": "cash_jp", "schd": "cash_us", "btc": "cash_us", "gold_f": "cash_us", "silver_f": "cash_us",
          "copper_f": "cash_us", "gsci": "cash_us", "em_f": "cash_us", "hy_f": "cash_us", "reit_f": "cash_us",
          "oil": "cash_us", "ust10": "cash_us", "ust30": "cash_us", "usd": "cash_kr"}


def targets(W, h=52):
    T = pd.DataFrame(index=W.index)
    for a, c in ASSETS.items():
        fr = W[a].shift(-h) / W[a] - 1; fc = W[c].shift(-h) / W[c] - 1
        T[a + "_ex"] = (fr - fc) * 100
        T[a + "_bad"] = (fr < fc).where(fr.notna() & fc.notna())
    return T


if __name__ == "__main__":
    W = build(); T = targets(W)
    feats = ["d_y2_12", "d_y10_12", "oil12", "d_ff12", "dxy12", "claims", "d_nfci6", "d_spr6", "d_cpi12", "d_ip_yoy6", "kr_exp_yoy", "cape", "d_real10_12"]
    Q = pd.DataFrame({f: roll_pct(W[f]) for f in feats})
    for a in ASSETS:
        px = W[a]; Q["dev5_" + a] = roll_pct(px / px.rolling(260).mean())
    pd.to_pickle({"W": W, "T": T, "Q": Q}, os.path.join(B, "data", "weekly.pkl"))
    for a in ASSETS:
        b = T[a + "_bad"].dropna()
        print(f"{a:9s} {b.index[0].date() if len(b) else '-'} n={len(b):5d} 현금이 나았던 주 {b.mean()*100:5.1f}%")
