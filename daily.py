# -*- coding: utf-8 -*-
"""일 단위 판정 (2026-10-21, 사용자: '일별로 측정'). 영업일 기준(나스닥 거래일 달력).
가격·금리·달러·실업수당 청구는 그날까지의 값, 월간 거시(물가·수출 등)는 월 패널 값(발표 시차 반영)을 그 달 말 이후에 붙임.
정답 = 앞으로 252거래일 자산 수익 < 현금. 규칙 문턱은 월·주와 같음.
pandas 날짜 연산이 이 PC에서 죽는 경우가 있어 numpy datetime64 로만 다룸.
py daily.py -> data/daily_panel.pkl
"""
import os, sys, csv, calendar
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
M = pd.read_pickle(os.path.join(B, "data", "panel.pkl"))["P"]


def load(n):
    r = [(x["date"], float(x["value"])) for x in csv.DictReader(open(os.path.join(B, "data", "daily", n + ".csv")))]
    return np.array([np.datetime64(a) for a, _ in r]), np.array([b for _, b in r])


DATES, _ = load("y_nasdaq")
DATES = DATES[DATES >= np.datetime64("1971-03-01")]
N = len(DATES)


def on_days(name, max_age=10):
    t, v = load(name); o = np.argsort(t); t, v = t[o], v[o]
    pos = np.searchsorted(t, DATES, side="right") - 1
    out = np.full(N, np.nan); ok = pos >= 0; out[ok] = v[pos[ok]]
    age = np.full(N, 1e9); age[ok] = (DATES[ok] - t[pos[ok]]) / np.timedelta64(1, "D")
    out[age > max_age] = np.nan
    return out


def from_month(col):
    s = M[col].dropna()
    t = np.array([np.datetime64(f"{p.year:04d}-{p.month:02d}-{calendar.monthrange(p.year, p.month)[1]:02d}") for p in s.index])
    pos = np.searchsorted(t, DATES, side="right") - 1
    out = np.full(N, np.nan); ok = pos >= 0; out[ok] = s.values[pos[ok]]; return out


def lag(x, k): y = np.full_like(x, np.nan); y[k:] = x[:-k]; return y
def roll_mean(x, w):
    out = np.full(len(x), np.nan); c = np.nancumsum(np.nan_to_num(x)); n = np.cumsum(~np.isnan(x))
    for i in range(w - 1, len(x)):
        cnt = n[i] - (n[i - w] if i >= w else 0)
        if cnt >= w * 0.9: out[i] = (c[i] - (c[i - w] if i >= w else 0)) / cnt
    return out
def roll_pct(x, win=5040, minn=1260, step=1):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        if np.isnan(x[i]): continue
        h = x[max(0, i - win + 1):i + 1]; h = h[~np.isnan(h)]
        if len(h) >= minn: out[i] = (h <= x[i]).mean()
    return out


def build():
    D = {"date": DATES}
    tb = on_days("f_DTB3"); tb = pd.Series(tb).ffill().values
    D["cash_us"] = np.cumprod(1 + np.nan_to_num(tb) / 100 / 252)
    D["cash_kr"] = from_month("cash_kr")
    for k, f in (("nasdaq", "y_nasdaq"), ("spx", "y_spx"), ("dji", "y_dji"), ("kospi", "y_kospi"), ("oil", "f_DCOILWTICO"), ("dxy", "y_dxy")):
        D[k] = on_days(f)
    D["oil"][D["oil"] <= 0] = np.nan
    y10 = pd.Series(on_days("f_DGS10")).ffill(limit=10).values / 100
    y0 = lag(y10, 1); n = 10 * 252 - 1; c = y0 / 2
    price = c / (y10 / 2) * (1 - (1 + y10 / 2) ** (-n / 126)) + (1 + y10 / 2) ** (-n / 126)
    r = np.nan_to_num(price - 1 + y0 / 252); D["ust10"] = np.where(np.isnan(y10), np.nan, np.cumprod(1 + r))
    y2 = pd.Series(on_days("f_DGS2")).ffill(limit=10).values; y2 = np.where(np.isnan(y2), tb, y2)
    D["d_y2_12"] = y2 - lag(y2, 252)
    ff = pd.Series(on_days("f_DFF")).ffill(limit=10).values; D["d_ff12"] = ff - lag(ff, 252)
    D["dxy12"] = (D["dxy"] / lag(D["dxy"], 252) - 1) * 100
    for c in ("kr_exp_yoy", "d_cpi12", "d_ip_yoy6"):
        D[c] = from_month(c)
    P = pd.DataFrame(D)
    Q = pd.DataFrame({"date": DATES})
    for f in ("d_y2_12", "d_ff12", "dxy12", "kr_exp_yoy", "d_cpi12"):
        Q[f] = roll_pct(P[f].values); print("pct", f, flush=True)
    for a in ("nasdaq", "spx", "kospi", "oil"):
        px = P[a].values; Q["dev5_" + a] = roll_pct(px / roll_mean(px, 1260)); print("pct dev5", a, flush=True)
    return P, Q


if __name__ == "__main__":
    P, Q = build()
    pd.to_pickle({"P": P, "Q": Q}, os.path.join(B, "data", "daily_panel.pkl"))
    print("ok", len(P))
