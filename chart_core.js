/* 주식 앱식 차트 부품 (2026-10-21). 로그 세로축 = 실제 값, 끌기=이동, 휠·두 손가락=확대·축소, 누르기=값 보기, 두 번 누르기=처음으로.
   LChart(canvas, data, opt)
   data = {p:[[t,v]...], bad:[[a,b]], sell:[[a,b]] 관망 신호, hold:[[a,b]] 신호 뒤 유지(후속 조치), buy:[[a,b]], known, unit}
   opt  = {view:{v0,v1} 공유 객체(여러 차트 맞춤), onView(), xmin, xmax, css(name)}  */
function LChart(c, d, opt) {
  const S = { hover: null, ptrs: new Map(), drag: null, pinch: null };
  const V = opt.view;
  const css = opt.css;
  const PADL = 54, PADR = 8, PADT = 8, PADB = 20;
  const t0 = d.p[0][0], t1 = d.p[d.p.length - 1][0];
  const XMIN = opt.xmin ?? t0, XMAX = (opt.xmax ?? t1) + 0.05;
  const inA = (arr, t) => { for (const [a, b] of arr) if (t >= a && t < b) return true; return false; };
  // 10-21: 주마다 상태 코드(d.s: M 매수 · R 강한 관망 · O 관망 · H 관망 유지 · N 보통)가 있으면 띠를 그 코드로만 만든다 → 겹침·어긋남 없음
  if (d.s && d.s.length === d.p.length) {
    const runs = c => { const out = []; let st = -1; for (let i = 0; i <= d.p.length; i++) { const on = i < d.p.length && d.s[i] === c; if (on && st < 0) st = i; if (!on && st >= 0) { out.push([d.p[st][0], i < d.p.length ? d.p[i][0] : d.p[i - 1][0] + 0.02]); st = -1; } } return out; };
    d.buy = runs("M"); d.strong = runs("R"); d.sell = runs("O"); d.hold = runs("H"); d.shold = runs("S");
  }
  function fmt(v) {
    const a = Math.abs(v);
    if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
    if (a >= 1e4) return Math.round(v).toLocaleString("ko-KR");
    if (a >= 100) return Math.round(v).toLocaleString("ko-KR");
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return v.toPrecision(2);
  }
  function dstr(t) {
    const y = Math.floor(t), doy = (t - y) * 365.25, dt = new Date(Date.UTC(y, 0, 1) + doy * 864e5);
    return `${dt.getUTCFullYear()}.${String(dt.getUTCMonth() + 1).padStart(2, "0")}.${String(dt.getUTCDate()).padStart(2, "0")}`;
  }
  function geom() {
    const r = c.getBoundingClientRect();
    return { W: r.width, H: r.height, left: r.left, X: t => PADL + (t - V.v0) / (V.v1 - V.v0) * (r.width - PADL - PADR) };
  }
  function tAt(clientX) {
    const g = geom(); return V.v0 + (clientX - g.left - PADL) / (g.W - PADL - PADR) * (V.v1 - V.v0);
  }
  function clampView() {
    let span = Math.max(0.15, Math.min(XMAX - XMIN, V.v1 - V.v0));
    let a = V.v0, b = a + span;
    if (a < XMIN) { a = XMIN; b = a + span; }
    if (b > XMAX) { b = XMAX; a = b - span; }
    V.v0 = a; V.v1 = b;
  }
  function zoomAt(t, f) {
    V.v0 = t - (t - V.v0) * f; V.v1 = t + (V.v1 - t) * f; clampView(); opt.onView();
  }
  function nearest(t) {
    let lo = 0, hi = d.p.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (d.p[m][0] <= t) lo = m; else hi = m; }
    return Math.abs(d.p[hi][0] - t) < Math.abs(d.p[lo][0] - t) ? d.p[hi] : d.p[lo];
  }
  let raf = 0;
  function draw() { if (!raf) raf = requestAnimationFrame(() => { raf = 0; render(); }); }
  function render() {
    const dp = devicePixelRatio || 1, r = c.getBoundingClientRect();
    const cw = Math.round(r.width * dp), chh = Math.round(r.height * dp);
    if (c.width !== cw || c.height !== chh) { c.width = cw; c.height = chh; }
    const g = c.getContext("2d"); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height); g.setTransform(dp, 0, 0, dp, 0, 0);
    const W = r.width, H = r.height, X = t => PADL + (t - V.v0) / (V.v1 - V.v0) * (W - PADL - PADR);
    // 11-01 사용자: 보조지표(RSI·공포탐욕·VIX)가 있으면 아래 40%를 보조 차트로 — 위 가격 차트 바닥 = MB
    const MB = d.ind ? Math.round(H * 0.6) : H - PADB, IT = MB + 18, IB = H - PADB;
    const vis = d.p.filter(p => p[0] >= V.v0 - 0.1 && p[0] <= V.v1 + 0.1);
    g.font = "11px " + css("--sans"); g.fillStyle = css("--mute");
    if (vis.length < 2) { g.textAlign = "left"; g.fillText("이 구간 자료 없음", PADL + 8, H / 2); return; }
    const lv = vis.map(p => Math.log(p[1])), lo = Math.min(...lv), hi = Math.max(...lv), pd = (hi - lo) * 0.08 || 0.05;
    const Y = v => PADT + (1 - (Math.log(v) - lo + pd) / (hi - lo + 2 * pd)) * (MB - PADT);
    // 세로 눈금 = 실제 값(1·2·5 단위)
    const vlo = Math.exp(lo - pd), vhi = Math.exp(hi + pd); let ticks = [];
    for (let e = Math.floor(Math.log10(vlo)) - 1; e <= Math.ceil(Math.log10(vhi)) + 1; e++)
      for (const m of [1, 1.5, 2, 3, 5, 7]) { const v = m * Math.pow(10, e); if (v >= vlo && v <= vhi) ticks.push(v); }
    const used = []; g.textAlign = "right";
    for (const v of ticks.sort((a, b) => a - b)) {
      const yy = Y(v); if (yy < PADT + 6 || yy > MB - 4 || used.some(u => Math.abs(u - yy) < 20)) continue; used.push(yy);
      g.strokeStyle = css("--grid"); g.lineWidth = 1; g.beginPath(); g.moveTo(PADL, yy); g.lineTo(W - PADR, yy); g.stroke();
      g.fillStyle = css("--mute"); g.fillText(fmt(v), PADL - 6, yy + 4);
    }
    g.save(); g.beginPath(); g.rect(PADL, 0, W - PADL - PADR, H); g.clip();
    // 가로 눈금
    const span = V.v1 - V.v0; g.textAlign = "center";
    if (span > 3) {
      const st = span > 40 ? 10 : span > 18 ? 5 : span > 8 ? 2 : 1;
      for (let y = Math.ceil(V.v0 / st) * st; y <= V.v1; y += st) {
        g.strokeStyle = css("--grid"); g.beginPath(); g.moveTo(X(y), PADT); g.lineTo(X(y), H - PADB); g.stroke();
        g.fillStyle = css("--mute"); g.fillText(String(y), X(y), H - 5);
      }
    } else {
      const stepM = span > 1.5 ? 3 : 1;
      for (let m = Math.ceil(V.v0 * 12 / stepM) * stepM; m <= V.v1 * 12; m += stepM) {
        const t = m / 12, yr = Math.floor(t), mo = Math.round((t - yr) * 12) + 1;
        g.strokeStyle = css("--grid"); g.beginPath(); g.moveTo(X(t), PADT); g.lineTo(X(t), H - PADB); g.stroke();
        g.fillStyle = css("--mute"); g.fillText(mo === 1 ? String(yr) : `${String(yr).slice(2)}.${String(mo).padStart(2, "0")}`, X(t), H - 5);
      }
    }
    const band = (arr, col, al) => { g.fillStyle = css(col); g.globalAlpha = al; for (const [a, b] of arr) if (b > V.v0 && a < V.v1) g.fillRect(X(a), PADT, Math.max(1.5, X(b) - X(a)), MB - PADT); g.globalAlpha = 1; };
    band(d.bad || [], "--badband", 1); band(d.sell || [], "--sell", 0.30); band(d.strong || [], "--red", 0.30);   // 11-01 사용자: 매수는 기간 색칠 없이 화살표만
    // 11-02: 환율 국면(한미 금리차) — 그래프 위쪽 얇은 띠. 진한 파랑 = 달러 우위(미국 금리 0.5%p↑), 옅은 파랑 = 중립, 회색 = 원화 우위
    for (const [a, b, k] of (d.rg || [])) {
      if (!(b > V.v0 && a < V.v1)) continue;
      g.fillStyle = css(k === "lo" ? "--mute" : "--hold"); g.globalAlpha = k === "hi" ? 0.85 : k === "mid" ? 0.35 : 0.25;
      g.fillRect(X(a), PADT, Math.max(1.5, X(b) - X(a)), 7); g.globalAlpha = 1;
    }
    // 신호 뒤 유지 기간: 옅은 빗금(신호 자체와 구분)
    for (const [a, b, hc] of [...(d.hold || []).map(r => [r[0], r[1], "--sell"]), ...(d.shold || []).map(r => [r[0], r[1], "--red"])]) {
      if (!(b > V.v0 && a < V.v1)) continue;
      const xa = X(a), xb = X(b);
      g.save(); g.beginPath(); g.rect(xa, PADT, Math.max(1.5, xb - xa), MB - PADT); g.clip();
      g.fillStyle = css(hc); g.globalAlpha = 0.07; g.fillRect(xa, PADT, xb - xa, MB - PADT);
      g.globalAlpha = 0.35; g.strokeStyle = css(hc); g.lineWidth = 1;
      for (let x = xa - H; x < xb; x += 7) { g.beginPath(); g.moveTo(x, MB); g.lineTo(x + H, PADT); g.stroke(); }
      g.restore();
    }
    if (d.known && t1 > d.known && d.known < V.v1) {
      g.save(); g.beginPath(); g.rect(X(d.known), PADT, X(t1 + 0.02) - X(d.known), H - PADT - PADB); g.clip();
      g.strokeStyle = css("--line"); g.lineWidth = 1;
      for (let x = X(d.known) - H; x < X(t1 + 0.02); x += 6) { g.beginPath(); g.moveTo(x, H - PADB); g.lineTo(x + H, PADT); g.stroke(); }
      g.restore();
    }
    g.lineJoin = "round"; g.lineCap = "round";
    const colOf = t => (inA(d.strong || [], t) || inA(d.shold || [], t)) ? css("--red") : (inA(d.sell || [], t) || inA(d.hold || [], t)) ? css("--sell") : css("--line-main");
    let i0 = 1; while (i0 < d.p.length && d.p[i0][0] < V.v0 - 0.1) i0++;
    const step = Math.max(1, Math.floor(vis.length / ((W - PADL - PADR) * 1.5)));
    let curK = null, kp = Math.max(0, i0 - 1);
    const flush = () => { if (curK !== null) { g.stroke(); curK = null; } };
    for (let k = Math.max(1, i0); k < d.p.length; k = (k + step < d.p.length || k === d.p.length - 1) ? k + step : d.p.length - 1) {
      const a = d.p[kp], b = d.p[k]; if (a[0] > V.v1 + 0.1) break;
      if (b[0] - a[0] > 1.5 * step) { flush(); kp = k; if (k === d.p.length - 1) break; continue; }
      const c0 = a[0], sc = colOf(c0), lw = (inA(d.sell || [], c0) || inA(d.strong || [], c0)) ? 2.8 : 1.7, al = (inA(d.hold || [], c0) || inA(d.shold || [], c0)) ? 0.6 : 1, key = sc + lw + al;
      if (key !== curK) { flush(); g.strokeStyle = sc; g.lineWidth = lw; g.globalAlpha = al; g.beginPath(); g.moveTo(X(a[0]), Y(a[1])); curK = key; }
      g.lineTo(X(b[0]), Y(b[1])); kp = k;
      if (k === d.p.length - 1) break;
    }
    flush();
    g.globalAlpha = 1;
    // 10-21: 기준선(환율: 5년 평균 +15% — 이 선 위면 환전 미루기)
    for (const [rr, rc] of [[d.ref, "--sell"], [d.ref2, "--buy"]]) {
      if (!rr || !rr.length) continue;
      g.strokeStyle = css(rc); g.lineWidth = 1.4; g.setLineDash([3, 3]); g.beginPath(); let st = false;
      for (const [t, v] of rr) { if (t < V.v0 - 0.1 || t > V.v1 + 0.1) { st = false; continue; } if (!st) { g.moveTo(X(t), Y(v)); st = true } else g.lineTo(X(t), Y(v)); }
      g.stroke(); g.setLineDash([]);
    }
    // 10-21 사용자: 매수 = 아래에서 위로 초록 화살표, 매도(경고) = 위에서 아래로 빨간 화살표. 신호가 처음 켜진 곳에. 틀리면 회색
    const MCOL = { buy: "--buy", bulk: "--buy", sell: "--red", inv: "--red", defer: "--sell", fearx: "--sell", fg1: "--hold", trend: "--fg", fxdip: "--buy" };   // trend = 고점 −20% 뒤 회복(주 단위)   // fg1 = RSI<30+공포탐욕<30 (참고 매수)   // fearx = 경고 기간이라 무시된 공포 조건
    for (const m of (d.marks || [])) {
      if (m.t0 < V.v0 || m.t0 > V.v1) continue;
      const x = X(m.t0), y = Y(m.v0), up = m.kind === "buy" || m.kind === "bulk" || m.kind === "fearx" || m.kind === "fg1" || m.kind === "trend" || m.kind === "fxdip";
      const col = css(MCOL[m.kind] || "--red");   // 10-21 사용자: 틀린 신호도 원래 색 그대로
      const tip = up ? y + 5 : y - 5, tail = up ? y + 24 : y - 24;
      g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 2.2;
      g.beginPath(); g.moveTo(x, tail); g.lineTo(x, tip + (up ? 6 : -6)); g.stroke();
      g.beginPath(); g.moveTo(x, tip); g.lineTo(x - 5, tip + (up ? 8 : -8)); g.lineTo(x + 5, tip + (up ? 8 : -8)); g.closePath(); g.fill();
    }
    // ---- 보조 차트: RSI(14)·공포탐욕(CNN, 2011 전은 추정)·VIX, 0~100 한 축. 30 선 = 매수 조건 문턱 ----
    const RT = d.ind && d.ind.mode === "rates";      // 11-02: 환율 보조 차트 = 한미 금리(%), 축은 보이는 구간에 맞춤
    let rMax = 100;
    if (RT) { rMax = 1; for (let i = 0; i < d.p.length; i++) { const t = d.p[i][0]; if (t < V.v0 || t > V.v1) continue; for (const k of ["us", "kr"]) { const v = d.ind[k][i]; if (v != null && v > rMax) rMax = v; } } rMax = Math.ceil(rMax + 0.5); }
    if (d.ind) {
      const IY = v => IT + (1 - Math.max(0, Math.min(rMax, v)) / rMax) * (IB - IT);
      g.strokeStyle = css("--grid"); g.lineWidth = 1; g.beginPath(); g.moveTo(PADL, IT - 6); g.lineTo(W - PADR, IT - 6); g.stroke();
      g.setLineDash([4, 3]); g.strokeStyle = css("--mute");
      for (const v of (RT ? [Math.round(rMax / 2)] : [30, 70])) { g.beginPath(); g.moveTo(PADL, IY(v)); g.lineTo(W - PADR, IY(v)); g.stroke(); }
      g.setLineDash([]);
      const SER = RT ? [["us", "--hold", 1.6], ["kr", "--sell", 1.6]] : [["rsi", "--line-main", 1.3], ["fg", "--sell", 1.6], ["vix", "--red", 1.3]];
      for (const [k, col, lw] of SER) {
        const arr = d.ind[k]; if (!arr) continue;
        g.strokeStyle = css(col); g.lineWidth = lw;
        let open = null, ip = Math.max(0, i0 - 1);
        for (let i = Math.max(1, i0); i < d.p.length; i += step) {
          const ta = d.p[ip][0], tb = d.p[i][0]; if (ta > V.v1 + 0.1) break;
          const va = arr[ip], vb = arr[i];
          if (va == null || vb == null || tb - ta > 1.5 * step) { if (open !== null) { g.stroke(); open = null; } ip = i; continue; }
          const al = (k === "fg" && d.ind.est_until && tb <= d.ind.est_until) ? 0.45 : 0.95;
          if (al !== open) { if (open !== null) g.stroke(); g.globalAlpha = al; g.beginPath(); g.moveTo(X(ta), IY(va)); open = al; }
          g.lineTo(X(tb), IY(vb)); ip = i;
        }
        if (open !== null) g.stroke();
      }
      g.globalAlpha = 1;
    }
    g.textBaseline = "alphabetic";
    g.restore();
    if (d.ind) {
      g.font = "10px " + css("--sans"); g.textAlign = "right"; g.fillStyle = css("--mute");
      for (const v of (RT ? [Math.round(rMax / 2), rMax] : [30, 70])) g.fillText(RT ? v + "%" : String(v), PADL - 6, IT + (1 - v / rMax) * (IB - IT) + 3);
      g.textAlign = "left"; let lx = PADL + 4;
      for (const [lab, col] of RT ? [["미국 금리(3개월 국채)", "--hold"], ["한국 금리(3년 국채)", "--sell"]] : [["RSI", "--line-main"], ["공포탐욕" + (d.ind.est_until && V.v0 < d.ind.est_until ? "(흐린 선=추정)" : ""), "--sell"], ["VIX", "--red"]]) {
        g.fillStyle = css(col); g.fillText(lab, lx, IT + 4); lx += g.measureText(lab).width + 10;
      }
    }
    // 마지막 값
    const lp = d.p[d.p.length - 1];
    if (lp[0] >= V.v0 && lp[0] <= V.v1 + 0.1) { g.fillStyle = css("--fg"); g.beginPath(); g.arc(X(lp[0]), Y(lp[1]), 3.2, 0, 7); g.fill(); }
    // 십자선 + 값
    const ht = opt.sharedHover ? opt.sharedHover.t : S.hover;
    if (ht != null && ht >= V.v0 && ht <= V.v1 && ht >= t0 - 0.05 && ht <= t1 + 0.05) {
      const p = nearest(ht), x = X(p[0]), y = Y(p[1]), pi = d.p.indexOf(p);
      g.strokeStyle = css("--fg"); g.globalAlpha = 0.45; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x, PADT); g.lineTo(x, H - PADB); g.moveTo(PADL, y); g.lineTo(W - PADR, y); g.stroke(); g.globalAlpha = 1;
      const iv = d.ind && pi >= 0 ? (RT ? ["us", "kr"] : ["rsi", "fg", "vix"]).map(k => d.ind[k] ? d.ind[k][pi] : null) : null;
      g.fillStyle = css("--fg"); g.beginPath(); g.arc(x, y, 3.8, 0, 7); g.fill();
      const st = inA(d.buy || [], p[0]) ? "매수 신호" : inA(d.strong || [], p[0]) ? "강한 관망" : inA(d.sell || [], p[0]) ? (d.sellTxt || "관망 신호") : inA(d.shold || [], p[0]) ? "강한 관망 유지(신호 뒤 1년)" : inA(d.hold || [], p[0]) ? "관망 유지(신호 뒤 1년)" : (d.s ? "보통 · 신호 없음" : "");
      const BT = d.badT || d.bad || [], res = (!d.badT && !(d.bad || []).length) || (d.known && p[0] > d.known) ? "" : inA(BT, p[0]) ? (d.badTxt || "이때 샀다면 1년 뒤 현금보다 못함") : (d.goodTxt || "이때 샀다면 1년 뒤 현금보다 나음");
      const rgk = (d.rg || []).find(r => p[0] >= r[0] && p[0] < r[1]);
      const txt = [dstr(p[0]), fmt(p[1]) + (d.unit ? " " + d.unit : ""), st, rgk ? { hi: "달러 우위 국면", mid: "금리차 중립", lo: "원화 우위 국면" }[rgk[2]] : "", (d.pl && st && d.pl[st]) || "", res].filter(Boolean).join(" · ");
      g.font = "12px " + css("--sans"); const tw = g.measureText(txt).width + 14;
      let bx = x + 10; if (bx + tw > W - PADR) bx = x - 10 - tw; bx = Math.max(PADL, bx);
      const txt2 = iv && RT ? `미국 ${iv[0] ?? "-"}% · 한국 ${iv[1] ?? "-"}%${iv[0] != null && iv[1] != null ? ` · 차 ${(iv[0] - iv[1] > 0 ? "+" : "") + (iv[0] - iv[1]).toFixed(2)}%p` : ""}` : iv ? `RSI ${iv[0] ?? "-"} · 공포탐욕 ${iv[1] ?? "-"}${d.ind.est_until && p[0] <= d.ind.est_until ? "(추정)" : ""} · VIX ${iv[2] ?? "-"}${d.ind.daily ? "" : "  (그 주 최저·최저·최고)"}` : "";
      const tw2 = txt2 ? g.measureText(txt2).width + 14 : 0, TW = Math.max(tw, tw2);
      let bx2 = x + 10; if (bx2 + TW > W - PADR) bx2 = x - 10 - TW; bx2 = Math.max(PADL, bx2);
      g.fillStyle = css("--tip-bg"); g.globalAlpha = 0.94; g.fillRect(bx2, PADT + 2, TW, txt2 ? 40 : 22); g.globalAlpha = 1;
      g.fillStyle = css("--tip-fg"); g.textAlign = "left"; g.fillText(txt, bx2 + 7, PADT + 17);
      if (txt2) g.fillText(txt2, bx2 + 7, PADT + 35);
      // 오른쪽 축 값 표시
      g.fillStyle = css("--fg"); g.textAlign = "right"; g.font = "11px " + css("--mono");
    }
  }
  // ---- 조작 ----
  c.style.touchAction = "pan-y";
  c.style.userSelect = "none"; c.style.webkitUserSelect = "none"; c.style.webkitTouchCallout = "none";
  let T = null;
  c.addEventListener("touchstart", e => {
    if (e.touches.length === 1) { const t = e.touches[0]; T = { mode: "?", x: t.clientX, y: t.clientY, v0: V.v0, v1: V.v1 }; }
    else if (e.touches.length >= 2) {
      const a = e.touches[0], b = e.touches[1];
      T = { mode: "pinch", d: Math.abs(a.clientX - b.clientX) || 1, v0: V.v0, v1: V.v1, mid: tAt((a.clientX + b.clientX) / 2) }; e.preventDefault();
    }
  }, { passive: false });
  c.addEventListener("touchmove", e => {
    if (!T) return;
    if (T.mode === "pinch" && e.touches.length >= 2) {
      e.preventDefault(); const a = e.touches[0], b = e.touches[1], f = T.d / (Math.abs(a.clientX - b.clientX) || 1);
      V.v0 = T.mid - (T.mid - T.v0) * f; V.v1 = T.mid + (T.v1 - T.mid) * f; clampView(); opt.onView(); return;
    }
    if (e.touches.length !== 1) return;
    const t = e.touches[0], dx = t.clientX - T.x, dy = t.clientY - T.y;
    if (T.mode === "?") { if (Math.abs(dx) > 6 && Math.abs(dx) >= Math.abs(dy)) T.mode = "pan"; else if (Math.abs(dy) > 6) T.mode = "scroll"; }
    if (T.mode === "pan") {
      e.preventDefault(); const g = geom(), dt = dx / (g.W - PADL - PADR) * (T.v1 - T.v0);
      V.v0 = T.v0 - dt; V.v1 = T.v1 - dt; clampView(); opt.onView();
    }
  }, { passive: false });
  c.addEventListener("touchend", e => {
    if (T && T.mode === "?" && e.changedTouches.length) setHover(tAt(e.changedTouches[0].clientX));
    if (e.touches.length === 1 && T && T.mode === "pinch") { const t = e.touches[0]; T = { mode: "pan", x: t.clientX, y: t.clientY, v0: V.v0, v1: V.v1 }; }
    else if (e.touches.length === 0) T = null;
  });
  c.addEventListener("pointerdown", e => {
    if (e.pointerType === "touch") return;
    S.ptrs.set(e.pointerId, e.clientX);
    if (S.ptrs.size === 1) { S.drag = { x: e.clientX, v0: V.v0, v1: V.v1, moved: false }; }
    if (S.ptrs.size === 2) { const xs = [...S.ptrs.values()]; S.pinch = { d: Math.abs(xs[0] - xs[1]) || 1, v0: V.v0, v1: V.v1, mid: tAt((xs[0] + xs[1]) / 2) }; S.drag = null; }
    try { c.setPointerCapture(e.pointerId); } catch (_) {}
  });
  c.addEventListener("pointermove", e => {
    if (e.pointerType === "touch") return;
    if (S.ptrs.has(e.pointerId)) S.ptrs.set(e.pointerId, e.clientX);
    if (S.pinch && S.ptrs.size >= 2) {
      const xs = [...S.ptrs.values()], dd = Math.abs(xs[0] - xs[1]) || 1, f = S.pinch.d / dd;
      V.v0 = S.pinch.mid - (S.pinch.mid - S.pinch.v0) * f; V.v1 = S.pinch.mid + (S.pinch.v1 - S.pinch.mid) * f; clampView(); opt.onView(); return;
    }
    if (S.drag) {
      const g = geom(), dx = e.clientX - S.drag.x;
      if (Math.abs(dx) > 3) S.drag.moved = true;
      if (S.drag.moved) {
        const dt = dx / (g.W - PADL - PADR) * (S.drag.v1 - S.drag.v0);
        V.v0 = S.drag.v0 - dt; V.v1 = S.drag.v1 - dt; clampView(); opt.onView(); return;
      }
    }
    setHover(tAt(e.clientX));
  });
  const end = e => {
    if (e.pointerType === "touch") return;
    S.ptrs.delete(e.pointerId);
    if (S.drag && !S.drag.moved && e.type === "pointerup") setHover(tAt(e.clientX));
    if (S.ptrs.size < 2) S.pinch = null;
    if (S.ptrs.size === 0) S.drag = null;
  };
  c.addEventListener("pointerup", end); c.addEventListener("pointercancel", end);
  c.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") setHover(null); });
  c.addEventListener("wheel", e => { e.preventDefault(); zoomAt(tAt(e.clientX), Math.exp(e.deltaY * 0.0015)); }, { passive: false });
  c.addEventListener("dblclick", () => { if (opt.reset) opt.reset(); });
  function setHover(t) { if (opt.sharedHover) { opt.sharedHover.t = t; opt.onView(); } else { S.hover = t; draw(); } }
  return { draw };
}
