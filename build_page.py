# -*- coding: utf-8 -*-
"""자산 시황판 화면 (2026-10-20): data/judge.json -> dashboard.html
py build_page.py
"""
import os, sys, json, datetime
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
J = json.load(open(os.path.join(B, "data", "judge.json"), encoding="utf-8"))

data = []
for a, r in J["assets"].items():
    rl = r.get("rule")
    st = "none"
    if rl and rl["pass"]:
        st = "hold" if r["count"] >= rl["k"] else "ok"
    elif rl is None:
        st = "nodata"
    per = []
    if rl:
        for k, lab in (("A", "~1999"), ("B", "2000~13"), ("V", "2014~")):
            s = rl[k]
            per.append({"lab": lab, "hit": None if s["hit"] is None or s["n"] < 6 else round(s["hit"] * 100),
                        "base": None if s["base"] is None else round(s["base"] * 100), "ep": s["ep"]})
    an = r.get("analog") or {}
    data.append({
        "id": a, "name": r["name"], "count": r["count"], "full": r["full"], "st": st,
        "k": rl["k"] if rl else None, "per": per,
        "lit": [nm for nm, v in r["lights"].items() if v],
        "off": [nm for nm, v in r["lights"].items() if v is False],
        "picks": [{"m": p["m"].replace("-", "."), "ex": round(p["ex"])} for p in an.get("picks", [])][:4],
        "base_bad": round(r["base_all"]["bad"] * 100), "from": r["base_all"]["from"][:4],
    })

asof = datetime.date.today().strftime("%Y.%m.%d")
html = r"""<title>자산 시황판</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* 레이아웃: 한 줄 요약 → 자산 카드 격자(상태 알약·경고등 점·기간별 적중 막대·비슷한 과거) */
:root{
 --bg:#F5F7FA; --card:#FFFFFF; --line:#E3E9F2; --fg:#16202E; --sub:#5B6676; --mute:#8D97A6;
 --blue:#2B6BF3; --warn:#E8770B; --warn-bg:#FFF1E3; --up:#12A150; --down:#E0453A; --ok-bg:#EAF1FF; --gray-bg:#EEF1F5;
 --sans:"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
 --bg:#0F141B; --card:#171E28; --line:#263142; --fg:#E8EDF4; --sub:#A3AEBE; --mute:#748094;
 --blue:#5B8DF7; --warn:#F2994A; --warn-bg:#3A2716; --up:#3CC77A; --down:#F06A60; --ok-bg:#1A2742; --gray-bg:#222B37; color-scheme:dark}}
:root[data-theme="dark"]{
 --bg:#0F141B; --card:#171E28; --line:#263142; --fg:#E8EDF4; --sub:#A3AEBE; --mute:#748094;
 --blue:#5B8DF7; --warn:#F2994A; --warn-bg:#3A2716; --up:#3CC77A; --down:#F06A60; --ok-bg:#1A2742; --gray-bg:#222B37; color-scheme:dark}
body{background:var(--bg);color:var(--fg);font-family:var(--sans);font-size:15px;line-height:1.55;
 padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:24px 40px}
.wrap{max-width:1040px;margin:0 auto;display:grid;gap:20px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px}
h1{font-size:22px;font-weight:700;margin:0;text-wrap:balance}
.asof{color:var(--mute);font-size:13px;font-variant-numeric:tabular-nums}
.sum{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 20px;display:grid;gap:4px}
.sum .q{color:var(--sub);font-size:14px}
.sum .a{font-size:24px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px;display:grid;gap:12px;min-width:0;align-content:start}
.top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.nm{font-size:17px;font-weight:700}
.pill{font-size:12.5px;font-weight:500;padding:4px 10px;border-radius:999px;white-space:nowrap}
.pill.hold{background:var(--warn-bg);color:var(--warn)}
.pill.ok{background:var(--ok-bg);color:var(--blue)}
.pill.none,.pill.nodata{background:var(--gray-bg);color:var(--sub)}
.lights{display:flex;align-items:center;gap:10px}
.dots{display:flex;gap:4px;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:var(--gray-bg);border:1px solid var(--line)}
.dot.on{background:var(--warn);border-color:var(--warn)}
.cnt{font-family:var(--mono);font-size:14px;color:var(--sub);font-variant-numeric:tabular-nums}
.litnames{font-size:13px;color:var(--fg);display:flex;flex-wrap:wrap;gap:6px}
.chip{background:var(--warn-bg);color:var(--warn);border-radius:8px;padding:2px 8px;font-size:12.5px}
.chip.quiet{background:var(--gray-bg);color:var(--sub)}
.sec{display:grid;gap:6px}
.lab{font-size:12px;color:var(--mute);letter-spacing:.02em}
.bars{display:grid;grid-template-columns:auto 1fr auto;gap:5px 8px;align-items:center;font-size:12.5px;font-variant-numeric:tabular-nums}
.bars .p{color:var(--sub)}
.track{position:relative;height:10px;background:var(--gray-bg);border-radius:5px;overflow:visible}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:5px;background:var(--warn)}
.fill.weak{background:var(--mute)}
.goal{position:absolute;top:-3px;bottom:-3px;width:0;border-left:1.5px dashed var(--fg);opacity:.45;left:80%}
.base{position:absolute;top:2px;bottom:2px;width:2px;background:var(--fg);opacity:.35}
.v{font-family:var(--mono);min-width:3.2em;text-align:right}
.picks{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;font-variant-numeric:tabular-nums}
.picks .m{color:var(--sub)}
.up{color:var(--up)} .down{color:var(--down)}
.note{font-size:12.5px;color:var(--mute)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--sub);align-items:center}
.legend i{display:inline-block;vertical-align:-1px;margin-right:5px}
</style>
<div class="wrap">
 <header><h1>자산 시황판</h1><span class="asof">__ASOF__ 기준 · 월 자료</span></header>
 <section class="sum" aria-live="polite"><span class="q">지금 관망 신호가 켜진 자산</span><span class="a" id="sumA"></span><span class="note" id="sumN"></span></section>
 <div class="legend">
  <span><i class="dot on" style="display:inline-block"></i>경고등 켜짐</span>
  <span><i style="width:16px;height:8px;background:var(--warn);border-radius:4px"></i>관망 때 1년 뒤 현금이 나았던 비율(적중)</span>
  <span><i style="width:0;height:12px;border-left:1.5px dashed var(--fg);opacity:.5"></i>목표 80%</span>
  <span><i style="width:2px;height:10px;background:var(--fg);opacity:.4"></i>평소</span>
 </div>
 <div class="grid" id="grid"></div>
 <p class="note">적중 = 관망 신호가 켜진 달 가운데 1년 뒤 그 자산 수익이 단기금리(현금)보다 낮았던 비율. 경고등 문턱은 최근 20년 자기 역사 상·하위 20%. 2014년 이후는 규칙을 정할 때 보지 않은 기간. 비슷한 과거는 예측력 검증을 통과하지 못해 참고용.</p>
</div>
<script>
const D=__DATA__;
const ST={hold:"관망",ok:"보통",none:"판정 없음",nodata:"판정 없음"};
const holds=D.filter(d=>d.st==="hold");
document.getElementById("sumA").textContent=holds.length?holds.map(d=>d.name).join(" · "):"없음";
const passed=D.filter(d=>d.st==="hold"||d.st==="ok").map(d=>d.name);
document.getElementById("sumN").textContent="관망 판정은 검증을 통과한 "+(passed.join("·")||"자산")+"만 냅니다. 나머지는 경고등 상태만 보여 줍니다.";
const g=document.getElementById("grid");
for(const d of D){
 const c=document.createElement("article");c.className="card";
 let dots="";for(let i=0;i<d.full;i++)dots+=`<span class="dot${i<d.count?" on":""}"></span>`;
 const chips=d.lit.length?d.lit.map(n=>`<span class="chip">${n}</span>`).join(""):`<span class="chip quiet">켜진 경고등 없음</span>`;
 let bars="";
 if(d.per.length){
  bars=`<div class="sec"><span class="lab">경고 ${d.k}개 이상일 때 관망 적중</span><div class="bars">`+
  d.per.map(p=>{
   const h=p.hit, w=h==null?0:h, weak=h==null||h<75;
   return `<span class="p">${p.lab}</span><span class="track"><span class="fill${weak?" weak":""}" style="width:${w}%"></span>${p.base!=null?`<span class="base" style="left:${p.base}%"></span>`:""}<span class="goal"></span></span><span class="v">${h==null?"표본 적음":h+"%"}</span>`;
  }).join("")+`</div></div>`;
 } else {
  bars=`<div class="sec"><span class="lab">관망 적중</span><span class="note">${d.from}년부터 자료뿐이라 규칙을 정하고 따로 시험할 기간이 없음</span></div>`;
 }
 const picks=d.picks.length?`<div class="sec"><span class="lab">지금과 비슷했던 때 → 1년 뒤 현금 대비 · 참고용</span><div class="picks">`+
  d.picks.map(p=>`<span><span class="m">${p.m}</span> <span class="${p.ex>=0?"up":"down"}">${p.ex>0?"+":""}${p.ex}%</span></span>`).join("")+`</div></div>`:"";
 c.innerHTML=`<div class="top"><span class="nm">${d.name}</span><span class="pill ${d.st}">${ST[d.st]}</span></div>
  <div class="lights"><span class="dots">${dots}</span><span class="cnt">${d.count}/${d.full}</span></div>
  <div class="litnames">${chips}</div>${bars}${picks}`;
 g.appendChild(c);
}
</script>
"""
html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__ASOF__", asof)
open(os.path.join(B, "dashboard.html"), "w", encoding="utf-8").write(html)
print("ok", len(data))
