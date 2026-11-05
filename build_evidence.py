# -*- coding: utf-8 -*-
"""근거 페이지 (2026-11-06, 사용자: '왜 경고인지·왜 꺼졌는지, 그 근거 페이지까지 있어야 믿고 누른다').
사건 표(경고·하락장)는 자료로 매번 다시 계산. 나머지 시험 결과는 2026-11-06 에 돌린 숫자(logs/_*.txt, 만든 스크립트 _*.py).
py build_evidence.py -> evidence.html"""
import os, sys, json
import numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, B); os.chdir(B)
import evolve as EV
from weekly import from_month
W, Q = EV.W, EV.Q; R = json.load(open("data/rules.json", encoding="utf-8"))


def table(head, rows, cls=""):
    return f'<div class="tw"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>"


def pct(x, d=0): return f"{x:+.{d}f}%"


def eps(sig, gap=26):
    o = []
    for i in np.where(sig.values)[0]:
        if o and i - o[-1][1] <= gap: o[-1][1] = i
        else: o.append([i, i])
    return o


def warn_table(assets, price, cash):
    s = pd.Series(False, index=W.index)
    for r in R:
        if r["status"] == "확정" and r["kind"] in ("관망", "강한관망") and r["asset"] in assets: s |= EV.signal(r, r["asset"], EV.FW).reindex(W.index).fillna(False)
    px = W[price]; c = W[cash]; rows = []; good = n = 0
    for a, b in eps(s & px.notna()):
        e = min(b + 26, len(W) - 1); done = b + 26 < len(W)
        ret = px.iloc[e] / px.iloc[a] - 1; cr = c.iloc[e] / c.iloc[a] - 1; low = px.iloc[a:e + 1].min() / px.iloc[a] - 1
        if done: n += 1; good += ret < cr
        rows.append([f"{W.index[a].date()}", f"{W.index[b].date()}", pct(ret * 100), pct(cr * 100), pct(low * 100), ("<b class=g>잘 판 것</b>" if ret < cr else "<b class=r>괜히 판 것</b>") if done else "진행 중"])
    return table(["켜진 날", "마지막 날", "6개월 뒤까지 주가", "그동안 예금", "가장 많이 빠졌을 때", "팔았다면"], rows), good, n


def bear_table(a):
    px = W[a]; ma = px.rolling(43).mean(); tr = ((px < ma) & (ma < ma.shift(13))).fillna(False); sahm = from_month("sahm")
    bub = (Q["dev5_" + a] >= .9).astype(float).rolling(104, min_periods=1).max().astype(bool); rec = ((sahm >= .5) | (Q["claims"] >= .7)).astype(float).rolling(26, min_periods=1).max().astype(bool)
    b3 = (tr & bub & rec).fillna(False).values; p = px.values; m = ma.values; c = W["cash_us"].values; rows = []; i = 1; n = len(p)
    while i < n:
        if b3[i] and not np.isnan(p[i]):
            j = i + 1
            while j < n - 1 and not p[j] > m[j]: j += 1
            ret = p[j] / p[i] - 1; cr = c[j] / c[i] - 1
            rows.append([f"{W.index[i].date()}", f"{W.index[j].date()}", pct(ret * 100), pct((np.nanmin(p[i:j + 1]) / p[i] - 1) * 100), "<b class=g>이득</b>" if ret < cr else "<b class=r>손해</b>"]); i = j + 1
        else: i += 1
    return table(["판 날", "다시 산 날", "그 사이 주가", "가장 많이 빠졌을 때", "팔아서"], rows)


t_us, g_us, n_us = warn_table(("nasdaq", "spx"), "nasdaq", "cash_us"); t_sp, g_sp, n_sp = warn_table(("nasdaq", "spx"), "spx", "cash_us"); t_k, g_k, n_k = warn_table(("kospi",), "kospi", "cash_kr")
rules = {(r["asset"], r["kind"]): r for r in R if r["status"] == "확정"}
html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>신호판 근거</title>
<style>:root{{--bg:#F5F6F8;--card:#fff;--fg:#17191F;--sub:#5B6170;--line:#E3E6EC;--g:#12804A;--r:#C9342F;--a:#2B6BF3}}
@media (prefers-color-scheme:dark){{:root{{--bg:#101218;--card:#191C24;--fg:#EDEFF4;--sub:#A2A8B6;--line:#2C303B;--g:#3CC77A;--r:#F0726D;--a:#6E9AF8}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:20px 16px 60px}}h1{{font-size:24px;margin:8px 0 4px}}h2{{font-size:18px;margin:0 0 8px}}h3{{font-size:15px;margin:16px 0 6px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}}p{{margin:6px 0}}.s{{color:var(--sub);font-size:13.5px}}a{{color:var(--a)}}
.tw{{overflow-x:auto;margin:8px 0}}table{{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}}th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;white-space:nowrap}}th{{color:var(--sub);font-weight:600}}
.g{{color:var(--g)}}.r{{color:var(--r)}}.weak{{border-left:3px solid var(--r);padding:4px 10px;margin:10px 0;font-size:14px}}.why{{border-left:3px solid var(--a);padding:4px 10px;margin:10px 0;font-size:14px}}ul{{margin:6px 0;padding-left:20px}}</style></head><body><div class="wrap">
<p><a href="./">← 신호판으로</a></p><h1>정말 믿어도 되나요?</h1><p class="s">과거 자료로 시험한 결과예요. 앞으로도 똑같다는 보장은 없어요. 세금과 수수료는 안 뺐고, 주문한 가격에 정확히 샀다고 쳤어요.</p>

<section><h2>먼저 알아둘 약점</h2><ul>
<li><b>사례가 적어요.</b> 위험 신호는 35년에 몇 번뿐이고, 신호가 꺼진 뒤 많이 떨어진 날은 8~9번이에요.</li>
<li><b>결과를 보고 고른 값이 섞여 있어요.</b> 그래서 실제로는 여기 숫자보다 못할 수 있어요.</li>
<li><b>2008년 폭락은 신호가 못 잡았어요.</b> 그런 때는 −55%를 그대로 맞아요.</li>
<li><b>벌 땐 조금, 틀리면 크게 잃어요.</b> 많이 떨어질 때 사서 되파는 건 한 번에 +2~5%인데, 틀리면 −15~−30%예요.</li></ul></section>

<section><h2>1. 왜 파나요?</h2>
<p class="why">주가가 이미 많이 올랐는데 금리·기름값·물가까지 뛰면, 돈 빌리는 부담이 커지고 비싼 주식부터 값이 깎여요.</p>
<ul><li><b>나스닥:</b> 주가가 지난 20년 중 비싼 쪽 20%에 들고, 2년 금리도 크게 올랐을 때</li><li><b>S&amp;P:</b> 주가가 비싼 쪽 20%에 들고, 2년 금리·10년 금리·물가·기름값 넷 중 셋이 크게 올랐을 때</li><li><b>코스피:</b> 주가가 비싼 쪽 30%에 들고, 한국 수출도 꼭대기일 때</li><li>미국은 하나만 켜져도 나스닥과 S&amp;P를 같이 팔아요. 다우는 새로 안 사기만 해요.</li></ul>
<h3>이럴 때 샀다면, 1년 뒤 예금보다 못했던 비율</h3>{table(["", "나스닥을 샀다면", "S&P를 샀다면", "다우를 샀다면"], [["아무 때나", "27%", "28%", "22%"], ["나스닥 신호 켜졌을 때", "79%", "76%", "69%"], ["S&P 신호 켜졌을 때", "84%", "85%", "100%"]])}
<h3>나스닥 실제 기록 (팔아서 좋았던 비율 {round(g_us / max(n_us, 1) * 100)}%)</h3>{t_us}<h3>S&amp;P 실제 기록 ({round(g_sp / max(n_sp, 1) * 100)}%)</h3>{t_sp}<h3>코스피 실제 기록 ({round(g_k / max(n_k, 1) * 100)}%)</h3>{t_k}
<p class="weak"><b>약점:</b> 신호가 꺼져도 하락이 끝난 건 아니에요(2000년, 2022년). 평일에 보이는 신호는 금요일 종가로 확정돼요.</p></section>

<section><h2>2. 신호가 꺼졌는데 왜 6개월은 조심하나요?</h2>
<p class="why">신호가 꺼졌다는 건 대개 주가가 떨어졌다는 뜻이에요. 금리·기름값 부담은 아직 남아 있어서, 바로 마음 놓으면 위험해요.</p>
<h3>이럴 때 아무 날이나 샀다면 (1991년부터)</h3>{table(["", "1년 뒤 오른 비율", "10% 넘게 더 빠진 비율", "1년 평균 수익"], [["나스닥 평소", "86%", "33%", "+18%"], ["나스닥 신호 꺼지고 3개월 안", "72%", "72%", "0%"], ["S&P 평소", "86%", "23%", "+12%"], ["S&P 신호 꺼지고 3개월 안", "74%", "65%", "+4%"]])}
<h3>얼마나 조심해야 가장 좋았나 (몇 배가 됐나, 왼쪽은 2010년까지·오른쪽은 2011년부터)</h3>{table(["조심하는 기간", "나스닥", "나스닥 가장 크게 잃은 폭", "S&P", "코스피"], [["3개월", "×7.2 / ×14.3", "−68% / −30%", "×4.1 / ×7.3", "×5.3 / ×4.3"], ["<b>6개월 (이걸 써요)</b>", "<b>×14.3 / ×13.5</b>", "−56% / −30%", "×5.4 / ×7.1", "×5.3 / ×4.7"], ["1년", "×13.6 / ×13.3", "−56% / −30%", "×5.1 / ×7.0", "×5.1 / ×4.8"], ["10개월 평균선 회복까지", "×5.4 / ×14.9", "−74% / −30%", "×3.9 / ×7.9", "×4.7 / ×4.4"], ["그냥 들고 있기", "×7.1 / ×9.2", "−78% / −36%", "×3.9 / ×5.9", "×2.9 / ×2.8"]])}
<p class="weak"><b>약점:</b> 6개월과 1년은 거의 같아요. 6개월이 딱 정답이라기보다 3개월은 너무 이르다는 뜻에 가까워요.</p></section>

<section><h2>3. 많이 떨어졌을 때 얼마에 주문하나요?</h2>
<p class="why">사람들이 겁먹고 한꺼번에 팔면 너무 떨어졌다가 되돌아오곤 해요. 그래서 '많이 떨어졌다'의 기준인 RSI 30이 되는 가격에 미리 주문해둬요. 잠깐 찍고 올라가도 사져요. 시장 공포가 클 때만(VIX 30 넘음 또는 공포탐욕 30 아래) 주문해요.</p>
<h3>이 가격에 사서 규칙대로 팔았다면</h3><p class="s">칸 안의 숫자: 이득 본 비율 / 산 뒤 대부분 이 안쪽까지만 더 빠짐 / 가장 심하게 빠졌을 때 / 횟수</p>{table(["지금 상황", "나스닥", "S&P", "다우", "코스피"], [["평소", "94% / −11% / −18% / 53번", "93% / −9% / −30% / 44번", "98% / −9% / −34% / 49번", "85% / −32% / −38% / 13번"], ["위험 신호 중", "100% / −12% / −13% / 4번", "100% / −3% / −5% / 6번", "100% / −4% / −5% / 7번", "–"], ["신호 꺼지고 6개월 안", "75% / −16% / −33% / 8번", "89% / −9% / −17% / 9번", "100% / −7% / −7% / 7번", "100% / −2% / −2% / 1번"], ["하락 중", "82% / −21% / −31% / 28번", "95% / −14% / −15% / 19번", "89% / −14% / −21% / 18번", "83% / −20% / −32% / 18번"]])}
<h3>왜 이 기준인가: 진짜 바닥을 얼마나 잡았나 (나스닥, 1991년부터)</h3>{table(["기준", "진짜 바닥을 잡은 비율", "1년 나눠 산 것보다 싸게 산 정도"], [["VIX 40 넘음", "13%", "13.1%"], ["RSI 30 + VIX 30 넘음", "19%", "4.9%"], ["RSI 30 + 공포탐욕 30 아래", "44%", "3.5%"], ["RSI 35 + 고점에서 5% 떨어짐", "73%", "0.7~1.8%"], ["공포탐욕 30 아래만", "–", "0.5%"]])}
<p class="s">바닥을 많이 잡을수록 덜 싸고, 싸게 살수록 드물어요. 둘 다 되는 기준은 못 찾았어요.</p>
<p class="weak"><b>약점:</b> 2000년 10월에는 산 뒤 33%까지 더 빠졌어요. QLD였다면 −58%예요.</p></section>

<section><h2>4. 얼마에 파나요?</h2>
<p class="why">깊이 떨어질수록 반등도 커요. 그래서 떨어진 폭의 20%를 되찾으면 팔아요. <b>예: 최근 고점 100에서 떨어져 80에 샀다면 84에 팔아요.</b> 3개월 안에 그 가격이 안 오면 손해여도 팔아요.</p>
<h3>떨어진 깊이별 3개월 안 반등 (보통)</h3>{table(["최근 고점보다 떨어진 폭", "나스닥", "S&P"], [["10~15%", "+8%", "+7%"], ["15~20%", "+14%", "+15%"], ["20~30%", "+19%", "+21%"], ["30% 넘게", "+23%", "–"]])}
<h3>떨어진 폭의 몇 %에서 팔아야 좋았나 (왼쪽은 2010년까지·오른쪽은 2011년부터)</h3>{table(["되찾는 비율", "그 가격까지 오른 비율", "한 번에 평균", "가장 나빴을 때"], [["15%", "93% / 100%", "+4.7% / +3.1%", "−15% / +1%"], ["<b>20% (이걸 써요)</b>", "<b>88% / 94%</b>", "<b>+5.1% / +3.4%</b>", "−15% / −8%"], ["25%", "75% / 94%", "+4.4% / +4.0%", "−26% / −8%"], ["33%", "나스닥 62% / 60%", "+4.8% / +2.0%", "−26% / −7%"], ["50%", "나스닥 33% / 40%", "+1.9% / +2.1%", "−28% / −7%"]])}
<p class="weak"><b>약점:</b> 20%를 조금만 바꿔도 결과가 꽤 달라져요. 몇 번의 큰 거래가 결과를 좌우했어요. 평소에는 팔지 말고 들고 가는 게 나았어요(한 번에 +11%, 팔면 +5%).</p></section>

<section><h2>5. 왜 7% 더 떨어지면 또 사나요?</h2>
<p class="why">충분히 더 떨어져야 평균 가격이 내려가요. RSI 25 같은 기준은 금방 와서 겨우 2.6% 싸게 사게 돼요.</p>
{table(["또 사는 기준", "횟수", "팔 가격까지 오른 비율", "한 번에 평균", "가장 나빴을 때"], [["RSI 25", "38", "92%", "+3.5%", "−19%"], ["공포탐욕 20 아래", "34", "91%", "+2.6%", "−22%"], ["VIX 40 넘음", "16", "94%", "+5.3%", "−6%"], ["최근 고점에서 20% 떨어짐", "25", "72%", "+2.0%", "−24%"], ["산 값에서 5% 더 떨어짐", "37", "95%", "+4.6%", "−11%"], ["<b>산 값에서 7% 더 떨어짐 (이걸 써요)</b>", "<b>27</b>", "<b>96%</b>", "<b>+5.5%</b>", "<b>−7%</b>"], ["산 값에서 10% 더 떨어짐", "21", "90%", "+5.9%", "−6%"]])}
<p class="weak"><b>약점:</b> 2011년 뒤 사례는 5번뿐이에요. 7%와 10%는 큰 차이가 없어요.</p></section>

<section><h2>6. 큰 하락장이면 왜 나스닥만 파나요?</h2>
<p class="why">거품이 있었고, 10개월 평균선 아래로 꺾였고, 실업까지 늘면 2000년 닷컴 붕괴와 닮았어요. 그때 나스닥은 반등이 와도 반년 더 오른 경우가 12%뿐이었어요.</p>
{table(["셋 다 켜지면 팔고, 10개월 평균선 위로 오면 다시 사기", "그냥 들고 있기", "규칙대로", "결론"], [["나스닥 (1981년부터)", "×197 · 최대 −77%", "<b>×486 · 최대 −53%</b>", "<b class=g>팔아요</b>"], ["S&P (1963년부터)", "×575 · 최대 −55%", "×651 · 최대 −55%", "거의 같아서 안 팔아요"], ["다우 (2001년부터)", "×8.5 · 최대 −52%", "×6.5 · 최대 −52%", "<b class=r>손해라서 안 팔아요</b>"], ["코스피 (2006년부터)", "×5.4 · 최대 −53%", "×7.0 · 최대 −38%", "1번뿐이라 판단 못 해요"]])}
<h3>나스닥 실제 기록</h3>{bear_table("nasdaq")}
<p class="weak"><b>약점:</b> 이득 대부분이 2000~2003년에서 나왔어요. 절반은 팔자마자 다시 올라서 약간 손해였어요.</p></section>

<section><h2>7. 전부 합치면 얼마나 벌었나요?</h2>
<p>규칙대로 사고팔았을 때 몇 배가 됐는지예요. 왼쪽은 2010년까지, 오른쪽은 2011년부터 새로 시작한 값이에요.</p>
{table(["", "규칙대로", "그냥 들고 있기", "규칙대로 가장 크게 잃은 폭", "들고 있기 가장 크게 잃은 폭"], [["나스닥", "×14.3 / ×13.5", "×7.1 / ×9.2", "−56% / −30%", "−78% / −36%"], ["S&P", "×5.4 / ×7.1", "×3.9 / ×5.9", "−57% / −34%", "−57% / −34%"], ["다우", "×3.6 / ×4.8", "×3.7 / ×4.5", "−54% / −37%", "−54% / −37%"], ["코스피", "×5.3 / ×4.7", "×2.9 / ×2.8", "−56% / −38%", "−65% / −44%"]])}
<p class="weak"><b>약점:</b> 이 계산은 '5% 더 떨어지면 또 사기'로 돌린 값이고, 지금 쓰는 7%로는 다시 안 돌렸어요. 큰 하락장 매도도 안 들어 있어요. 2008년 때문에 크게 잃은 폭은 많이 안 줄었어요.</p></section>

<section><h2>8. 시험했지만 뺀 것</h2><ul>
<li><b>채권:</b> 예금보다 1년에 2% 남짓 더 벌 뿐이고, 믿을 만한 신호가 없어요.</li><li><b>금:</b> 아무 때나 사면 이득 54%. 사는 신호는 84%지만 7번뿐이고, 파는 신호는 못 찾았어요.</li><li><b>위험할 때 배당주로 옮기기:</b> 1980년부터 보면 단기 국채가 나았어요(1년에 13.8%, 배당주 12.7%).</li><li><b>환율 싸게 바꾸는 날:</b> 59%로 아무 날(49%)과 큰 차이가 없고, 아끼는 돈도 1.4%예요.</li><li><b>환율 급등 경보:</b> 위기마다 원인이 달라서 26%만 맞았어요.</li><li><b>QQQ 자체 RSI:</b> 나스닥 지수로 보는 것보다 나빴어요(한 번에 +2.2%, 지수는 +4.4%).</li></ul></section>
</div></body></html>"""
open("evidence.html", "w", encoding="utf-8").write(html); print("ok evidence", len(html))
