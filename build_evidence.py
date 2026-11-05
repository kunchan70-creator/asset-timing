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
        rows.append([f"{W.index[a].date()}", f"{W.index[b].date()}", pct(ret * 100), pct(cr * 100), pct(low * 100), ("<b class=g>맞음</b>" if ret < cr else "<b class=r>틀림</b>") if done else "진행 중"])
    return table(["켜진 날", "마지막 날", "그 뒤 6개월까지 주가", "그동안 현금", "그 안 최저", "팔았다면"], rows), good, n


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
    return table(["3/3 켜져 판 날", "10개월선 위로 와서 다시 산 날", "그 사이 주가", "그 사이 최저", "팔아서"], rows)


t_us, g_us, n_us = warn_table(("nasdaq", "spx"), "nasdaq", "cash_us"); t_sp, g_sp, n_sp = warn_table(("nasdaq", "spx"), "spx", "cash_us"); t_k, g_k, n_k = warn_table(("kospi",), "kospi", "cash_kr")
rules = {(r["asset"], r["kind"]): r for r in R if r["status"] == "확정"}
html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>자산 신호판 근거</title>
<style>:root{{--bg:#F5F6F8;--card:#fff;--fg:#17191F;--sub:#5B6170;--line:#E3E6EC;--g:#12804A;--r:#C9342F;--a:#2B6BF3}}
@media (prefers-color-scheme:dark){{:root{{--bg:#101218;--card:#191C24;--fg:#EDEFF4;--sub:#A2A8B6;--line:#2C303B;--g:#3CC77A;--r:#F0726D;--a:#6E9AF8}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:20px 16px 60px}}h1{{font-size:24px;margin:8px 0 4px}}h2{{font-size:18px;margin:0 0 8px}}h3{{font-size:15px;margin:16px 0 6px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}}p{{margin:6px 0}}.s{{color:var(--sub);font-size:13.5px}}a{{color:var(--a)}}
.tw{{overflow-x:auto;margin:8px 0}}table{{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}}th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;white-space:nowrap}}th{{color:var(--sub);font-weight:600}}
.g{{color:var(--g)}}.r{{color:var(--r)}}.weak{{border-left:3px solid var(--r);padding:4px 10px;margin:10px 0;font-size:14px}}.why{{border-left:3px solid var(--a);padding:4px 10px;margin:10px 0;font-size:14px}}ul{{margin:6px 0;padding-left:20px}}</style></head><body><div class="wrap">
<p><a href="./">← 신호판으로</a></p><h1>근거</h1><p class="s">과거 자료로 시험한 결과예요. 세금·수수료 전, 종가나 지정가에 정확히 체결됐다고 가정했어요. 맞을 확률이지 보장이 아니에요. 사건 표는 자료로 매번 다시 계산하고, 나머지는 2026-11-06에 돌린 숫자예요.</p>

<section><h2>먼저 읽기: 얼마나 믿을 수 있나</h2><ul>
<li><b>사례가 적어요.</b> 경고는 35년에 몇 번뿐이고, '경고 꺼진 6개월' 저점은 8~9번, 하락장 3/3은 8번이에요.</li>
<li><b>결과를 보고 고른 값이 섞여 있어요.</b> 2010년까지로 고르고 2011년 뒤로 확인했지만, 여러 번 돌려 본 값이라 실제보다 좋게 나왔을 거예요.</li>
<li><b>2008년 같은 하락은 경고가 안 켜졌어요.</b> 최대 낙폭이 −55%로 그대로 남아요.</li>
<li><b>이득은 작고 손실은 커요.</b> 반등 매매는 거래당 +2~5%인데, 틀리면 −15~−30%예요.</li></ul></section>

<section><h2>1. 경고: 왜 파나</h2>
<p class="why"><b>이치:</b> 주가가 이미 많이 오른 상태에서 금리·물가·유가가 같이 뛰면, 연준 긴축과 비용 부담이 오고 비싼 주식의 값이 깎여요. 2년물은 앞으로의 기준금리를 미리 반영하는 금리예요.</p>
<ul><li><b>나스닥 경고:</b> 많이 오름 상위 20% + 2년물 1년 상승 상위 30%</li><li><b>S&amp;P 강한 경고:</b> 많이 오름 상위 20% + (2년물·10년물·물가·유가) 중 3개 이상</li><li><b>코스피 경고:</b> 많이 오름 상위 30% + 한국 수출 증가율 상위 30%</li><li>백분위는 지난 20년 안에서의 위치예요. 둘 중 하나만 켜져도 나스닥·S&amp;P 함께 따라요. 다우는 새로 안 사기만 해요.</li></ul>
<h3>경고 때 샀다면, 1년 뒤 현금보다 못한 비율</h3>{table(["", "나스닥에 사면", "S&P에 사면", "다우에 사면"], [["아무 때나", "27%", "28%", "22%"], ["나스닥 경고", "79%", "76%", "69%"], ["S&P 강한 경고", "84%", "85%", "100%"]])}
<h3>나스닥: 실제 사건 (팔았다면 맞음 {g_us}/{n_us})</h3>{t_us}<h3>S&amp;P: 실제 사건 (맞음 {g_sp}/{n_sp})</h3>{t_sp}<h3>코스피: 실제 사건 (맞음 {g_k}/{n_k})</h3>{t_k}
<p class="weak"><b>약점:</b> 경고가 꺼져도 하락이 끝난 게 아니에요(2000, 2022). 장중 값은 금요일 종가로 확인 전까지 추정이에요.</p></section>

<section><h2>2. 조심 구간: 왜 6개월인가</h2>
<p class="why"><b>이치:</b> 경고가 꺼졌다는 건 대개 주가가 빠졌다는 뜻이에요. 금리·유가 압력은 아직 남아 있어서 바로 평시로 돌아가면 위험해요.</p>
<h3>경고 꺼진 지 13주 안에 아무 날 샀다면 (1991~)</h3>{table(["", "1년 오름", "−10% 더 빠짐", "1년 평균"], [["나스닥 평시", "86%", "33%", "+18%"], ["나스닥 경고 꺼진 13주", "72%", "72%", "0%"], ["S&P 평시", "86%", "23%", "+12%"], ["S&P 경고 꺼진 13주", "74%", "65%", "+4%"]])}
<h3>구간을 얼마로 두나 (규칙 전체, 끝나면 남은 현금 전부 삼. 앞 ~2010 / 뒤 2011~)</h3>{table(["끝 기준", "나스닥", "낙폭", "S&P", "코스피"], [["경고 뒤 13주", "×7.2 / ×14.3", "−68% / −30%", "×4.1 / ×7.3", "×5.3 / ×4.3"], ["<b>경고 뒤 26주 (씀)</b>", "<b>×14.3 / ×13.5</b>", "−56% / −30%", "×5.4 / ×7.1", "×5.3 / ×4.7"], ["경고 뒤 52주", "×13.6 / ×13.3", "−56% / −30%", "×5.1 / ×7.0", "×5.1 / ×4.8"], ["10개월선 회복", "×5.4 / ×14.9", "−74% / −30%", "×3.9 / ×7.9", "×4.7 / ×4.4"], ["그냥 보유", "×7.1 / ×9.2", "−78% / −36%", "×3.9 / ×5.9", "×2.9 / ×2.8"]])}
<p class="weak"><b>약점:</b> 26주와 52주는 차이가 없어서, 6개월이 정답이라기보다 "3개월은 너무 이르다"에 가까워요. 경고 사건이 적어요.</p></section>

<section><h2>3. 저점: 어디에 걸어두나</h2>
<p class="why"><b>이치:</b> 공포에 과하게 던진 뒤에는 되돌림이 나와요. 걸어두는 값은 "오늘 종가가 이 값이면 RSI 30"인 가격이에요. 저가가 찍고 바로 튀어도 체결돼요. VIX 30↑ 또는 공포탐욕 30↓일 때만 유효해요(코스피는 VIX만).</p>
<h3>이 값에 사서 규칙대로 팔았다면 (이득 / 10번 중 9번은 이 안 / 최악 / 횟수)</h3>{table(["상황", "나스닥", "S&P", "다우", "코스피"], [["평시", "94% / −11% / −18% / 53번", "93% / −9% / −30% / 44번", "98% / −9% / −34% / 49번", "85% / −32% / −38% / 13번"], ["경고 중", "100% / −12% / −13% / 4번", "100% / −3% / −5% / 6번", "100% / −4% / −5% / 7번", "–"], ["경고 꺼진 6개월", "75% / −16% / −33% / 8번", "89% / −9% / −17% / 9번", "100% / −7% / −7% / 7번", "100% / −2% / −2% / 1번"], ["하락 추세", "82% / −21% / −31% / 28번", "95% / −14% / −15% / 19번", "89% / −14% / −21% / 18번", "83% / −20% / −32% / 18번"]])}
<h3>왜 RSI + 공포인가: 진짜 저점을 몇 번 잡았나 (1991~, 미국 지수당 약 48번)</h3>{table(["조합", "잡은 저점 (나스닥)", "아무 날보다 더 싸게 (1년 나눠 산 평균 대비)"], [["VIX 40↑", "6번", "13.1%"], ["RSI 30↓ + VIX 30↑", "9번", "4.9%"], ["RSI 30↓ + 공포탐욕 30↓", "21번", "3.5%"], ["RSI 35↓ + 고점 −5%", "35번", "0.7~1.8%"], ["공포탐욕 30↓만", "–", "0.5%"]])}
<p class="s">많이 잡을수록 덜 싸고, 싸게 살수록 드물어요. 둘 다 되는 조합은 못 찾았어요.</p>
<p class="weak"><b>약점:</b> 2000년 10월처럼 −33%까지 빠진 경우가 있어요. 그때 QLD 환산 최악은 −58%예요.</p></section>

<section><h2>4. 매도가: 왜 빠진 폭의 20%인가</h2>
<p class="why"><b>이치:</b> 깊이 빠질수록 반등이 커요. 그래서 고정 %가 아니라 빠진 폭에 비례해 정해요. <b>매도가 = 산 값 + (60일 고점 − 산 값) × 20%</b>. 60거래일 안에 못 닿으면 팔아요.</p>
<h3>빠진 깊이별 60일 안 반등 (나스닥 / S&P 중앙값)</h3>{table(["60일 고점 대비", "나스닥", "S&P"], [["10~15%", "+8%", "+7%"], ["15~20%", "+14%", "+15%"], ["20~30%", "+19%", "+21%"], ["30%↑", "+23%", "–"]])}
<h3>되돌림 비율별 (경고 지속 구간, 네 지수 합. 앞 ~2010 / 뒤 2011~)</h3>{table(["비율", "닿음", "거래당", "최악"], [["15%", "93% / 100%", "+4.7% / +3.1%", "−15% / +1%"], ["<b>20% (씀)</b>", "<b>88% / 94%</b>", "<b>+5.1% / +3.4%</b>", "−15% / −8%"], ["25%", "75% / 94%", "+4.4% / +4.0%", "−26% / −8%"], ["33%", "나스닥 62% / 60%", "+4.8% / +2.0%", "−26% / −7%"], ["50%", "나스닥 33% / 40%", "+1.9% / +2.1%", "−28% / −7%"]])}
<p class="weak"><b>약점:</b> 비율에 민감해요. 나스닥 복리가 15%에서 ×2.2, 25%에서 ×1.1로 흔들려요. 몇 번의 큰 거래가 좌우해요. 평시 저점은 팔지 말고 들고 가는 게 나았어요(거래당 +11% vs +5%).</p></section>

<section><h2>5. 2차 매수: 왜 7% 더 빠질 때인가</h2>
<p class="why"><b>이치:</b> 매수값보다 충분히 더 빠져야 평균을 낮추는 효과가 있어요. RSI 25는 금방 와서 겨우 2.6% 낮게 사게 돼요.</p>
{table(["2차 기준 (조심 구간, 네 지수 합)", "횟수", "닿음", "거래당", "최악"], [["RSI 25 값", "38", "92%", "+3.5%", "−19%"], ["공포탐욕 20↓", "34", "91%", "+2.6%", "−22%"], ["VIX 40↑", "16", "94%", "+5.3%", "−6%"], ["60일 고점 −20%", "25", "72%", "+2.0%", "−24%"], ["지난 매수값 −5%", "37", "95%", "+4.6%", "−11%"], ["<b>지난 매수값 −7% (씀)</b>", "<b>27</b>", "<b>96%</b>", "<b>+5.5%</b>", "<b>−7%</b>"], ["지난 매수값 −10%", "21", "90%", "+5.9%", "−6%"]])}
<p class="weak"><b>약점:</b> 2011년 뒤 사례는 5번뿐이에요. −7%와 −10%는 차이가 크지 않아요.</p></section>

<section><h2>6. 하락장 3/3: 왜 나스닥만 파나</h2>
<p class="why"><b>이치:</b> 거품(2년 안 상위 10%) + 10개월선 아래로 꺾임 + 침체 신호가 겹치면 2000년형 붕괴와 닮아요. 그때 반등 뒤 반년 더 오른 건 나스닥 12%뿐이었어요.</p>
{table(["3/3에 전부 팔고 10개월선 위에서 다시 사기", "그냥 보유", "규칙", "판단"], [["나스닥 (1981~)", "×197 · −77%", "<b>×486 · −53%</b>", "<b class=g>팔기</b>"], ["S&P (1963~)", "×575 · −55%", "×651 · −55%", "거의 같음, 안 팖"], ["다우 (2001~)", "×8.5 · −52%", "×6.5 · −52%", "<b class=r>손해</b>, 안 팖"], ["코스피 (2006~)", "×5.4 · −53%", "×7.0 · −38%", "1번뿐, 판단 못 함"]])}
<h3>나스닥: 실제 사건</h3>{bear_table("nasdaq")}
<p class="weak"><b>약점:</b> 나스닥 이득의 대부분이 2000~2003년에서 나왔어요. 절반은 팔자마자 돌아와서 약간 손해였어요.</p></section>

<section><h2>7. 규칙 전체를 처음부터 끝까지</h2>
<p>현금 1로 시작해 규칙대로 사고팔았을 때예요(앞 ~2010, 뒤 2011~ 각각 새로 시작). 경고 때 팔고, 조심 구간엔 저점만 반등 매매, 조심 끝나면 남은 현금 전부 사서 보유.</p>
{table(["", "규칙", "그냥 보유", "규칙 낙폭", "보유 낙폭"], [["나스닥", "×14.3 / ×13.5", "×7.1 / ×9.2", "−56% / −30%", "−78% / −36%"], ["S&P", "×5.4 / ×7.1", "×3.9 / ×5.9", "−57% / −34%", "−57% / −34%"], ["다우", "×3.6 / ×4.8", "×3.7 / ×4.5", "−54% / −37%", "−54% / −37%"], ["코스피", "×5.3 / ×4.7", "×2.9 / ×2.8", "−56% / −38%", "−65% / −44%"]])}
<p class="weak"><b>약점:</b> 이 계산은 2차 간격 5% 기준이고 −7%로 다시 돌리지 않았어요. 하락장 3/3 매도도 안 들어 있어요. 낙폭은 2008년 때문에 크게 안 줄었어요.</p></section>

<section><h2>8. 시험했지만 뺀 것</h2><ul>
<li><b>채권:</b> 예금보다 연 2%p 남짓, 80% 넘는 신호 없음.</li><li><b>금:</b> 아무 때나 54%, 사는 신호 84%(7번)뿐이고 파는 신호 없음.</li><li><b>경고 때 배당주로 갈아타기:</b> 1980년부터 보면 단기국채가 나음(연 13.8% vs 12.7%).</li><li><b>싸게 환전(환율 RSI):</b> 59%(아무 날 49%), 아끼는 돈 1.4%.</li><li><b>환율 급등 경보:</b> 위기마다 원인이 달라 적중 26%.</li><li><b>QQQ 자체 RSI:</b> 나스닥 지수 RSI보다 나빴음(거래당 +2.2% vs +4.4%).</li></ul></section>
</div></body></html>"""
open("evidence.html", "w", encoding="utf-8").write(html); print("ok evidence", len(html))
