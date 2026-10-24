# -*- coding: utf-8 -*-
"""스스로 점검하고 천천히 고치는 판단 루프 (2026-10-21, 사용자: '알아서 진화하되 과적합 말고 납득되는 선에서').

원칙(미리 못 박음 — 루프가 이걸 바꾸지 못함):
1. 재료 제한: 자산마다 '그 자산을 움직이는 이유'가 설명되는 지표만 씀(PIECES). 데이터를 뒤져 새 지표를 만들지 않음.
2. 모양 제한: '많이 오름(dev5) + 압력 1개' 또는 '많이 오름 + 압력 n개 중 k개'. 문턱은 0.7 / 0.8 두 가지뿐.
3. 채점은 '사건' 단위: 신호가 켜진 덩어리 하나 = 1번. 따라 했을 때(첫 신호~마지막 신호+52주 현금) 현금이 나았나.
   점수 = 맞은 사건 비율의 보수적 하한(윌슨 하한, z=1.28) → 사건이 적으면 자동으로 깎임.
4. 합격선: 사건 4번 이상 · 주 단위 적중 75%+ · 시대(~1999 / 2000~13 / 2014~)마다 크게 틀린 적 없음 ·
   따라 하면 수익이 줄지 않음 · 미국 주식은 비슷한 다른 시장에서도 통함.
5. 바꾸는 속도 제한: 새 규칙은 먼저 '후보'로만 보여주고(따르지 않음), 매달 점검에서 3번 연속 1등이고
   지금 규칙보다 하한이 0.05 이상 높을 때만 교체. 지금 규칙은 하한이 합격선보다 0.10 넘게 떨어지거나
   채택 뒤 실전에서 3번 이상 켜져 절반도 못 맞히면 '참고'로 내림.
6. 모든 변화는 logs/evolve_log.md 에 날짜·이유와 함께 남김.

py evolve.py          매주: 지금 규칙 재채점 + 실전 성적 + 강등 판단 (달이 바뀌었으면 후보 탐색까지)
py evolve.py search   후보 탐색 강제
산출: data/rules.json (규칙 목록·상태), data/evolve_state.json (점수·실전 성적), logs/evolve_log.md
"""
import os, sys, json, datetime, itertools
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(os.path.join(B, "data", "weekly.pkl")); W, T, Q = D["W"], D["T"], D["Q"]
TV = W.index.values
RULES_F = os.path.join(B, "data", "rules.json"); STATE_F = os.path.join(B, "data", "evolve_state.json")
LOG_F = os.path.join(B, "logs", "evolve_log.md")
TODAY = datetime.date.today().isoformat()

# 자산별로 쓸 수 있는 재료와 이유 (방향: ">=" 높을수록 나쁨, "<=" 낮을수록 나쁨)
US_P = [("d_y2_12", ">=", "2년물 급등(연준 긴축 예상)"), ("d_y10_12", ">=", "10년물 급등(할인율 상승)"),
        ("d_cpi12", ">=", "물가 가속"), ("oil12", ">=", "유가 급등(비용·물가 압력)"), ("d_ff12", ">=", "기준금리 인상"),
        ("d_spr6", ">=", "회사채 가산금리 확대(신용 악화)"), ("d_nfci6", ">=", "금융 여건 긴축"), ("claims", ">=", "실업수당 청구 증가")]
PIECES = {
    "nasdaq": US_P, "spx": US_P, "dji": US_P, "rut": US_P,
    "kospi": [("kr_exp_yoy", ">=", "한국 수출 증가율 정점"), ("dxy12", ">=", "달러 강세(외국인 이탈)"), ("d_y2_12", ">=", "미 2년물 급등"),
              ("oil12", ">=", "유가 급등(수입 비용)"), ("d_cpi12", ">=", "미 물가 가속")],
    "oil": [("dxy12", ">=", "달러 강세"), ("d_ip_yoy6", "<=", "미 산업생산 둔화"), ("d_y2_12", ">=", "미 2년물 급등")],
    "ust10": [("d_cpi12", ">=", "물가 가속"), ("d_ff12", ">=", "기준금리 인상"), ("oil12", ">=", "유가 급등"), ("d_y2_12", ">=", "2년물 급등")],
}
SIBLING = {"nasdaq": ["spx", "rut", "dji"], "spx": ["nasdaq", "rut", "dji"], "dji": ["spx", "nasdaq"], "rut": ["spx", "nasdaq"]}
CASH = {"kospi": "cash_kr"}
NODEV = {"ust10"}     # 채권은 '많이 오름' 조건 없이 압력만
ERAS = [("~1999", None, "1999-12-31"), ("2000~13", "2000-01-01", "2013-12-31"), ("2014~", "2014-01-01", None)]
Z = 1.28; ACCEPT = 0.55
NAME = {"nasdaq": "나스닥", "spx": "S&P500", "dji": "다우", "rut": "러셀2000", "kospi": "코스피", "oil": "원유", "ust10": "미국채 10년"}
KN = lambda sc: f"{sc['n']}번 중 {sc['k']}번 맞음"


def wilson_lb(k, n, z=Z):
    if n == 0: return 0.0
    p = k / n; d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


# ---------- 자료 틀: 주 단위 / 월 단위 (월이 더 길게 거슬러 감: 코스피 1981~, 원유 1960~) ----------
class Frame:
    def __init__(self, name, P, T, Q, dev, h, gap, ma, idx, colmap, cashmap):
        self.name, self.P, self.T, self.Q, self._dev, self.h, self.gap, self.ma = name, P, T, Q, dev, h, gap, ma
        self.idx, self.col, self.cash, self._dc = idx, colmap, cashmap, {}
    def px(self, a): return self.P[self.col(a)] if self.col(a) in self.P else None
    def c(self, a): return self.P[self.cash(a)]
    def dev(self, a):
        if a not in self._dc: self._dc[a] = self._dev(a)
        return self._dc[a]


FW = Frame("주", W, T, Q, lambda a: Q["dev5_" + a] if "dev5_" + a in Q else None, 52, 26, 43, TV.astype("datetime64[D]"),
           lambda a: a, lambda a: CASH.get(a, "cash_us"))
_FM = None
def FM():
    global _FM
    if _FM is None:
        from build_history import P as MP, T as MT, Q as MQ, dev5 as mdev
        from panel import ASSETS
        mi = np.array([np.datetime64(f"{p.year:04d}-{p.month:02d}") for p in MP.index]).astype("datetime64[D]")
        _FM = Frame("월", MP, MT, MQ, lambda a: mdev(a) if a in ASSETS else None, 12, 6, 10, mi,
                    lambda a: ASSETS[a][0] if a in ASSETS else a, lambda a: ASSETS[a][1] if a in ASSETS else "cash_us")
    return _FM


# ---------- 규칙 → 신호 ----------
def signal(r, asset=None, F=FW):
    a = asset or r["asset"]; px = F.px(a)
    if px is None: return None
    if r.get("form") == "trend":
        up = px > px.rolling(F.ma).mean(); dd = (px / px.rolling(F.h).max() - 1).rolling(F.h).min()
        return ((dd <= -0.2) & up & (px / px.cummax() - 1 <= -0.1)).fillna(False)
    if r.get("form") == "cheap":
        d = F.dev(a); return None if d is None else (d <= r["dev"]).fillna(False)
    cnt = sum(((F.Q[c] >= q) if op == ">=" else (F.Q[c] <= q)).fillna(False).astype(int) for c, op, q in r["conds"])
    s = cnt >= r.get("k", len(r["conds"]))
    if r.get("dev") is not None:
        d = F.dev(a)
        if d is None: return None
        s = s & (d >= r["dev"])
    return s.fillna(False)


def describe(r):
    if r.get("form") == "trend": return "고점에서 20% 넘게 빠진 뒤 다시 오르기 시작"
    if r.get("form") == "cheap": return f"5년 평균보다 많이 싸짐(하위 {round(r['dev']*100)}%)"
    names = {c: why for p in PIECES.values() for c, _, why in p}
    top = lambda op, q: f"상위 {round((1-q)*100)}%" if op == ">=" else f"하위 {round(q*100)}%"
    parts = [f"{names.get(c, c)}({top(op, q)})" for c, op, q in r["conds"]]
    s = " · ".join(parts) if r.get("k", len(parts)) == len(parts) else f"{' · '.join(parts)} 중 {r['k']}개 이상"
    return (f"많이 오른 상태(상위 {round((1-r['dev'])*100)}%) + " if r.get("dev") is not None else "") + s


# ---------- 채점 ----------
def episodes(sig, gap):
    idx = np.where(sig.values)[0]; eps = []
    for i in idx:
        if eps and i - eps[-1][1] <= gap: eps[-1][1] = i
        else: eps.append([i, i])
    return eps


def score1(r, a, since, F):
    """관망: 첫 신호~마지막 신호+1년을 현금으로 있었을 때 현금이 나았나. 매수: 첫 신호부터 1년 들고 있었을 때 자산이 나았나."""
    sig = signal(r, a, F)
    if sig is None: return None
    pxs = F.px(a); px = pxs.values; c = F.c(a).values; sig = sig & pxs.notna()
    if since: sig = sig & (F.idx >= np.datetime64(since))
    sell = r["kind"] != "매수"; n_last = len(px) - 1; eps = []
    for s, e in episodes(sig, F.gap):
        end = (e if sell else s) + F.h
        if end > n_last or np.isnan(px[end]) or np.isnan(px[s]) or np.isnan(c[end]) or np.isnan(c[s]):
            eps.append({"start": str(F.idx[s]), "end": str(F.idx[e]), "done": False}); continue
        ar, cr = px[end] / px[s], c[end] / c[s]
        eps.append({"start": str(F.idx[s]), "end": str(F.idx[e]), "done": True, "hit": bool(cr > ar if sell else ar > cr),
                    "asset": round((ar - 1) * 100, 1), "cash": round((cr - 1) * 100, 1)})
    done = [x for x in eps if x["done"]]; k = sum(x["hit"] for x in done); n = len(done)
    bad = F.T[a + "_bad"] if a + "_bad" in F.T else None
    if bad is not None:
        bad = bad.reindex(sig.index); m = sig & bad.notna()
        hit = float((bad[m] if sell else 1 - bad[m]).mean()) if m.sum() else float("nan")
    else: hit = float("nan")
    era = {}
    for en, lo, hi in ERAS:
        sel = [x for x in done if (lo is None or x["start"] >= lo) and (hi is None or x["start"] <= hi)]
        if sel: era[en] = [sum(x["hit"] for x in sel), len(sel)]
    return {"frame": F.name, "n": n, "k": k, "lb": round(float(wilson_lb(k, n)), 3), "hit": round(hit * 100, 1) if hit == hit else None,
            "era": era, "eps": eps, "on_share": round(float(sig[pxs.notna()].mean()) * 100, 1)}


def score(r, asset=None, since=None):
    """주·월 둘 다 채점하고, 끝난 사건이 더 많은(근거가 많은) 쪽을 대표로. 둘의 적중률을 함께 기록."""
    a = asset or r["asset"]
    w = score1(r, a, since, FW); m = score1(r, a, since, FM())
    if w is None and m is None: return None
    best = max([x for x in (w, m) if x], key=lambda x: (x["n"], x["frame"] == "주"))
    out = dict(best); out["wk"] = w["hit"] if w else None; out["mo"] = m["hit"] if m else None
    return out


def returns_effect(r):
    """관망 규칙만: 신호 뒤 1년 현금으로 있었을 때 연수익·최대하락 (주 단위, 1985~, 가격 기준)."""
    a = r["asset"]; px = W[a]; c = W[CASH.get(a, "cash_us")]
    sig = signal(r, a, FW)
    if sig is None: return None
    sig = sig & px.notna(); out = sig.astype(int).rolling(52, min_periods=1).max().astype(bool).shift(1, fill_value=False)
    ra = (px / px.shift(1) - 1); rc = (c / c.shift(1) - 1)
    m = (TV >= np.datetime64("1985-01-01")) & ra.notna().values & rc.notna().values
    res = {}
    for nm, x in (("hold", ra), ("rule", ra.where(~out, rc))):
        x = x[m].values; eq = np.cumprod(1 + x); y = len(x) / 52.18
        res[nm] = [round(float(eq[-1] ** (1 / y) - 1) * 100, 2), round(float((eq / np.maximum.accumulate(eq) - 1).min()) * 100, 1)]
    return res


def passes(r, sc, eff, sib):
    why = []
    if sc is None: return False, ["자료 없음"]
    if sc["n"] < 4: why.append(f"사건 {sc['n']}번(4번 미만)")
    h = [x for x in (sc.get("wk"), sc.get("mo")) if x is not None]
    if not h or min(h) < 70 or max(h) < 75: why.append(f"적중 주 {sc.get('wk')}% · 월 {sc.get('mo')}%")
    if sc["lb"] < ACCEPT: why.append(f"보수적 하한 {sc['lb']}")
    for en, (k, n) in sc["era"].items():
        if n >= 2 and k / n < 0.5: why.append(f"{en} {k}/{n}")
    if eff and (eff["rule"][0] < eff["hold"][0] - 0.3): why.append(f"수익 감소 {eff['rule'][0]} < {eff['hold'][0]}")
    if sib is not None and sib < 0.6: why.append(f"다른 시장 {round(sib*100)}%")
    return not why, why


def sibling_rate(r):
    sibs = SIBLING.get(r["asset"])
    if not sibs: return None
    k = n = 0
    for s in sibs:
        sc = score(r, s)
        if sc: k += sc["k"]; n += sc["n"]
    return k / n if n else None


# ---------- 처음 규칙(지금 신호판 그대로) ----------
def seed():
    P4 = [["d_y2_12", ">=", 0.7], ["d_y10_12", ">=", 0.8], ["d_cpi12", ">=", 0.7], ["oil12", ">=", 0.8]]
    R = [
        {"id": "nasdaq_sell_1", "asset": "nasdaq", "kind": "관망", "dev": 0.8, "conds": [["d_y2_12", ">=", 0.7]], "k": 1},
        {"id": "nasdaq_strong_1", "asset": "nasdaq", "kind": "강한관망", "dev": 0.8, "conds": P4, "k": 3},
        {"id": "spx_strong_1", "asset": "spx", "kind": "강한관망", "dev": 0.8, "conds": P4, "k": 3},
        {"id": "kospi_sell_1", "asset": "kospi", "kind": "관망", "dev": 0.7, "conds": [["kr_exp_yoy", ">=", 0.7]], "k": 1},
        {"id": "ust10_sell_1", "asset": "ust10", "kind": "관망", "dev": None, "conds": [["d_cpi12", ">=", 0.7], ["d_ff12", ">=", 0.7]], "k": 2},
        {"id": "oil_sell_1", "asset": "oil", "kind": "관망", "dev": 0.7, "conds": [["dxy12", ">=", 0.7]], "k": 1},
        {"id": "nasdaq_buy_1", "asset": "nasdaq", "kind": "매수", "form": "trend"},
        {"id": "spx_buy_1", "asset": "spx", "kind": "매수", "form": "trend"},
        {"id": "dji_buy_1", "asset": "dji", "kind": "매수", "form": "trend"},
        {"id": "kospi_buy_1", "asset": "kospi", "kind": "매수", "form": "cheap", "dev": 0.2},
    ]
    for r in R: r.update({"status": "확정", "since": "2026-10-21", "streak": 0})
    return R


def log(lines):
    if not lines: return
    new = not os.path.exists(LOG_F)
    with open(LOG_F, "a", encoding="utf-8") as f:
        if new: f.write("# 판단 루프 변경 기록\n")
        f.write(f"\n## {TODAY}\n" + "".join(f"- {x}\n" for x in lines))


# ---------- 후보 탐색 ----------
def candidates(a):
    P = PIECES[a]; out = []
    devs = [None] if a in NODEV else [0.7, 0.8]
    for dv in devs:
        for (c, op, _), q in itertools.product(P, (0.7, 0.8)):
            if a in NODEV: continue
            out.append({"asset": a, "kind": "관망", "dev": dv, "conds": [[c, op, q if op == ">=" else round(1 - q, 1)]], "k": 1})
        for (c1, o1, _), (c2, o2, _) in itertools.combinations(P, 2):
            out.append({"asset": a, "kind": "관망", "dev": dv, "conds": [[c1, o1, 0.7 if o1 == ">=" else 0.3], [c2, o2, 0.7 if o2 == ">=" else 0.3]], "k": 2})
        if len(P) >= 4:
            for kk in (3,):
                sub = P[:4]
                out.append({"asset": a, "kind": "관망", "dev": dv, "conds": [[c, o, 0.7 if o == ">=" else 0.3] for c, o, _ in sub], "k": kk})
    return out


def key(r):
    return json.dumps([r["asset"], r["kind"], r.get("dev"), r.get("form"), r.get("conds"), r.get("k")], ensure_ascii=False)


def search(R, state, logs):
    tried = 0
    for a in PIECES:
        if a not in W: continue
        inc = [r for r in R if r["asset"] == a and r["kind"] == "관망" and r["status"] == "확정"]
        inc_sc = [state["scores"][r["id"]] for r in inc if r["id"] in state["scores"]]
        inc_lb = max([x["lb"] for x in inc_sc] or [0]); inc_txt = KN(max(inc_sc, key=lambda x: x["lb"])) if inc_sc else ""
        best = None
        for cnd in candidates(a):
            tried += 1
            sc = score(cnd)
            if not sc or sc["n"] < 4 or sc["lb"] < ACCEPT: continue
            if best is None or sc["lb"] > best[1]["lb"] or (sc["lb"] == best[1]["lb"] and len(cnd["conds"]) < len(best[0]["conds"])):
                best = (cnd, sc)
        if not best: continue
        cnd, sc = best
        ok, why = passes(cnd, sc, returns_effect(cnd), sibling_rate(cnd))
        if not ok or sc["lb"] < inc_lb + 0.05: continue
        old = [r for r in R if r["status"] == "후보" and r["asset"] == a and r["kind"] == "관망"]
        same = [r for r in old if key(r) == key(cnd)]
        if same:
            same[0]["streak"] += 1
            if same[0]["streak"] >= 3:
                for r in inc: r["status"] = "은퇴"; logs.append(f"{NAME.get(a, a)}: '{describe(r)}' 은퇴 (더 나은 규칙으로 교체)")
                same[0]["status"] = "확정"; same[0]["since"] = TODAY
                logs.append(f"{NAME.get(a, a)}: 후보 '{describe(same[0])}' 확정 (3달 연속 1등, {KN(sc)})")
        else:
            for r in old: r["status"] = "은퇴"
            cnd.update({"id": f"{a}_cand_{TODAY}", "status": "후보", "since": TODAY, "streak": 1})
            R.append(cnd); logs.append(f"{NAME.get(a, a)}: 새 후보 '{describe(cnd)}' — 과거 {KN(sc)}" + (f" (지금 규칙 {inc_txt})" if inc_txt else "") + ". 아직 안 따름, 3달 연속 1등이면 교체")
    state["last_search"] = TODAY[:7]; state["tried_total"] = state.get("tried_total", 0) + tried
    return tried


def main(force_search=False):
    R = json.load(open(RULES_F, encoding="utf-8")) if os.path.exists(RULES_F) else seed()
    state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {}
    first = not state; state.setdefault("scores", {}); logs = []
    if first: logs.append("루프 시작: 지금 신호판 규칙 10개를 '확정'으로 등록")
    for r in R:
        if r["status"] == "은퇴": continue
        sc = score(r); live = score(r, since=r["since"])
        eff = returns_effect(r) if r["kind"] != "매수" else None
        sib = sibling_rate(r) if r["kind"] != "매수" else None
        ok, why = passes(r, sc, eff, sib) if r["kind"] != "매수" else (sc["lb"] >= ACCEPT, [] if sc["lb"] >= ACCEPT else [f"보수적 하한 {sc['lb']}"])
        state["scores"][r["id"]] = {"desc": describe(r), "asset": r["asset"], "kind": r["kind"], "status": r["status"], "since": r["since"],
                                    "n": sc["n"], "k": sc["k"], "lb": sc["lb"], "wk": sc["wk"], "mo": sc["mo"], "frame": sc["frame"], "era": sc["era"], "on_share": sc["on_share"],
                                    "eff": eff, "sib": None if sib is None else round(sib * 100), "ok": ok, "why": why,
                                    "live": {"n": live["n"], "k": live["k"], "open": sum(not x["done"] for x in live["eps"])},
                                    "eps": sc["eps"][-8:]}
        if r["status"] == "확정":
            if sc["lb"] < ACCEPT - 0.10:
                r["status"] = "참고"; logs.append(f"{NAME.get(r['asset'], r['asset'])} {r['kind']}: '{describe(r)}' 참고로 내림 — 과거 {KN(sc)}, " + ("자주 틀림" if sc["n"] >= 8 else "근거가 적음") + f"")
            elif live["n"] >= 3 and live["k"] / live["n"] < 0.5:
                r["status"] = "참고"; logs.append(f"{NAME.get(r['asset'], r['asset'])} {r['kind']}: '{describe(r)}' 참고로 내림 — 채택 뒤 실전 {live['n']}번 중 {live['k']}번")
            elif not ok and not first:
                state["scores"][r["id"]]["warn"] = True
    tried = None
    if force_search or state.get("last_search") != TODAY[:7]:
        tried = search(R, state, logs)
    state["checked"] = TODAY
    json.dump(R, open(RULES_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    log(logs)
    for r in R:
        s = state["scores"].get(r["id"])
        if s: print(f"{r['status']:3s} {r['asset']:7s} {r['kind']:4s} {s['k']}/{s['n']} lb {s["lb"]} {s["frame"]} wk {s["wk"]} mo {s["mo"]} sib {s['sib']} ok {s['ok']} {' / '.join(s['why'])} | {s['desc']}")
    print("search tried", tried, "| log:", logs)


if __name__ == "__main__":
    main(force_search="search" in sys.argv[1:])
