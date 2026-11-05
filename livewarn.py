# -*- coding: utf-8 -*-
"""경고를 지금 시세로 다시 계산 (2026-11-06, 사용자: '경고는 일주일 단위고 지금 신호만 실시간 아닌가 → 고쳐줘').
판 규칙(data/rules.json)·20년 백분위(weekly.roll_pct) 그대로, 이번 주 값만 지금 시세로 바꿔 넣음.
- 많이 오름: 주 총수익 지수 × (지금 가격 / 그 주 일봉)
- 2년물·10년물: FRED 마지막 값 + 그날 뒤 야후 변화 · 유가: FRED 마지막 값 × 그날 뒤 선물 변화
- 물가·수출·실업청구: 마지막 값 그대로(월·주 자료)
규칙 검증은 금요일 종가 기준이라 장중 값은 추정. 판 자체는 금요일 단위로만 넘어감."""
import os, json, datetime, subprocess
import numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_c = {"mt": None}


def _data():
    f = os.path.join(B, "data", "weekly.pkl"); mt = os.path.getmtime(f)
    if _c["mt"] != mt:
        D = pd.read_pickle(f); _c.update(mt=mt, W=D["W"], Q=D["Q"])
    return _c["W"], _c["Q"]


def _daily(n):
    x = pd.read_csv(os.path.join(B, "data", "daily", n + ".csv")); x.index = pd.to_datetime(x["date"]); return x["value"].astype(float).dropna()


def _at(s, t):
    return float(s[s.index <= t].iloc[-1])


def _yahoo(sym):
    """(지금 값, {날짜: 종가}) 최근 한 달"""
    t = subprocess.run(["curl", "-s", "-m", "20", "-A", UA, f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=1d"], capture_output=True, timeout=30).stdout.decode("utf-8", "replace")
    r = json.loads(t)["chart"]["result"][0]; q = r["indicators"]["quote"][0]["close"]
    ds = {datetime.datetime.utcfromtimestamp(a).date(): b for a, b in zip(r["timestamp"], q) if b is not None}
    return float(r["meta"]["regularMarketPrice"]), ds


def _since(sym, day):
    """FRED 마지막 날(day) 뒤 야후 값이 얼마나 움직였나 → (지금, 그날 값)"""
    now, ds = _yahoo(sym); ks = [k for k in sorted(ds) if k <= day.date()]
    return now, float(ds[ks[-1]]) if ks else now


def _pct(hist, v, win=1040):
    h = hist.dropna().values[-(win - 1):]; h = np.append(h, v); return float((h <= v).mean())


def evaluate(prices, neutral=False):
    """prices: {자산: 지금 가격}. neutral=True 면 지금 시세 대신 판 자료 값 그대로(검증용).
    반환 {us_strong, us_warn, kospi_warn, turn, q:{재료: 백분위}}"""
    W, Q = _data()
    td = datetime.date.today(); fri = pd.Timestamp((td + datetime.timedelta(days=(4 - td.weekday()) % 7)).isoformat())   # 이 PC 판다스: Timedelta 덧셈이 죽음
    cur = W.index[-1] >= fri                 # 이번 주 줄이 이미 있으면 그 줄을 지금 값으로 바꿈, 없으면 새 줄
    if neutral: fri, cur = W.index[-1], True
    prev = W.iloc[:-1] if cur else W
    ago = pd.Timestamp((fri.date() - datetime.timedelta(days=364)).isoformat())
    qv = {}; rw = {}; need = {}
    for c in Q.columns: qv[c] = float(Q[c].dropna().iloc[-1]) if Q[c].notna().any() else np.nan
    # 금리: 1년 변화
    for c, n, sym in (("d_y2_12", "f_DGS2", "2YY=F"), ("d_y10_12", "f_DGS10", "^TNX")):
        s = _daily(n); base = float(s.iloc[-1])
        try:
            if neutral: v = base
            else: a, b = _since(sym, s.index[-1]); v = base + a - b
            rw[c] = v - _at(s, ago); qv[c] = _pct(prev[c], rw[c])
        except Exception: pass
    # 유가: 1년 변화 %
    try:
        s = _daily("f_DCOILWTICO"); base = float(W["oil"].dropna().iloc[-1])
        if neutral: v = base
        else: a, b = _since("CL=F", s.index[-1]); v = base * a / b
        y0 = float(W["oil"][W.index <= ago].dropna().iloc[-1]); rw["oil12"] = (v / y0 - 1) * 100; qv["oil12"] = _pct(prev["oil12"], rw["oil12"])
    except Exception: pass
    # 많이 오름: 5년 평균 대비
    for a, p in prices.items():
        try:
            px = W[a].dropna(); d = _daily("y_" + a); base = _at(d, W.index[-1])
            r = 1.0 if neutral or p is None else p / base
            pv = px.iloc[:-1] if px.index[-1] >= fri else px
            nowv = float(px.iloc[-1]) * r
            dev = pv / pv.rolling(260).mean()
            dv = nowv / float(np.append(pv.values[-259:], nowv).mean()); qv["dev5_" + a] = _pct(dev, dv); rw["dev5_" + a] = (dv - 1) * 100
            for th in (.7, .8): need[(a, th)] = (float(np.quantile(dev.dropna().values[-1039:], th)) / dv - 1) * 100
        except Exception: pass
    R = json.load(open(os.path.join(B, "data", "rules.json"), encoding="utf-8"))
    def on(r):
        cnt = sum((qv[c] >= q) if op == ">=" else (qv[c] <= q) for c, op, q in r["conds"])
        return cnt >= r.get("k", len(r["conds"])) and (r.get("dev") is None or qv["dev5_" + r["asset"]] >= r["dev"])
    us_s = us_w = kw = False
    for r in R:
        if r.get("status") != "확정" or r["kind"] not in ("관망", "강한관망"): continue
        if r["asset"] in ("nasdaq", "spx"):
            if on(r):
                if r["kind"] == "강한관망": us_s = True
                else: us_w = True
        elif r["asset"] == "kospi" and on(r): kw = True
    # 조심 구간: 경고 중·꺼진 지 26주 안·하락 추세 (_nosell.py: 13주는 너무 일러 2001년에 크게 다침, 26·52주는 비슷)(10개월선 아래 + 선이 13주 전보다 낮음)
    def recent(asset_list):
        h = pd.Series(False, index=Q.index)
        for r in R:
            if r.get("status") != "확정" or r["kind"] not in ("관망", "강한관망") or r["asset"] not in asset_list: continue
            cnt = sum(((Q[c] >= q) if op == ">=" else (Q[c] <= q)).fillna(False).astype(int) for c, op, q in r["conds"])
            m = cnt >= r.get("k", len(r["conds"]))
            if r.get("dev") is not None: m = m & (Q["dev5_" + r["asset"]] >= r["dev"]).fillna(False)
            h = h | m
        return bool(h.iloc[-26:].any())
    reg = {}; state = {}
    for a in prices:
        px = W[a].dropna(); ma = px.rolling(43).mean()
        bear = bool(px.iloc[-1] < ma.iloc[-1] and ma.iloc[-1] < ma.iloc[-14])
        warn_ = kw if a == "kospi" else (us_s or us_w)
        rc_ = recent(["kospi"] if a == "kospi" else ["nasdaq", "spx"]); reg[a] = warn_ or bear or rc_
        state[a] = "하락 추세" if bear else "경고 중" if warn_ else "경고 꺼진 6개월" if rc_ else "평시"
    # 왜 이 상태인가
    def item(lab, c, th, unit=""):
        x = rw.get(c); return {"k": lab + (f" ({x:+.2f}{unit})" if x is not None and unit == "%p" else f" ({x:+.0f}{unit})" if x is not None else ""), "v": round(qv[c] * 100), "th": round(th * 100), "on": bool(qv[c] >= th)}
    def last_on(lst):
        h = pd.Series(False, index=Q.index)
        for r in R:
            if r.get("status") != "확정" or r["kind"] not in ("관망", "강한관망") or r["asset"] not in lst: continue
            cnt = sum(((Q[c] >= q) if op == ">=" else (Q[c] <= q)).fillna(False).astype(int) for c, op, q in r["conds"])
            m = cnt >= r.get("k", len(r["conds"]))
            if r.get("dev") is not None: m = m & (Q["dev5_" + r["asset"]] >= r["dev"]).fillna(False)
            h = h | m
        return h[h].index[-1] if h.any() else None
    pr = [item("2년물 1년 변화", "d_y2_12", .7, "%p"), item("10년물 1년 변화", "d_y10_12", .8, "%p"), item("유가 1년 변화", "oil12", .8, "%"), item("물가 가속", "d_cpi12", .7)]
    npr = sum(x["on"] for x in pr); sp_d = item("S&P 많이 오름(5년 평균 대비)", "dev5_spx", .8, "%"); nq_d = item("나스닥 많이 오름(5년 평균 대비)", "dev5_nasdaq", .8, "%")
    lu = last_on(["nasdaq", "spx"]); lk = last_on(["kospi"])
    end = lambda t: (t.date() + datetime.timedelta(days=182)).isoformat() if t is not None else None
    if us_s or us_w:
        msg = ("S&P 많이 오름 + 압력 %d/4" % npr if us_s else "나스닥 많이 오름 + 2년물 급등") + " → 켜짐."
        if us_s: msg += f" S&P가 {need.get(('spx', .8), 0):+.1f}% 내려가면 많이 오름이 문턱 아래로 가서 꺼져요."
    else:
        msg = f"S&P 많이 오름이 {sp_d['v']}%로 문턱 80% 아래라 꺼짐. 금리·유가 압력은 {npr}/4로 그대로예요. 주가가 빠져서 꺼진 거지 위험이 끝난 건 아니에요."
        if npr >= 3: msg += f" S&P가 {need.get(('spx', .8), 0):+.1f}% 오르면 다시 켜져요."
        if lu is not None: msg += f" 이대로면 조심 구간은 {end(lu)}쯤 끝나요."
    kd = item("코스피 많이 오름(5년 평균 대비)", "dev5_kospi", .7, "%"); kx = item("한국 수출 증가율", "kr_exp_yoy", .7)
    km = (f"많이 오름·수출 둘 다 문턱 위라 켜짐. 수출이 {kx['v']}%라 코스피가 {need.get(('kospi', .7), 0):+.1f}% 빠져야 꺼져요." if kw else "많이 오름이나 수출이 문턱 아래라 꺼짐." + (f" 이대로면 조심 구간은 {end(lk)}쯤 끝나요." if lk is not None else ""))
    detail = {"us": {"name": "미국 경고 (S&P 강한 경고 또는 나스닥 경고)", "on": bool(us_s or us_w), "items": [sp_d, nq_d] + pr, "msg": msg},
              "kospi": {"name": "코스피 경고", "on": bool(kw), "items": [kd, kx], "msg": km},
              "turn": {"name": "경기 꺾임", "on": bool(qv["claims"] >= .8 and qv["kr_exp_yoy"] >= .8), "items": [{"k": "실업수당 청구", "v": round(qv["claims"] * 100), "th": 80, "on": bool(qv["claims"] >= .8)}, {"k": "한국 수출 증가율", "v": round(qv["kr_exp_yoy"] * 100), "th": 80, "on": bool(qv["kr_exp_yoy"] >= .8)}], "msg": "고용이 깨지기 시작하는데 수출은 꼭대기면 침체 입구. 켜지면 조심 구간이에요."}}
    return {"detail": detail, "reg": reg, "state": state, "us_strong": us_s, "us_warn": us_s or us_w, "kospi_warn": kw, "turn": qv["claims"] >= .8 and qv["kr_exp_yoy"] >= .8, "q": qv}
