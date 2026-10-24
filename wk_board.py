# -*- coding: utf-8 -*-
"""주 단위 자산 신호판 (2026-10-21, 사용자: '핸드폰에서 보기 쉽게, 살 것·팔 것').
상태 = 매수(검증된 매수 신호) / 관망(검증된 관망 신호 + 마지막 신호 뒤 52주) / 보통(둘 다 아님).
확률 = 과거 같은 상태였던 주들 가운데 52주 뒤 그 자산이 현금(3개월 국채)보다 나았던 비율.
구리만 일별 자료가 2000년부터라 월 단위(panel.py) 그대로.
py wk_board.py -> board.html (board_tpl.html 에 자료를 넣음)
"""
import os, sys, json, datetime
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(os.path.join(B, "data", "weekly.pkl")); W, T, Q = D["W"], D["T"], D["Q"]


def buy_w(a):
    px = W[a]; up = px > px.rolling(43).mean()
    dd52 = (px / px.rolling(52).max() - 1).rolling(52).min()
    return ((dd52 <= -0.2) & up & (px / px.cummax() - 1 <= -0.1)).fillna(False)


A = [  # id, 이름, 상품 예, 관망 규칙, 매수 규칙, 관망 규칙 설명
    ("nasdaq", "나스닥", "QQQ · 나스닥100 ETF", lambda: (Q["dev5_nasdaq"] >= 0.8) & (Q["d_y2_12"] >= 0.7), lambda: buy_w("nasdaq"), "많이 오른 상태 + 미 2년물 금리 급등"),
    ("spx", "S&P500", "SPY · VOO", lambda: strong_w("spx"), lambda: buy_w("spx"), "많이 오른 상태 + 과열 압력 3개 이상(강한 관망만)"),
    ("dji", "다우", "DIA · SCHD와 비슷", None, lambda: buy_w("dji"), None),
    ("kospi", "코스피", "KODEX 200 등", lambda: (Q["dev5_kospi"] >= 0.7) & (Q["kr_exp_yoy"] >= 0.7),
     lambda: (Q["dev5_kospi"] <= 0.2).fillna(False), "많이 오른 상태 + 한국 수출 증가율 정점"),   # 10-21 매수: 5년 평균 대비 하위 20%(2000년 이후 검증, 사용자 '20년 넘게 맞으면 믿는다')
    ("ust10", "미국채 10년", "IEF", lambda: (Q["d_cpi12"] >= 0.7) & (Q["d_ff12"] >= 0.7), None, "물가 상승 가속 + 연준 금리 인상"),
    ("oil", "원유", "유가(ETF는 수익이 다를 수 있음)", lambda: (Q["dev5_oil"] >= 0.7) & (Q["dxy12"] >= 0.7), None, "많이 오른 상태 + 달러 강세"),
]
from weekly import wk, d as dly
DISP = {"nasdaq": lambda: wk(dly("y_nasdaq")), "spx": lambda: wk(dly("y_spx")), "dji": lambda: wk(dly("y_dji")), "kospi": lambda: wk(dly("y_kospi"))}
UNIT_W = {"nasdaq": "pt", "spx": "pt", "dji": "pt", "kospi": "pt", "ust10": "총수익지수", "oil": "$/배럴"}
BUY_TXT = "고점에서 20% 넘게 빠진 뒤 다시 오르기 시작"
# 10-21 강한 관망: 많이 오른 상태 + 과열 압력 4개(2년물 급등·10년물 급등·물가 가속·유가 급등) 중 3개 이상
#   월 검증: 나스닥 1년 뒤 현금이 나음 88%·1년 안 -20% 75%(4번), S&P 83%·35%(6번, 1987 포함), 러셀 92%(안 본 시장). 일본·신흥국은 안 맞음.
PRESS = {"2년물 급등": ("d_y2_12", 0.7), "10년물 급등": ("d_y10_12", 0.8), "물가 가속": ("d_cpi12", 0.7), "유가 급등": ("oil12", 0.8)}
def press_cnt(): return sum((Q[c] >= q).astype(int) for c, q in PRESS.values())
def strong_w(a): return ((Q["dev5_" + a] >= 0.8) & (press_cnt() >= 3)).fillna(False)
STRONG = {"nasdaq", "spx"}
BUY_TXT_ID = {"kospi": "5년 평균보다 많이 싸짐(하위 20%) · 2000년 이후 검증"}


def fmt(ts):
    return f"{ts.year}.{ts.month:02d}.{ts.day:02d}"


def ranges(s, idx):
    s = s.fillna(False).values; out = []; st = None
    t = [round(x.year + (x.dayofyear - 1) / 365.25, 3) for x in idx]
    for i, v in enumerate(s):
        if v and st is None: st = i
        if not v and st is not None: out.append([t[st], t[i - 1] + 1 / 52]); st = None
    if st is not None: out.append([t[st], t[-1] + 1 / 52])
    return out


def registry():
    """10-21 판단 루프(evolve.py)가 관리하는 규칙 목록. 없으면 예전 고정 규칙(A) 그대로."""
    f = os.path.join(B, "data", "rules.json"); g = os.path.join(B, "data", "evolve_state.json")
    if not os.path.exists(f): return None, {}
    return json.load(open(f, encoding="utf-8")), (json.load(open(g, encoding="utf-8")) if os.path.exists(g) else {})


def main():
    out = []
    R, ST = registry()
    if R is not None:
        import evolve as EV
    for aid, name, prod, sell, buy, rule in A:
        px = W[aid]; valid = px.notna(); F0 = pd.Series(False, index=W.index)
        ev = {"tier_sell": None, "tier_buy": None, "sell_ev": [], "buy_ev": [], "strong_ref": False, "cands": [], "checked": ST.get("checked")}
        if R is None:
            sig = sell().fillna(False) & valid if sell else F0
            bs = buy().fillna(False) & valid if buy else F0
            strong = strong_w(aid) & valid if aid in STRONG else F0
            strong_draw = strong
        else:
            # 10-21 사용자: '검증 확률 안 높으면 갖다 버려' → 루프가 확정했고 사건 단위 75% 이상인 규칙만
            def strong_ok(r):
                sc_ = ST.get("scores", {}).get(r["id"])
                return r["status"] == "확정" and sc_ and sc_["n"] >= 4 and sc_["k"] / sc_["n"] >= 0.75
            mine = [r for r in R if r["asset"] == aid and strong_ok(r)]
            def orsig(rs): 
                s = F0.copy()
                for r in rs: s = s | EV.signal(r, aid, EV.FW).reindex(W.index).fillna(False)
                return s & valid
            sc = lambda rs: [{"desc": ST["scores"][r["id"]]["desc"], "k": ST["scores"][r["id"]]["k"], "n": ST["scores"][r["id"]]["n"], "status": r["status"], "frame": ST["scores"][r["id"]].get("frame"),
                              "live": ST["scores"][r["id"]]["live"], "since": r["since"]} for rs_ in [rs] for r in rs_ if r["id"] in ST.get("scores", {})]
            sc_, sr_ = [r for r in mine if r["kind"] in ("관망", "강한관망") and r["status"] == "확정"], [r for r in mine if r["kind"] in ("관망", "강한관망") and r["status"] == "참고"]
            bc_, br_ = [r for r in mine if r["kind"] == "매수" and r["status"] == "확정"], [r for r in mine if r["kind"] == "매수" and r["status"] == "참고"]
            use_s = sc_ or sr_; use_b = bc_ or br_
            sig = orsig([r for r in use_s if r["kind"] == "관망"]); strong = orsig([r for r in sc_ if r["kind"] == "강한관망"])
            if not sc_: strong = orsig([r for r in sr_ if r["kind"] == "강한관망"]) & False
            bs = orsig(use_b)
            ev["tier_sell"] = ("확정" if sc_ else "참고") if use_s else None; ev["tier_buy"] = ("확정" if bc_ else "참고") if use_b else None
            ev["sell_ev"] = sc(use_s); ev["buy_ev"] = sc(use_b)
            sref = [r for r in sr_ if r["kind"] == "강한관망"] if sc_ else []
            ev["strong_ref"] = bool(orsig(sref).iloc[-1]) if sref else False
            strong_draw = strong | orsig([r for r in sr_ if r["kind"] == "강한관망"])   # 10-21 사용자: 강한 관망은 빨강으로(참고 등급 포함)
            ev["strong_ref_ev"] = sc(sref)
            ev["cands"] = [ST["scores"][r["id"]]["desc"] for r in R if r["asset"] == aid and r["status"] == "후보" and r["id"] in ST.get("scores", {})]
            if not use_s: sell = None
            if aid == "dji":
                # 10-21 사용자 '다우 82%면 사야 하나' → 다우는 자기 경고 규칙이 없지만 미국 대형주라 나스닥·S&P 경고를 그대로 따름
                #   (미국 경고 중 다우를 샀으면 1년 뒤 현금보다 나음 24%, 사건 4번 중 1번 = 경고가 3번 맞음)
                us_r = [r for r in R if r["asset"] in ("nasdaq", "spx") and r["kind"] in ("관망", "강한관망") and strong_ok(r)]
                usig = F0.copy()
                for r in us_r: usig = usig | EV.signal(r, r["asset"], EV.FW).reindex(W.index).fillna(False)
                sig = usig & valid
                px_, c_ = W["dji"], W["cash_us"]; eps_ = []
                for i in np.where(sig.values)[0]:
                    if eps_ and i - eps_[-1][1] <= 26: eps_[-1][1] = i
                    else: eps_.append([i, i])
                # 채점: 경고가 처음 켜진 주에 다우를 새로 샀다면 1년 뒤 현금보다 못했나(= 사지 않은 게 맞았나).
                #   팔고 1년 더 기다리는 것까지는 다우에선 4번 중 1번만 맞아서 '팔기'는 안 함 → 경고 중 '새로 사지 않기'만
                kk_ = nn_ = 0
                for a_, b_ in eps_:
                    e_ = a_ + 52
                    if e_ < len(W) and not np.isnan(px_.iloc[e_]):
                        nn_ += 1; kk_ += bool(c_.iloc[e_] / c_.iloc[a_] > px_.iloc[e_] / px_.iloc[a_])
                ev["tier_sell"] = "확정"; ev["nobuy"] = True
                ev["sell_ev"] = [{"desc": "미국 경고 중 새로 사지 않기", "k": kk_, "n": nn_, "status": "확정", "live": {"n": 0, "k": 0}}]
                use_s = us_r; rule = "나스닥 관망 또는 S&P 강한 관망이 켜져 있는 동안 새로 사지 않기 (들고 있으면 그대로)"; sell = True
            if not use_s and not use_b and aid != "dji": continue     # 검증된 규칙이 없는 자산은 빼기(다우는 평소 확률 74%·34번으로 남김)
            if not use_b: buy = None
            rule = " / ".join(x["desc"] for x in ev["sell_ev"]) or None
        sig = sig | strong
        # 10-21 사용자: '빨강일 때 매수 신호 떠도 사면 안 되는 거 아님?' → 경고 중·마지막 경고 뒤 6개월은 매수 무시
        #   (경고 켜진 중 매수: 나스닥 2000-04 1년 뒤 -43%, 경고 직후 2000-07 -52%. 6개월 지난 뒤 매수는 5/6 이득)
        bs = bs & ~sig.astype(int).rolling(26, min_periods=1).max().astype(bool)
        fb = fear_buy(aid, sig) if aid in FEAR else None
        if fb is not None:
            bs = bs | fb["sig"]
            ev.setdefault("buy_ev", []); ev["buy_ev"] = list(ev["buy_ev"]) + [fb["ev"]]
        # 10-21 조건 점검: 나스닥·S&P는 서로의 매수 신호도 따름(상대만 켜졌을 때 사서 1년 뒤: 나스닥 10번 중 9번, S&P 19번 중 15번)
        if R is not None and aid in ("nasdaq", "spx"):
            oth = "spx" if aid == "nasdaq" else "nasdaq"
            ob = F0.copy(); ow = F0.copy()
            for r in R:
                if r["asset"] == oth and strong_ok(r):
                    if r["kind"] == "매수": ob = ob | EV.signal(r, oth, EV.FW).reindex(W.index).fillna(False)
                    else: ow = ow | EV.signal(r, oth, EV.FW).reindex(W.index).fillna(False)
            ob = ob | fear_buy(oth, ow)["sig"]
            only = ob & ~bs & valid
            px_, c_ = W[aid], W["cash_us"]; eps_ = []
            for i in np.where(only.values)[0]:
                if eps_ and i - eps_[-1][1] <= 26: eps_[-1][1] = i
                else: eps_.append([i, i])
            res_ = [bool(px_.iloc[a_ + 52] / px_.iloc[a_] > c_.iloc[a_ + 52] / c_.iloc[a_]) for a_, _ in eps_ if a_ + 52 < len(W) and not np.isnan(px_.iloc[a_ + 52])]
            if res_ and len(res_) >= 4 and sum(res_) / len(res_) >= 0.75:
                bs = (bs | (ob & valid)) & ~sig.astype(int).rolling(26, min_periods=1).max().astype(bool)
                ev["buy_ev"] = list(ev.get("buy_ev", [])) + [{"desc": f"{'S&P' if oth == 'spx' else '나스닥'} 매수 신호 따라감", "k": int(sum(res_)), "n": len(res_), "status": "확정", "live": {"n": 0, "k": 0}}]
                ev["buy_follow"] = "S&P500" if oth == "spx" else "나스닥"
        hold = sig.astype(int).rolling(52, min_periods=1).max().astype(bool)
        if ev.get("nobuy"): hold = sig.copy()      # 다우: 경고 뒤 1년 유지 없음(유지 기간에 산 건 4번 중 2번으로 반반)
        # 10-21: 관망을 '신호 켜진 주'와 '꺼진 뒤 52주 유지'로 나눔(섞으면 확률이 흐려짐: 나스닥 80% → 57%)
        st = pd.Series("보통", index=W.index); st[hold] = "관망유지"; st[sig] = "관망"; st[strong] = "강한관망"; st[bs] = "매수"
        pv = px.values; fmin = pd.Series(pv[::-1]).rolling(52, min_periods=52).min().values[::-1]
        fmin = np.r_[fmin[1:], np.nan]; dd20 = pd.Series(np.where(np.isnan(fmin), np.nan, (fmin / pv - 1 <= -0.2).astype(float)), index=W.index)
        bad = T[aid + "_bad"]; ex = T[aid + "_ex"]
        start = px.first_valid_index()
        if R is not None and use_s:   # 10-21 감사: 규칙에 실제로 쓰인 재료가 다 있는 첫 주부터
            ins = sorted({c for r in use_s for c, _, _ in r.get("conds", [])} | ({"dev5_" + aid} if any(r.get("dev") is not None for r in use_s) else set()))
            start = max([start] + [Q[c].first_valid_index() for c in ins])
        elif sell: start = max(start, sig.index[(Q.get("dev5_" + aid, Q["d_cpi12"]).notna()).values.argmax()])
        v = valid & bad.notna() & (W.index.values >= np.datetime64(start.date()))
        stats = {}
        for k in ("매수", "보통", "관망", "관망유지", "강한관망"):
            m = v & (st == k)
            if m.sum() >= 10:
                stats[k] = {"p": round(float(1 - bad[m].mean()) * 100), "med": round(float(ex[m].median()), 1),
                            "low": round(float(ex[m].quantile(.1)), 1), "share": round(float(m.sum() / v.sum()) * 100),
                            "dd20": round(float(dd20[m & dd20.notna()].mean()) * 100) if (m & dd20.notna()).sum() else None}
                # 10-21 사용자: '30일 켜지면 30번이 한 번에 자료가 됨' → 1년씩 안 겹치게 뽑아 셈(한 번 뽑으면 52주 건너뜀)
                ii = np.where(m.values)[0]; take = []; nxt = -1
                for i in ii:
                    if i >= nxt: take.append(i); nxt = i + 52
                good = [(1 - bad.iloc[i]) for i in take]
                stats[k]["n1"] = len(take); stats[k]["k1"] = int(sum(good))
        now = st[valid].iloc[-1]; last = W.index[valid][-1]
        until = None
        if now in ("관망", "관망유지", "강한관망"):
            lastsig = sig[sig].index[-1]
            until = str(np.datetime64(lastsig.date()) + np.timedelta64(357, "D")).replace("-", ".")
        lastbuy = fmt(bs[bs].index[-1]) if bs.any() else None
        since = None
        chg = st[valid] != now
        if chg.any():
            sv = st[valid]; prev = sv[chg].index[-1]; since = fmt(sv.index[sv.index.values > np.datetime64(prev.date())][0])
        keep = pd.Series(W.index.values >= np.datetime64("1990-01-01"), index=W.index)
        dpx = DISP[aid]() if aid in DISP else px          # 10-21: 화면은 실제 값(지수 포인트·달러), 신호는 총수익 지수
        dser = dpx[keep & valid].dropna(); dser = dser[dser > 0]
        p = [[round(x.year + (x.dayofyear - 1) / 365.25, 3), float(f"{y:.4g}")] for x, y in dser.items()]
        # 10-21 사용자: 띠 색과 선 색이 겹치거나 어긋남 → 주마다 상태 하나(매수 > 강한 관망 > 관망 > 관망 유지 > 보통)로 띠·선을 같이 칠함
        st_draw = st.copy(); st_draw[strong_draw & st.isin(["관망", "강한관망"])] = "강한관망"
        # 10-21: 강한 관망 뒤 1년은 따로(빨간 빗금) — 나스닥 그 기간 1년 안 -20% 36% vs 보통 관망 뒤 4%, S&P 16% vs 0%
        st_draw[(st == "관망유지") & strong_draw.astype(int).rolling(52, min_periods=1).max().astype(bool)] = "강한유지"
        scode = "".join(st_draw.reindex(dser.index).map({"매수": "M", "강한관망": "R", "관망": "O", "관망유지": "H", "강한유지": "S"}).fillna("N").values)
        out.append({"id": aid, "name": name, "prod": prod, "rule": rule, "buyrule": BUY_TXT_ID.get(aid, BUY_TXT) if buy else None, "unit": UNIT_W.get(aid, ""),
                    "now": now, "since": since, "until": until, "lastbuy": lastbuy, "stats": stats,
                    "press": [k for k, (c, q) in PRESS.items() if bool((Q[c] >= q).iloc[-1])] if aid in STRONG else [], "ev": ev,
                    "marks": marks_for(sig, dpx.reindex(W.index), px, W["cash_kr" if aid == "kospi" else "cash_us"], "sell") + marks_for(bs, dpx.reindex(W.index), px, W["cash_kr" if aid == "kospi" else "cash_us"], "buy"),
                    "p": p, "s": scode, "sell": ranges(sig & keep, W.index), "strong": ranges(strong_draw & keep, W.index), "hold": ranges(hold & ~sig & keep, W.index), "buy": ranges(bs & keep, W.index), "bad": ranges((bad == 1) & keep, W.index),
                    "known": round(bad.last_valid_index().year + bad.last_valid_index().dayofyear / 365.25, 3), "asof": fmt(last)})
        print(name, now, since, until, stats)
    out.insert(0, fx_card(keep))
    tpl = open(os.path.join(B, "board_tpl.html"), encoding="utf-8").read()
    html = tpl.replace("__CHART_JS__", open(os.path.join(B, "chart_core.js"), encoding="utf-8").read()).replace("__JIPSEM_CSS__", open(os.path.join(B, "jipsem_style.css"), encoding="utf-8").read()) \
              .replace("__DATA__", json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o))).replace("__EVOLOG__", json.dumps(evolog(), ensure_ascii=False)).replace("__TB3__", tb3()).replace("__ASOF__", out[0]["asof"])
    open(os.path.join(B, "board.html"), "w", encoding="utf-8").write(html)
    print("ok", len(html))


FEAR = {"nasdaq": "y_nasdaq", "spx": "y_spx"}


def fear_buy(aid, sig):
    """10-21 사용자: 'RSI·공포지수로 바닥 잡기'. 일봉 RSI(14) 30 미만 + 공포지수(VIX) 30 이상인 날이 있는 주.
    단, 관망 경고 중이거나 마지막 경고 뒤 1년 안이면 안 씀(2000~01·2022 거품 붕괴 땐 계속 더 빠짐).
    1990~ 나스닥 1년 뒤 17번 중 15번 상승(평균 +32%), S&P 16번 중 14번. 틀린 2번 = 2001-09·2008-01."""
    import csv
    def load(n):
        r = [(x["date"], float(x["value"])) for x in csv.DictReader(open(os.path.join(B, "data", "daily", n + ".csv")))]
        d = np.array([np.datetime64(a) for a, _ in r]); v = np.array([b for _, b in r]); o = np.argsort(d); return d[o], v[o]
    d, p = load(FEAR[aid]); vd, vv = load("f_VIXCLS")
    sd = pd.Series(p).diff(); up = sd.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); dn = (-sd.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    r14 = (100 - 100 / (1 + up / dn)).values
    pos = np.searchsorted(vd, d, side="right") - 1; vix = np.where(pos >= 0, vv[np.clip(pos, 0, None)], np.nan)
    hit = (r14 < 30) & (vix >= 30)
    wk = np.searchsorted(W.index.values.astype("datetime64[D]"), d, side="left")        # 그 날이 속한 주(금요일)
    s = np.zeros(len(W), bool); ok = wk < len(W); s[wk[ok & hit]] = True
    hold = sig.astype(int).rolling(52, min_periods=1).max().astype(bool).values
    s = pd.Series(s & ~hold, index=W.index)
    # 근거(사건 단위, 1년 뒤 가격)
    px = W[aid]; c = W["cash_us"]; eps = []
    for i in np.where(s.values)[0]:
        if eps and i - eps[-1][1] <= 4: eps[-1][1] = i
        else: eps.append([i, i])
    res = [px.iloc[a + 52] / px.iloc[a] > c.iloc[a + 52] / c.iloc[a] for a, _ in eps if a + 52 < len(W) and not np.isnan(px.iloc[a + 52])]
    return {"sig": s, "ev": {"desc": "공포 매수: RSI 30 미만 + 공포지수 30 이상", "k": int(sum(res)), "n": len(res), "status": "참고", "live": {"n": 0, "k": 0}}}


def marks_for(sig, dpx, px, cash, kind, gap=26, h=52):
    """10-21 사용자: '이때 경고였는데 이때 낮아졌죠' — 신호가 처음 켜진 주 → 1년 뒤를 화살표로."""
    out = []; v = sig.fillna(False).values; idx = W.index; last = len(v) - 1; eps = []
    for i in np.where(v)[0]:
        if eps and i - eps[-1][1] <= gap: eps[-1][1] = i
        else: eps.append([i, i])
    tt = lambda i: round(idx[i].year + (idx[i].dayofyear - 1) / 365.25, 3)
    for a, e in eps:
        if np.isnan(dpx.iloc[a]): continue
        end = (e if kind == "sell" else a) + h          # 경고: 마지막 경고 뒤 1년까지(실제로 따라 하는 기간) · 매수: 1년
        b = min(end, last); done = end <= last
        while b > a and np.isnan(dpx.iloc[b]): b -= 1
        chg = dpx.iloc[b] / dpx.iloc[a] - 1
        if done and not np.isnan(px.iloc[b]):
            beat = px.iloc[b] / px.iloc[a] > cash.iloc[b] / cash.iloc[a]
            ok = (not beat) if kind == "sell" else beat
        else: ok = None
        out.append({"t0": tt(a), "v0": float(f"{dpx.iloc[a]:.4g}"), "t1": tt(b), "v1": float(f"{dpx.iloc[b]:.4g}"), "kind": kind, "ok": ok,
                    "d0": fmt(idx[a])[:7], "chg": round(chg * 100), "done": done})
    return out


def fx_card(keep):
    """10-21 사용자: '환전을 기본으로 두고, 적어도 이럴 땐 환전 피해야 한다'.
    환전 미루기 = 환율이 5년 평균보다 15% 넘게 높음 → 원화로 두었다가 꺼지면(최대 9개월) 환전. fx_signal.weekly 참고."""
    import fx_signal as FXS
    f = FXS.weekly(W); fx = W["usdkrw"]; valid = fx.notna(); idx = W.index
    tt = lambda i: round(idx[i].year + (idx[i].dayofyear - 1) / 365.25, 3)
    cyc = []                      # 1~2주씩 끊긴 신호는 한 번(26주 안)으로 묶음
    for e in f["eps"]:
        if not e["done"]: cyc.append(dict(e, parts=[e])); continue
        if cyc and cyc[-1]["done"] and e["a"] - cyc[-1]["j"] <= 26:
            c = cyc[-1]; c["parts"].append(e); c["j"] = e["j"]; c["fx_j"] = e["fx_j"]
        else: cyc.append(dict(e, parts=[e]))
    marks = []; k = n = 0; gains = []
    for c in cyc:
        if idx[c["a"]] < pd.Timestamp("1990-01-01"): continue
        if not c["done"]:
            marks.append({"t0": tt(c["a"]), "v0": round(float(fx.iloc[c["a"]])), "t1": tt(len(idx) - 1), "v1": round(float(fx.dropna().iloc[-1])), "kind": "defer", "ok": None, "d0": fmt(idx[c["a"]])[:7], "done": False}); continue
        w = [p["j"] - p["a"] for p in c["parts"]]; g = sum(p["gain"] * x for p, x in zip(c["parts"], w)) / sum(w)
        avg = sum(w) / sum(x / p["fx_a"] for p, x in zip(c["parts"], w))      # 그때그때 바꿨다면 낸 평균 환율
        hit = g > 0; n += 1; k += hit; mid = (c["a"] + c["j"]) // 2; gains.append(g)
        marks.append({"t0": tt(c["a"]), "v0": round(float(fx.iloc[c["a"]])), "t1": tt(c["j"]), "v1": c["fx_j"], "kind": "defer", "ok": bool(hit),
                      "d0": fmt(idx[c["a"]])[:7], "d1": fmt(idx[c["j"]])[:7], "avg": round(float(avg)), "fxj": c["fx_j"], "g": round(g, 1), "done": True})
    inv = FXS.inverse(W); ik = in_ = 0; iworst = 0
    for e in inv["eps"]:
        if idx[e["a"]] < pd.Timestamp("1990-01-01"): continue
        if not e["done"]:
            marks.append({"t0": tt(e["a"]), "v0": round(float(fx.iloc[e["a"]])), "t1": tt(len(idx) - 1), "v1": round(float(fx.dropna().iloc[-1])), "kind": "inv", "ok": None, "d0": fmt(idx[e["a"]])[:7], "done": False}); continue
        in_ += 1; ik += e["r"] > 0; iworst = max(iworst, e["worst"])
        marks.append({"t0": tt(e["a"]), "v0": round(float(fx.iloc[e["a"]])), "t1": tt(e["j"]), "v1": round(float(fx.iloc[e["j"]])), "kind": "inv", "ok": e["r"] > 0,
                      "d0": fmt(idx[e["a"]])[:7], "d1": fmt(idx[e["j"]])[:7], "fxa": round(float(fx.iloc[e["a"]])), "fxj": round(float(fx.iloc[e["j"]])), "g": e["r"], "worst": e["worst"], "done": True})
    # 몰아서 환전(참고): 미국 주식 관망 중(신호+1년 유지) + 환율이 5년 평균 아래. 위기 때 원화가 약해지기 전에 싼 달러를 미리.
    R, _ = registry(); import evolve as EV
    usw = pd.Series(False, index=idx)
    for r in (R or []):
        if r["status"] == "확정" and r["asset"] in ("nasdaq", "spx") and r["kind"] in ("관망", "강한관망"):
            usw |= EV.signal(r, r["asset"], EV.FW).reindex(idx).fillna(False)
    usw = usw.astype(int).rolling(52, min_periods=1).max().astype(bool)
    dev = f["dev"]; bulk = (usw & (dev <= 0)).fillna(False) & valid
    cu, ck = W["cash_us"], W["cash_kr"]; bk = bn = 0
    def pull(t, N=52):
        if t + N >= len(idx) or np.isnan(fx.iloc[t + N]): return None
        ks = range(t, t + N + 1)
        return (sum((cu.iloc[k] / cu.iloc[t]) / fx.iloc[t] for k in ks) / sum((ck.iloc[k] / ck.iloc[t]) / fx.iloc[k] for k in ks) - 1) * 100
    bv = bulk.values; eps = []
    for i in np.where(bv)[0]:
        if eps and i - eps[-1][1] <= 13: eps[-1][1] = i
        else: eps.append([i, i])
    for a_, b_ in eps:
        if idx[a_] < pd.Timestamp("1990-01-01"): continue
        g_ = pull(a_); e_ = min(a_ + 52, len(idx) - 1)
        if g_ is None:
            marks.append({"t0": tt(a_), "v0": round(float(fx.iloc[a_])), "t1": tt(len(idx) - 1), "v1": round(float(fx.dropna().iloc[-1])), "kind": "bulk", "ok": None, "d0": fmt(idx[a_])[:7], "done": False}); continue
        bn += 1; bk += g_ > 0
        marks.append({"t0": tt(a_), "v0": round(float(fx.iloc[a_])), "t1": tt(e_), "v1": round(float(fx.iloc[e_])), "kind": "bulk", "ok": bool(g_ > 0),
                      "d0": fmt(idx[a_])[:7], "fxa": round(float(fx.iloc[a_])), "fxj": round(float(fx.iloc[e_])), "g": round(g_, 1), "done": True})
    on = f["on"] & valid; zone = f["zone"] & valid
    now = "관망" if bool(zone.iloc[-1]) else "보통"
    # 10-21 사용자: 검증 약한 신호는 버림 → 몰아서 환전(3번)·달러 인버스(위기 3번)는 화면에서 뺌(계산 코드는 남김)
    marks = [m for m in marks if m["kind"] in ("defer", "inv")]    # 10-21 사용자: 원화로 되돌리기 시점 → 보수적 인버스 규칙을 1배(달러→원화 환전)로 다시 씀(7번 중 7번)
    bulk_now = False
    p = [[tt(i), float(f"{y:.4g}")] for i, y in enumerate(fx.values) if keep.iloc[i] and not np.isnan(y)]
    # 주마다 환전 상태(예시 보기용): V 달러→원화 · D 원→달러 미루기 · N 평소
    vz = np.zeros(len(idx), bool)
    for e in inv["eps"]:
        vz[e["a"]:(e["j"] if e["done"] else len(idx))] = True
    fcode = "".join(("V" if vz[i] else "D" if bool(zone.iloc[i]) else "N") for i, y in enumerate(fx.values) if keep.iloc[i] and not np.isnan(y))
    line = W["usdkrw"].rolling(260).mean() * (1 + FXS.AVOID)
    ref = [[tt(i), round(float(y))] for i, y in enumerate(line.values) if keep.iloc[i] and not np.isnan(y)]
    avg5 = W["usdkrw"].rolling(260).mean()
    ref2 = [[tt(i), round(float(y))] for i, y in enumerate(avg5.values) if keep.iloc[i] and not np.isnan(y)]
    return {"id": "usdkrw", "name": "환전 (원 → 달러)", "prod": "원/달러", "unit": "원", "fxcard": True,
            "rule": "환율이 5년 평균보다 15% 넘게 높을 때", "fxrule2": "신호가 꺼지면 바꿈 (최대 9개월)", "fxok": "그때그때 바꾼 것보다 달러를 더 받으면 맞음",
            "now": now, "since": None, "until": None, "lastbuy": None, "stats": {}, "press": [], "buyrule": None,
            "gmax": round(float(max(gains)), 1) if gains else None, "bulk_on": bulk_now, "bk": bk, "bn": bn, "bulkrule": "미국 주식이 관망 중(나스닥 관망 또는 S&P 강한 관망, 뒤 1년 포함) + 환율이 5년 평균보다 낮을 때 · 앞으로 1년치 환전을 지금 몰아서", "fx": round(f["fx"]), "inv_on": inv["on"], "ink": ik, "inn": in_, "iworst": round(iworst), "invrule": f"5년 평균보다 {round(FXS.INV_DEV*100)}% 넘게 비싸고, 13주 고점에서 {round(FXS.INV_DROP*100)}% 꺾였을 때 · 5년 평균 +{round(FXS.INV_EXIT*100)}% 아래로 오면(최대 9개월) 정리", "fxdev": round(f["dev_now"] * 100, 1), "fxline": round(float(line.dropna().iloc[-1])), "evk": k, "evn": n, "gavg": round(float(np.mean(gains)), 1) if gains else None, "gmin": round(float(min(gains)), 1) if gains else None, "lb": round(float(__import__("evolve").wilson_lb(k, n)) * 100) if n else None,
            "ev": {}, "p": p, "fs": fcode, "ref": ref, "ref2": ref2, "marks": marks, "sell": ranges(on & keep, W.index), "strong": [], "hold": [], "buy": [], "bad": [],
            "sellTxt": "환전 미루기", "known": None, "asof": fmt(W.index[valid][-1])}


def evolog():
    f = os.path.join(B, "logs", "evolve_log.md"); g = os.path.join(B, "data", "evolve_state.json")
    lines = []
    if os.path.exists(f):
        cur = None
        for ln in open(f, encoding="utf-8"):
            if ln.startswith("## "): cur = ln[3:].strip()
            elif ln.startswith("- ") and cur: lines.append(f"{cur} · {ln[2:].strip()}")
    st = json.load(open(g, encoding="utf-8")) if os.path.exists(g) else {}
    return {"checked": st.get("checked"), "lines": lines[::-1][:12]}


def tb3():
    import csv
    r = list(csv.DictReader(open(os.path.join(B, "data", "daily", "f_DTB3.csv"))))
    return f"{float(r[-1]['value']):.1f}"


def _runs(s):
    s = s.fillna(False); res = []; st = prev = None
    for d, v in s.items():
        if v and st is None: st = d
        if not v and st is not None: res.append((st, prev)); st = None
        prev = d
    if st is not None: res.append((st, prev))
    return res


if __name__ == "__main__":
    main()
