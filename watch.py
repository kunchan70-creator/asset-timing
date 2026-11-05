# -*- coding: utf-8 -*-
"""장중 감시 + 폰 알림 (2026-11-02, 사용자: '폭락은 짧게 끝나니 장중에도 확인 · 폰 알람, 상황 바뀌면 알람 안 바뀌면 그대로 ·
알람은 내가 끄지 않는 한 폰 위에 떠 있게, 주요한 요소들은 남아있도록').

- 폰 알림은 ntfy(앱 설치 → 주제 구독) 한 개만 씀: 늘 같은 번호(sequence id)로 보내서 새로 쌓이지 않고 '상황판' 알림 하나가 그 자리에서 바뀜.
- 보내는 때 = 상황판 핵심 줄(할 일·저점매수·VIX 40↑·하락장 경보·환율 국면)이 바뀔 때만. 숫자(RSI·VIX)는 바뀔 때의 값을 같이 적음.
- 저점매수는 판과 같은 규칙: RSI(14, 와일더) 30↓ + (VIX 30↑ 또는 공포탐욕 30↓, 코스피는 VIX만) · VIX 40↑ 은 경고 중에도 삼 ·
  경고/경기 꺾임 중이면 '무시'. 장중 RSI = 지금 가격을 오늘 종가로 친 추정. 10분 두 번 연속 같아야 바뀐 것으로 봄(문턱 근처 깜빡임 방지).
- 판 쪽 할 일(경고·관망 등)은 data/watch_state.json 에서 읽음. 화~토 아침 7시에 이 프로그램이 update_all.py 를 돌려 갱신(판 게시는 따로).
- 장 시간: 미국 9:30~16:00(뉴욕), 한국 9:00~15:30. 장 밖에서는 판 상태 파일만 10분마다 확인.

py watch.py          계속 돌기 (Ctrl+C 로 끝)
py watch.py once     한 번만 계산해 보여 주기(보내지 않음)
py watch.py test     지금 상황판을 폰으로 한 번 보내 보기
실행: watch_start.vbs 가 창 없이 띄움(윈도우 시작프로그램에 등록, 앱·터미널과 무관). 이미 떠 있으면 새로 뜬 쪽이 바로 끝남.
죽음 알림: 1시간마다 ntfy 에 '6시간 뒤 울릴 예약 알림'을 같은 번호로 다시 걸어 둠 → 감시가 죽거나 PC 가 꺼지면 6시간 뒤 폰이 울림.
설정: watch_config.json {"topic": "...", "server": "https://ntfy.sh", "poll_min": 5}
"""
import os, sys, json, time, datetime, subprocess
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd
import livewarn
B = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(B, "watch_config.json"); LAST = os.path.join(B, "logs", "watch_last.json"); LOG = os.path.join(B, "logs", "watch.log")
SYM = {"nasdaq": "^IXIC", "spx": "^GSPC", "dji": "^DJI", "kospi": "^KS11"}
NAME = {"nasdaq": "나스닥", "spx": "S&P500", "dji": "다우", "kospi": "코스피"}
NOW_TXT = {"관망유지": "새로 안 사기", "매수": "사기", "보통": "들고 가기"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
NY, SEOUL = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f: f.write(f"{datetime.datetime.now():%m-%d %H:%M} {msg}\n")


def get(url, ref=None):
    cmd = ["curl", "-s", "-m", "20", "-A", UA] + (["-H", f"Referer: {ref}"] if ref else []) + [url]
    try: return subprocess.run(cmd, capture_output=True, timeout=30).stdout.decode("utf-8", "replace")
    except Exception: return ""


META = {}


def limit_level(aid, when):
    """오늘 종가가 이 값이면 RSI 30 (어제까지 자료만). 반환 (값, 어제 종가)"""
    h = hist(aid); day = pd.Timestamp(when.astimezone(SEOUL if aid == "kospi" else NY).date().isoformat()); c = h[h.index < day].values
    U = D = 0.0
    for i in range(1, len(c)):
        x = c[i] - c[i - 1]; U = U * 13 / 14 + max(x, 0) / 14; D = D * 13 / 14 + max(-x, 0) / 14
    return float(c[-1] - 13 * (7 * U / 3 - D)), float(c[-1])


def etf_prices(buy, goal):
    """나스닥 값을 QQQ·QLD 값으로: 어제 종가 대비 움직임 × 베타(최근 60일 QQQ/나스닥), QLD 는 2배"""
    try:
        q = pd.read_csv(os.path.join(B, "data", "daily", "y_qqq.csv")).set_index("date")["value"].astype(float); n = pd.read_csv(os.path.join(B, "data", "daily", "y_nasdaq.csv")).set_index("date")["value"].astype(float)
        d = pd.concat([q, n], axis=1, keys=["q", "n"]).dropna().iloc[-61:].pct_change().dropna(); beta = float((d.q * d.n).sum() / (d.n * d.n).sum())
        live("QQQ"); live("QLD"); pq, pl = float(META["QQQ"]["chartPreviousClose"]), float(META["QLD"]["chartPreviousClose"]); pn = float(META["^IXIC"]["chartPreviousClose"])
        ri = float(META["^IXIC"]["regularMarketPrice"]) / pn - 1; rq = float(META["QQQ"]["regularMarketPrice"]) / pq - 1
        if abs(ri) >= .01 and 0.7 < rq / ri < 1.6: beta = rq / ri       # 오늘 실제로 움직인 비율(큰 날은 이게 더 정확)
        r = buy / pn - 1; qb = pq * (1 + beta * r); g = goal / buy - 1; qg = qb * (1 + beta * g)
        return {"qqq": qb, "qld": pl * (qb / pq * 2 - 1), "qqq_goal": qg, "qld_goal": pl * (qg / pq * 2 - 1)}
    except Exception as e:
        log(f"etf err {e!r}"); return None


def live(sym):
    """야후 지금 값 (가격, 그 값의 시각)"""
    try:
        m = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=5m"))["chart"]["result"][0]["meta"]; META[sym] = m
        return float(m["regularMarketPrice"]), datetime.datetime.fromtimestamp(m["regularMarketTime"], datetime.timezone.utc)
    except Exception:
        return None, None


def fg_now():
    try: return float(json.loads(get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", "https://edition.cnn.com/"))["fear_and_greed"]["score"])
    except Exception: return None


def hist(aid):
    x = pd.read_csv(os.path.join(B, "data", "daily", f"y_{aid}.csv")); x.index = pd.to_datetime(x["date"]); return x["value"].astype(float).dropna().iloc[-800:]


def rsi_with(aid, price, when):
    """지금 가격을 오늘(그 시장 날짜) 종가로 친 RSI(14, 와일더)"""
    h = hist(aid)
    if price is not None:
        day = pd.Timestamp(when.astimezone(SEOUL if aid == "kospi" else NY).date())
        h = h[h.index < day]; h.loc[day] = price
    sd = h.diff(); up = sd.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); dn = (-sd.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    return float((100 - 100 / (1 + up / dn)).iloc[-1])


def market_open(aid, t=None):
    t = t or datetime.datetime.now(datetime.timezone.utc)
    z = t.astimezone(SEOUL if aid == "kospi" else NY)
    if z.weekday() >= 5: return False
    a, b = ((9, 0), (15, 30)) if aid == "kospi" else ((9, 30), (16, 0))
    return (z.hour, z.minute) >= a and (z.hour, z.minute) <= (b[0], b[1] + 5)


def compute():
    ws = json.load(open(os.path.join(B, "data", "watch_state.json"), encoding="utf-8"))
    vix, vt = live("^VIX"); fg = fg_now()
    if vix is None:      # 야후 실패 시 마지막 일봉
        v = pd.read_csv(os.path.join(B, "data", "daily", "f_VIXCLS.csv")); vix = float(v["value"].dropna().iloc[-1])
    rows = {}
    quotes = {aid: live(sym) for aid, sym in SYM.items() if ws["assets"].get(aid)}
    # 11-06 사용자 '경고도 실시간으로': 지금 시세로 경고 다시 계산(실패하면 판 값 그대로)
    try: lw = livewarn.evaluate({k: v[0] for k, v in quotes.items()})
    except Exception as e: lw = None; log(f"livewarn err {e!r}")
    for aid in quotes:
        a = ws["assets"][aid]; p, t = quotes[aid]; r = rsi_with(aid, p, t or datetime.datetime.now(datetime.timezone.utc))
        now, blocked = a["now"], a["blocked"]
        if lw:
            warn = lw["kospi_warn"] if aid == "kospi" else lw["us_warn"]; blocked = warn or lw["turn"]
            if warn: now = "강한관망" if aid in ("nasdaq", "spx") and lw["us_strong"] else "관망"
            elif lw["turn"]: now = "관망유지"
            elif a["now"] in ("관망", "강한관망", "관망유지"): now = "보통"
        cond = r < 30 and (vix >= 30 or (not a["nofg"] and fg is not None and fg <= 30))
        reg = bool(lw["reg"].get(aid, blocked)) if lw else bool(blocked)
        on = vix >= 40 or cond
        mode = "bounce" if reg else "all" if vix >= 40 else "hold"
        dip = "아님" if not on else ("사기(VIX 40↑)" if vix >= 40 else "사기")
        h = hist(aid); hi = float(max(h.iloc[-59:].max(), p or 0)); pv = float(p if p else h.iloc[-1])
        L, _ = limit_level(aid, t or datetime.datetime.now(datetime.timezone.utc)); m = META.get(SYM[aid], {}); low = float(m.get("regularMarketDayLow") or pv)
        fear = vix >= 30 or (not a["nofg"] and fg is not None and fg <= 30)
        touch = fear and low <= L
        rows[aid] = {"now": now, "dip": dip if on else ("걸림" if touch else "아님"), "rsi": round(r), "live": market_open(aid), "est": now != a["now"], "cond": on or touch, "bear3": aid == "nasdaq" and a.get("bear") == 3, "state": lw["state"].get(aid) if lw else None, "mode": mode, "reg": reg, "p": pv, "hi": hi, "L": L, "low": low, "fear": fear, "ent": min(L, pv) if touch and not vix >= 40 else pv}
    bear = max([a.get("bear") or 0 for a in ws["assets"].values()])
    fx = ws.get("fx", {})
    return {"rows": rows, "vix": round(vix, 1), "fg": None if fg is None else round(fg), "bear": bear, "regime": fx.get("regime"), "gap": fx.get("gap"), "asof": ws["asof"], "q": lw["q"] if lw else None, "detail": lw["detail"] if lw else None}


def key_of(c):
    """바뀌었는지 보는 핵심(숫자 빼고 상태만)"""
    return json.dumps({"r": {k: [v["now"], v["dip"]] for k, v in c["rows"].items()}, "v40": c["vix"] >= 40, "bear": c["bear"], "rg": c["regime"], "o": c.get("open_n")}, ensure_ascii=False)


SHORT = {"nasdaq": "나스닥", "spx": "S&P", "dji": "다우", "kospi": "코스피"}
BOARD = "https://kunchan70-creator.github.io/asset-timing/"


SECOND = .07; TAKE = .20; BUY = .50; DAYS = 87      # 빠진 폭의 20% 되돌림에 팖 · 현금의 50% · 60거래일(약 87일). _playbook.py·_retrace.py


def todo_of(aid, v):
    """(점, 할 일) — 🔴 파세요 · 🟠 조심 · 🟢 사세요 · ⚪ 평소"""
    now = v["now"] if isinstance(v, dict) else v
    if isinstance(v, dict) and v.get("bear3"): return "🔴", "큰 하락장이에요. 파세요 (10개월 평균선 위로 올라오면 다시 사요)"
    if now in ("관망", "강한관망"):
        if aid == "dji": return "🟠", "새로 사지 마세요"
        return "🔴", "위험해요. 파세요 (돈은 국고채에)" if aid == "kospi" else "위험해요. 파세요 (돈은 BOXX에)"
    if isinstance(v, dict) and v.get("reg"): return "🟠", "조심할 때예요. 많이 떨어질 때만 사세요"
    if now == "관망유지": return "🟠", "새로 사지 마세요"
    if now == "매수": return "🟢", "사세요"
    return "⚪", "평소예요. 그냥 들고 가세요"


def hold_txt(aid, v):
    """이미 들고 있는 것: 🔴(다우 빼고)면 팔기, 나머지는 그대로"""
    return "파세요" if todo_of(aid, v)[0] == "🔴" else "그대로 두세요"


def plan_txt(aid, v):
    if v["mode"] == "bounce":
        e = v.get("ent") or v["p"]; goal = e + TAKE * (v["hi"] - e)
        return f"돈의 절반으로 {e:,.0f}에 사고, {goal:,.0f}({(goal/e-1)*100:+.1f}%)에 전부 파세요"
    return "남은 돈 전부 사서 들고 가세요" if v["mode"] == "all" else "돈의 절반으로 사서 들고 가세요"


def text_of(c, changed=""):
    """11-06 사용자 '쉽게': 자산마다 한 줄, 어려운 말 빼고"""
    L = list(c.get("notes") or [])
    if L: L.append("━━━━━━━━━━")
    for aid, v in c["rows"].items():
        dot, todo = todo_of(aid, v)
        if v["dip"] == "걸림":
            g = v["L"] + TAKE * (v["hi"] - v["L"]); dot, todo = "📝", f"오늘 {v['L']:,.0f} 아래까지 갔다가 올라왔어요. 샀다면 {g:,.0f}({(g/v['L']-1)*100:+.1f}%)에 파세요"
        elif v["dip"] != "아님": dot, todo = "🟢", plan_txt(aid, v)
        L.append(f"{dot} {SHORT[aid]}: {todo}" + ("" if dot == "🔴" else f" · 가진 건 {hold_txt(aid, v)}") + (" (금요일에 확정돼요)" if v.get("est") else ""))
    if c.get("open_lines"): L.append("📌 샀다면: " + " / ".join(c["open_lines"]))
    if c.get("next_lines"): L.append("📉 더 떨어지면: " + " / ".join(c["next_lines"]))
    L.extend(limit_lines(c))
    L.append("━━━━━━━━━━")
    L.append("공포 지수 VIX " + f"{c['vix']:.0f}{' 🚨 지금이 살 때(40 넘음)' if c['vix'] >= 40 else ''} · 공포탐욕 {c['fg'] if c['fg'] is not None else '-'} (낮을수록 공포)")
    L.append(f"큰 하락장 신호 3개 중 {c['bear']}개" + (" ⚠️ 나스닥은 파세요" if c["bear"] >= 3 else ""))
    L.append(f"환율: {'달러가 유리한 때' if c['regime'] == 'hi' else '중간' if c['regime'] == 'mid' else '원화가 유리한 때'}")
    if changed: L.append(f"🔄 {changed}")
    L.append(f"🕐 {datetime.datetime.now():%m/%d %H:%M}")
    return "\n".join(L)


STATE_TXT = {"평시": "평소", "경고 꺼진 6개월": "위험 신호가 막 꺼진 뒤", "경고 중": "위험 신호 중", "하락 추세": "하락 중"}


def past_txt(aid, v, etf=False):
    """지금과 같은 때 과거에 샀다면"""
    try:
        x = json.load(open(os.path.join(B, "data", "oneline.json"), encoding="utf-8"))[aid][v["state"]]
        t = f"과거 '{STATE_TXT[v['state']]}'에 이 방법으로 샀다면 ({x['n']}번): {x['win']}%는 이득. 산 뒤 대부분 {x['dd90']}% 안쪽까지만 더 빠졌고, 가장 심할 땐 {x['worst']}%"
        return t + f" (QLD는 대부분 {x['dd90_2']}% 안쪽, 가장 심할 땐 {x['worst2']}%)" if etf else t
    except Exception: return ""


def limit_lines(c):
    """📝 주문 가격: 지금 값에서 5% 안인 것만"""
    o = []
    for aid, v in c["rows"].items():
        if v["L"] <= 0 or v["p"] / v["L"] - 1 > .05 or v["p"] < v["L"]: continue
        goal = v["L"] + TAKE * (v["hi"] - v["L"]); tail = "" if v["fear"] else " (지금은 시장 공포가 약해서 주문하지 마세요)"
        if aid == "nasdaq":
            e = etf_prices(v["L"], goal)
            if e: o.append(f"📝 오늘의 주문: QQQ {e['qqq']:.1f}에 사기 → {e['qqq_goal']:.1f}에 팔기 / QLD {e['qld']:.1f}에 사기 → {e['qld_goal']:.1f}에 팔기 (나스닥 {v['L']:,.0f}까지 떨어질 때){tail}"); o.append("    └ " + past_txt(aid, v, True)); continue
        o.append(f"📝 오늘의 주문: {SHORT[aid]} {v['L']:,.0f}에 사기 → {goal:,.0f}에 팔기{tail}"); o.append("    └ " + past_txt(aid, v))
    return o


def write_live(c):
    """판(wk_board)이 읽는 지금 상태"""
    rows = {}; ll = limit_lines(c)
    for aid, v in c["rows"].items():
        dot, todo = todo_of(aid, v); act = {"🔴": "파세요", "🟠": "새로 사지 마세요" if "새로 사지" in todo else "조심", "⚪": "평소", "🟢": "사세요"}.get(dot, todo); why = todo
        if v["dip"] == "걸림": dot = "📝"; act = "갔다 옴"; why = todo = f"오늘 {v['L']:,.0f} 아래까지 갔다가 올라왔어요. 샀다면 {v['L'] + TAKE * (v['hi'] - v['L']):,.0f}에 파세요"
        elif v["dip"] != "아님": dot = "🟢"; act = "사세요"; why = todo = plan_txt(aid, v)
        rows[aid] = {"dot": dot, "act": act, "todo": todo, "hold": hold_txt(aid, v), "why": why if dot == "🔴" else f"가진 건 {hold_txt(aid, v)} · {why}", "line": next((x for x in ll if aid != "nasdaq" and SHORT[aid] in x or aid == "nasdaq" and "QQQ" in x), ""), "past": past_txt(aid, v)}
    j = {"at": datetime.datetime.now().strftime("%m/%d %H:%M"), "title": title_of(c), "rows": rows, "detail": c.get("detail"), "limits": ll, "open": (c.get("open_lines") or []) + (c.get("next_lines") or [])}
    json.dump(j, open(os.path.join(B, "data", "watch_live.json"), "w", encoding="utf-8"), ensure_ascii=False)


def title_of(c):
    if c.get("notes"): return c["notes"][0]
    buy = [SHORT[k] for k, v in c["rows"].items() if v["dip"].startswith("사기")]
    if buy: return "🟢 사세요: " + "·".join(buy)
    sell = [SHORT[k] for k, v in c["rows"].items() if todo_of(k, v)[0] == "🔴"]
    care = [SHORT[k] for k, v in c["rows"].items() if todo_of(k, v)[0] == "🟠"]
    p = []
    if sell: p.append("🔴 파세요: " + "·".join(sell))
    if care: p.append("🟠 조심: " + "·".join(care))
    return " / ".join(p) or "⚪ 평소예요"


def apply_arrows(c, last):
    """화살표(10일 쉬거나 5% 더 빠지면 새로)마다 살 비율·매도가·기한을 만들고, 닿으면 '전부 파세요'. 반환: 이번에 울릴 문구"""
    A = last.setdefault("arrows", {}); notes = []; lines = []; nexts = []
    for aid, v in c["rows"].items():
        st = A.setdefault(aid, {"on": None, "lp": None, "n": 0, "open": [], "pend": False})
        today = datetime.datetime.now(SEOUL if aid == "kospi" else NY).date(); ts = today.isoformat()
        if st.get("reg") and not v["reg"]:       # 조심 구간 끝: 반등 매매 끝, 이제 보유
            notes.append(f"🟢 {SHORT[aid]} 이제 괜찮아졌어요. 남은 돈 전부 사고, 이제 팔지 마세요" + (" (걸어둔 팔기 주문은 취소)" if st["open"] else "")); st["open"] = []
        st["reg"] = v["reg"]
        for pos in st["open"][:]:
            if v["p"] >= pos["goal"]:
                notes.append(f"💰 {SHORT[aid]} {pos['goal']:,.0f} 도착! {pos['n']}차로 산 것 전부 파세요"); st["open"].remove(pos)
            elif ts > pos["until"]:
                notes.append(f"⏰ {SHORT[aid]} {pos['n']}차 기한 끝! 손해여도 오늘 전부 파세요 (지금 {v['p']:,.0f})"); st["open"].remove(pos)
        seen = st.get("seen") == ts; pl = st.get("low")     # 켜기 전에 이미 지나간 터치는 체결로 안 봄: 지켜보던 중 새로 찍었거나 지금 그 값 근처일 때만
        st["seen"] = ts; st["low"] = v["low"]
        fresh = (seen and pl is not None and pl > v["L"] >= v["low"]) or v["p"] <= v["L"] * 1.005 or v["dip"].startswith("사기")
        def add(e):
            st["n"] += 1; st["lp"] = e; vv = dict(v); vv["ent"] = e; msg = f"🟢 {SHORT[aid]} {st['n']}차: {plan_txt(aid, vv)}"
            if v["mode"] == "bounce":
                goal = e + TAKE * (v["hi"] - e); pos_ = {"n": st["n"], "buy": e, "goal": goal, "until": (today + datetime.timedelta(days=DAYS)).isoformat()}; st["open"].append(pos_)
                msg += f" ({(today + datetime.timedelta(days=DAYS)).strftime('%m/%d')}까지 안 오면 그날 파세요)"
                if aid == "nasdaq":
                    x = etf_prices(e, goal)
                    if x: msg += f" · QQQ {x['qqq']:.1f}에 사서 {x['qqq_goal']:.1f}에 팔기 · QLD {x['qld']:.1f}에 사서 {x['qld_goal']:.1f}에 팔기"; pos_["goal_q"] = x["qqq_goal"]
            notes.append(msg)
        if st["open"]:           # 들고 있으면: 지난 매수값보다 7% 더 빠지면 다음 차수 (_second.py)
            e2 = st["lp"] * (1 - SECOND)
            if v["live"] and v["low"] <= e2 and ((seen and pl is not None and pl > e2) or v["p"] <= e2 * 1.005): add(min(e2, v["p"]))
            e2 = st["lp"] * (1 - SECOND)
            if st["open"]:
                t2 = f"{SHORT[aid]} {e2:,.0f}"
                if aid == "nasdaq":
                    x = etf_prices(e2, e2 + TAKE * (v["hi"] - e2))
                    if x: t2 += f"(QQQ {x['qqq']:.1f}·QLD {x['qld']:.1f})"
                nexts.append(t2 + "에서 남은 돈의 절반으로 또 사세요")
        elif v["cond"] and v["live"] and fresh:
            gap = 99 if not st["on"] else (today - datetime.date.fromisoformat(st["on"])).days
            if gap > 14: add(v.get("ent") or v["p"])
            st["on"] = ts
        else: st["pend"] = False
        for pos in st["open"]:
            t_ = f"{SHORT[aid]} {pos['n']}차 {pos['goal']:,.0f}"
            if pos.get("goal_q"):        # QLD 매도가는 그날 실제 어제 종가에서 다시 계산
                try:
                    live("QQQ"); live("QLD"); pq, pl = float(META["QQQ"]["chartPreviousClose"]), float(META["QLD"]["chartPreviousClose"])
                    t_ += f"(QQQ {pos['goal_q']:.1f}·QLD {pl * (pos['goal_q'] / pq * 2 - 1):.1f})"
                except Exception: pass
            lines.append(t_ + f"에 전부 파세요 ({pos['until'][5:].replace('-', '/')}까지 안 오면 그날 파세요)")
    c["open_lines"] = lines; c["next_lines"] = nexts; c["open_n"] = {k: [A[k]["n"], len(A[k]["open"])] for k in A}
    return notes


def send(c, changed):
    cfg = json.load(open(CFG, encoding="utf-8"))
    body = {"topic": cfg["topic"], "title": title_of(c), "message": text_of(c, changed), "click": BOARD,
            "actions": [{"action": "view", "label": "판 열기", "url": BOARD}],
            "priority": 5}
    # 11-02 실측: 같은 번호로 덮어쓰면 폰에서 소리·팝업 없이 조용히 바뀜 → 바뀔 때마다 새 번호로 보내 울리고, 이전 상황판 알림은 지움(위에는 늘 하나)
    seq = "board-" + datetime.datetime.now().strftime("%m%d%H%M%S"); body["sequence_id"] = seq
    srv = cfg.get("server", "https://ntfy.sh")
    r = subprocess.run(["curl", "-s", "-m", "20", "-H", "Content-Type: application/json", "--data-binary", "@-", srv],
                       input=json.dumps(body, ensure_ascii=False).encode("utf-8"), capture_output=True, timeout=30)
    ok = b'"id"' in r.stdout; log(f"send {'ok' if ok else 'FAIL'} {title_of(c)}")
    if ok:
        prev = json.load(open(LAST, encoding="utf-8")).get("seq", "board") if os.path.exists(LAST) else "board"
        subprocess.run(["curl", "-s", "-m", "20", "-X", "DELETE", f"{srv}/{cfg['topic']}/{prev}"], capture_output=True, timeout=30)
        SEQ[0] = seq
    return ok


SEQ = [None]


NOW_TXT = {"관망": "위험", "강한관망": "위험", "관망유지": "새로 사지 않기", "매수": "사기", "보통": "평소"}


def diff(old, new):
    if not old: return "감시 시작"
    o, n = json.loads(old), json.loads(new); out = []
    for k, v in n["r"].items():
        if o["r"].get(k) != v: out.append(f"{SHORT[k]} {NOW_TXT.get(o['r'].get(k, ['-', '-'])[0], '-')} → {NOW_TXT.get(v[0], v[0])}" + ("" if v[1] == "아님" else " (주문 가격까지 갔다 옴)" if v[1] == "걸림" else " (지금 살 가격)"))
    if o["v40"] != n["v40"]: out.append("VIX 40 " + ("넘음" if n["v40"] else "아래로"))
    if o["bear"] != n["bear"]: out.append(f"큰 하락장 신호 {o['bear']}개 → {n['bear']}개 (3개면 나스닥 팔기)")
    if o["rg"] != n["rg"]: out.append("환율 흐름 바뀜")
    if not out and o.get("o") != n.get("o"): out.append("사고팔 가격 바뀜")
    return " · ".join(out)


def alive():
    """죽음 알림 다시 걸기(같은 번호면 예약이 바뀜)"""
    cfg = json.load(open(CFG, encoding="utf-8"))
    body = {"topic": cfg["topic"], "title": "⚠️ 자산 감시 멈춤", "message": "6시간 넘게 감시가 돌지 않아요. PC가 꺼졌거나 프로그램이 죽었어요.", "priority": 5, "delay": "6h", "sequence_id": "alive"}
    r = subprocess.run(["curl", "-s", "-m", "20", "-H", "Content-Type: application/json", "--data-binary", "@-", cfg.get("server", "https://ntfy.sh")],
                       input=json.dumps(body, ensure_ascii=False).encode("utf-8"), capture_output=True, timeout=30)
    return b'"id"' in r.stdout


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "once":
        import copy
        c = compute(); apply_arrows(c, copy.deepcopy(json.load(open(LAST, encoding="utf-8")) if os.path.exists(LAST) else {})); open(os.path.join(B, "logs", "watch_once.txt"), "w", encoding="utf-8").write(title_of(c) + "\n" + text_of(c)); write_live(c); print("written"); return
    if mode == "test":
        import copy
        c = compute(); apply_arrows(c, copy.deepcopy(json.load(open(LAST, encoding="utf-8")) if os.path.exists(LAST) else {})); ok = send(c, "시험 알림")
        if ok:
            last = json.load(open(LAST, encoding="utf-8")) if os.path.exists(LAST) else {}
            last["seq"] = SEQ[0]; json.dump(last, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)
        print("sent" if ok else "send failed"); return
    last = json.load(open(LAST, encoding="utf-8")) if os.path.exists(LAST) else {}
    cfg = json.load(open(CFG, encoding="utf-8")); poll = cfg.get("poll_min", 5) * 60
    pending, seen = None, 0
    import socket
    lock = socket.socket(); lock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try: lock.bind(("127.0.0.1", 48765))     # 한 개만 돌게
    except OSError: log("already running, exit"); return
    log("start"); beat = 0; disp = 0
    while True:
        try:
            if time.time() - beat > 3600:
                ok = alive(); log(f"alive {'ok' if ok else 'FAIL'}")
                if ok: beat = time.time()
            # 매일 아침 7시(화~토, 미국 장 마감 뒤) 자료·판 다시 만들기 → watch_state.json 갱신 (게시는 따로)
            lt = datetime.datetime.now()
            if lt.weekday() in (1, 2, 3, 4, 5) and lt.hour >= 7 and last.get("upd") != lt.strftime("%Y-%m-%d"):
                r = subprocess.run([sys.executable, "update_all.py"], cwd=B, capture_output=True, timeout=3600)
                log(f"update_all exit {r.returncode}")
                if r.returncode == 0:
                    last["upd"] = lt.strftime("%Y-%m-%d"); json.dump(last, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)
            anyopen = any(market_open(a) for a in SYM)
            if anyopen and time.time() - disp > 870:      # 깃허브 예약은 몇 시간씩 늦음 → 장중엔 PC 가 페이지 갱신을 직접 요청
                disp = time.time(); r = subprocess.run(["gh", "workflow", "run", "daily.yml", "-R", "kunchan70-creator/asset-timing", "-f", "mode=quick"], capture_output=True, timeout=60); log(f"page refresh {'ok' if r.returncode == 0 else 'FAIL'}")
            c = compute(); last["notes"] = (last.get("notes") or []) + apply_arrows(c, last); c["notes"] = last["notes"]; k = key_of(c)
            ny = datetime.datetime.now(NY)
            if ny.weekday() < 5 and (ny.hour, ny.minute) >= (9, 0) and (ny.hour, ny.minute) < (9, 30) and last.get("pre") != ny.date().isoformat():
                ll = limit_lines(c)
                if ll: c["notes"] = c["notes"] + ["📝 오늘 주문할 가격이에요 (장 시작 전)"]
                last["pre"] = ny.date().isoformat()
            json.dump(last, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)
            write_live(c)
            with open(os.path.join(B, "logs", "watch_status.txt"), "w", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now():%m-%d %H:%M} 장중={anyopen}\n" + title_of(c) + "\n" + text_of(c))
            if c["notes"]:      # 매수·매도 문구는 기다리지 않고 바로
                if send(c, diff(last.get("key"), k)): last.update({"key": k, "at": datetime.datetime.now().isoformat(), "seq": SEQ[0], "notes": []}); json.dump(last, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)
                pending = None
            elif k != last.get("key"):
                # 장중에는 두 번 연속 같아야 보냄(깜빡임 방지), 장 밖(판 갱신 등)은 바로
                if anyopen and pending != k: pending, seen = k, 1
                else:
                    ch = diff(last.get("key"), k)
                    if send(c, ch): last.update({"key": k, "at": datetime.datetime.now().isoformat(), "seq": SEQ[0]}); json.dump(last, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)
                    pending = None
            else: pending = None
            time.sleep(poll if anyopen else 600)
        except KeyboardInterrupt:
            log("stop"); break
        except Exception as e:
            log(f"err {e!r}"); time.sleep(120)


if __name__ == "__main__":
    main()
