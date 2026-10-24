# -*- coding: utf-8 -*-
"""월 패널 만들기 (2026-10-20): 자산 총수익 지수 + 현금 + 후보 지표.
정답(부동산 매수 판단과 같은 틀) = 앞으로 12개월 자산 수익 < 같은 기간 현금(단기금리) 수익 → '관망이 나았던 달'.
지표는 그 달 말에 알 수 있던 값만(월간 발표 거시는 1~2개월 늦춤). 자기 가격 추세는 지표 후보에서 뺀다(이미 빠진 시세로 켜는 건 예측 아님).
py panel.py -> data/panel.pkl
"""
import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(B, "data", "raw")


def s(name):
    p = os.path.join(RAW, name + ".csv")
    d = pd.read_csv(p)
    d.index = pd.PeriodIndex(d["date"], freq="M")
    return d["value"].astype(float)


def splice(old, new):
    """old 뒤에 new 의 변화율을 이어 붙임(겹치는 마지막 달 기준)."""
    old = old.dropna(); new = new.dropna()
    common = old.index.intersection(new.index)
    if len(common) == 0:
        return old
    k = common[-1]
    tail = new[new.index > k] / new[k] * old[k]
    return pd.concat([old, tail])


def splice_pref(old, new):
    """new(월말 값)가 있는 달은 new, 그 전은 old 를 new 첫 달에 맞춰 이어 붙임(10-21: 월평균이 최근까지 남아 ETF와 어긋나던 문제)."""
    old = old.dropna(); new = new.dropna()
    k = new.index[0]
    if k not in old.index:
        return new
    head = old[old.index < k] / old[k] * new[k]
    return pd.concat([head, new])


def build():
    idx = pd.period_range("1953-01", pd.Timestamp.today().strftime("%Y-%m"), freq="M")
    P = pd.DataFrame(index=idx)

    # ---- 현금 ----
    tb = s("f_TB3MS").reindex(idx).ffill()
    P["cash_us"] = (1 + tb / 100 / 12).cumprod()
    # 1991 이전은 한국 국채 수익률로 대신(10-21: 코스피 1981~ 연장)
    kr3 = s("f_IR3TIB01KRM156N").combine_first(s("f_INTGSBKRM193N")).reindex(idx).ffill()
    P["cash_kr"] = (1 + kr3 / 100 / 12).cumprod()
    jp = s("f_IRSTCI01JPM156N").combine_first(s("f_INTDSRJPM193N")).reindex(idx).ffill()   # 일본 콜금리(1985~), 이전 재할인율
    P["cash_jp"] = (1 + jp / 100 / 12).cumprod()

    # ---- 자산 총수익 지수 ----
    # S&P500: 야후 월말 + 배당수익률(실러, 이후 마지막 값 유지)
    spx = s("y_spx").reindex(idx)
    dy = (s("sh_div") / s("sh_price")).reindex(idx).ffill()
    r = spx.pct_change() + dy / 12
    P["spx"] = (1 + r.fillna(0)).cumprod().where(spx.notna())
    nas = s("y_nasdaq").reindex(idx)
    P["nasdaq"] = (1 + (nas.pct_change() + 0.01 / 12).fillna(0)).cumprod().where(nas.notna())
    ks = splice(s("f_SPASTT01KRM661N")[:"1996-12"], s("y_kospi")).reindex(idx)   # OECD 한국 주가(1981~) + 야후
    P["kospi"] = (1 + (ks.pct_change() + 0.015 / 12).fillna(0)).cumprod().where(ks.notna())
    gold = splice_pref(s("wb_gold"), s("y_gold_f")).reindex(idx)
    gold[gold.index < pd.Period("1971-08", "M")] = np.nan   # 금본위(고정가) 이전 제외
    P["gold"] = gold
    P["comm"] = splice_pref(s("wb_allcomm"), s("y_gsci")).reindex(idx)
    sil = splice_pref(s("wb_silver"), s("y_silver_f")).reindex(idx)
    sil[sil.index < pd.Period("1971-08", "M")] = np.nan
    P["silver"] = sil
    nk = s("y_nikkei").reindex(idx)
    P["nikkei"] = (1 + (nk.pct_change() + 0.015 / 12).fillna(0)).cumprod().where(nk.notna())   # 배당 연 1.5% 근사
    for k, dv in (("dji", 0.02), ("sox", 0.01), ("rut", 0.013)):   # 가격지수 + 배당 근사
        x = s("y_" + k).reindex(idx)
        P[k] = (1 + (x.pct_change() + dv / 12).fillna(0)).cumprod().where(x.notna())
    P["schd"] = s("y_schd").reindex(idx)   # 수정주가 = 배당 포함
    for k in ("em_f", "hy_f", "reit_f"):
        P[k[:-2]] = s("y_" + k).reindex(idx)
    P["oil"] = splice_pref(s("wb_crude"), s("y_wti_f")).reindex(idx)
    P["copper"] = splice_pref(s("wb_copper"), s("y_copper_f")).reindex(idx)
    P["btc"] = s("y_btc").reindex(idx)
    # 미 국채 총수익: 만기 N년 액면채를 매달 다시 사는 근사. 10-21: 월말 금리(DGS 일별의 월말)로 — 월평균은 IEF 상관 0.72
    y = splice(s("f_GS10"), s("f_DGS10")).reindex(idx).ffill() / 100          # 지표용(월평균) 그대로
    def tr(ye, years):
        y0 = ye.shift(1); n = years * 12 - 1; c = y0 / 2
        price = c / (ye / 2) * (1 - (1 + ye / 2) ** (-n / 6)) + (1 + ye / 2) ** (-n / 6)
        return (1 + (price - 1 + y0 / 12).fillna(0)).cumprod().where(ye.notna())
    y10e = s("e_DGS10").combine_first(s("f_GS10")).reindex(idx).ffill() / 100
    P["ust10"] = tr(y10e, 10)
    y30e = s("e_DGS30").combine_first(s("e_DGS20")).reindex(idx) / 100       # 30년물 없던 2002~06 은 20년물
    y30e[y30e.index < pd.Period("1977-02", "M")] = np.nan
    P["ust30"] = tr(y30e, 30)
    # 달러(원화 투자자): 미 현금 + 환율
    fx = splice_pref(s("f_DEXKOUS"), s("y_usdkrw")).reindex(idx)
    P["usd"] = P["cash_us"] * fx   # 원화로 본 달러 예금
    P["usdkrw"] = fx

    # ---- 지표(그 달 말에 알 수 있던 값) ----
    lag1 = lambda x: x.shift(1)   # 다음 달 발표
    g = lambda nm: s(nm).reindex(idx)
    gs10 = y * 100
    P["tb3"] = tb
    P["ff"] = g("f_FEDFUNDS").ffill()
    P["d_ff12"] = P["ff"] - P["ff"].shift(12)
    two = g("f_DGS2")
    P["y2"] = two.fillna(tb)   # 1976 이전은 3개월물로
    P["d_y2_12"] = P["y2"] - P["y2"].shift(12)
    P["d_y10_12"] = gs10 - gs10.shift(12)
    P["curve"] = gs10 - tb
    P["curve_min12"] = P["curve"].rolling(12).min()
    cpi = lag1(g("f_CPIAUCSL"))
    P["cpi_yoy"] = (cpi / cpi.shift(12) - 1) * 100
    core = lag1(g("f_CPILFESL"))
    P["core6"] = ((core / core.shift(6)) ** 2 - 1) * 100
    P["d_cpi12"] = P["cpi_yoy"] - P["cpi_yoy"].shift(12)
    P["real10"] = gs10 - P["cpi_yoy"]
    P["d_real10_12"] = P["real10"] - P["real10"].shift(12)
    tips = g("f_DFII10")
    P["tips"] = tips
    P["d_tips12"] = tips - tips.shift(12)
    P["real_ff"] = P["ff"] - P["cpi_yoy"]
    baa = g("f_BAA")
    P["baa_spr"] = baa - gs10
    P["d_spr6"] = P["baa_spr"] - P["baa_spr"].shift(6)
    P["d_spr12"] = P["baa_spr"] - P["baa_spr"].shift(12)
    nf = g("f_NFCI")
    P["nfci"] = nf
    P["d_nfci6"] = nf - nf.shift(6)
    P["vix"] = g("f_VIXCLS")
    un = lag1(g("f_UNRATE"))
    P["sahm"] = un.rolling(3).mean() - un.rolling(3).mean().rolling(12).min()
    P["d_un12"] = un - un.shift(12)
    ic = g("f_ICSA")
    P["claims"] = (ic.rolling(3).mean() / ic.rolling(3).mean().rolling(12).min() - 1) * 100
    ip = lag1(g("f_INDPRO"))
    P["ip_yoy"] = (ip / ip.shift(12) - 1) * 100
    P["d_ip_yoy6"] = P["ip_yoy"] - P["ip_yoy"].shift(6)
    pay = lag1(g("f_PAYEMS"))
    P["pay3"] = (pay / pay.shift(3) - 1) * 400
    perm = lag1(g("f_PERMIT"))
    P["permit_yoy"] = (perm.rolling(3).mean() / perm.rolling(3).mean().shift(12) - 1) * 100
    P["cfnai3"] = g("f_CFNAI").shift(1).rolling(3).mean()
    P["sent"] = lag1(g("f_UMCSENT"))
    P["d_sent12"] = P["sent"] - P["sent"].shift(12)
    m2 = lag1(g("f_M2SL"))
    P["m2_yoy"] = (m2 / m2.shift(12) - 1) * 100
    P["m2_real"] = P["m2_yoy"] - P["cpi_yoy"]
    cr = lag1(g("f_TOTALSL"))
    P["credit_yoy"] = (cr / cr.shift(12) - 1) * 100
    walcl = g("f_WALCL")
    P["fedbs_yoy"] = (walcl / walcl.shift(12) - 1) * 100
    dxy = g("y_dxy")
    P["dxy12"] = (dxy / dxy.shift(12) - 1) * 100
    P["dxy6"] = (dxy / dxy.shift(6) - 1) * 100
    P["krw12"] = (fx / fx.shift(12) - 1) * 100
    ex = g("f_XTEXVA01KRM667S").shift(2)
    P["kr_exp_yoy"] = (ex.rolling(3).mean() / ex.rolling(3).mean().shift(12) - 1) * 100
    P["kr_y3"] = kr3
    P["d_kr3_12"] = kr3 - kr3.shift(12)
    P["oil12"] = (P["oil"] / P["oil"].shift(12) - 1) * 100
    P["comm12"] = (P["comm"] / P["comm"].shift(12) - 1) * 100
    P["copper_gold"] = P["copper"] / P["gold"]
    P["d_cg12"] = (P["copper_gold"] / P["copper_gold"].shift(12) - 1) * 100
    # 밸류에이션: CAPE(실러) — 2023-09 이후는 S&P 가격 비율로 연장(이익 증가 무시 = 다소 높게 셈)
    cape = s("sh_cape").reindex(idx)
    last = cape.last_valid_index()
    ext = cape.copy()
    ext[ext.index > last] = (cape[last] * spx / spx[last])[ext.index > last]
    P["cape"] = ext
    rcpi = splice(s("sh_cpi"), s("f_CPIAUCSL")).reindex(idx).ffill()
    P["gold_real"] = P["gold"] / rcpi
    P["comm_real"] = P["comm"] / rcpi
    P["oil_real"] = P["oil"] / rcpi
    return P


ASSETS = {  # 자산: (총수익 지수 열, 현금 열, 이름)
    "spx": ("spx", "cash_us", "S&P500"),
    "nasdaq": ("nasdaq", "cash_us", "나스닥"),
    "kospi": ("kospi", "cash_kr", "코스피"),
    "gold": ("gold", "cash_us", "금"),
    "comm": ("comm", "cash_us", "원자재"),
    "oil": ("oil", "cash_us", "원유"),
    "copper": ("copper", "cash_us", "구리"),
    "silver": ("silver", "cash_us", "은"),
    "nikkei": ("nikkei", "cash_jp", "일본 닛케이"),
    "em": ("em", "cash_us", "신흥국 주식"),
    "dji": ("dji", "cash_us", "다우"),
    "sox": ("sox", "cash_us", "필라델피아 반도체"),
    "rut": ("rut", "cash_us", "러셀2000"),
    "schd": ("schd", "cash_us", "SCHD"),
    "hy": ("hy", "cash_us", "미 하이일드 채권"),
    "reit": ("reit", "cash_us", "미 리츠"),
    "ust10": ("ust10", "cash_us", "미 국채10년"),
    "ust30": ("ust30", "cash_us", "미 장기채(30년)"),
    "btc": ("btc", "cash_us", "비트코인"),
    "usd": ("usd", "cash_kr", "달러(원화)"),
}


def targets(P, h=12):
    T = pd.DataFrame(index=P.index)
    for a, (col, cash, _) in ASSETS.items():
        fr = P[col].shift(-h) / P[col] - 1
        fc = P[cash].shift(-h) / P[cash] - 1
        T[a + "_ex"] = (fr - fc) * 100          # 앞으로 12개월 초과 수익(%p)
        T[a + "_bad"] = (fr < fc).where(fr.notna() & fc.notna())  # 관망이 나았다
    return T


if __name__ == "__main__":
    P = build()
    T = targets(P)
    pd.to_pickle({"P": P, "T": T}, os.path.join(B, "data", "panel.pkl"))
    for a in ASSETS:
        b = T[a + "_bad"].dropna()
        print(f"{a:7s} {str(b.index[0]) if len(b) else '-':8s}~{str(b.index[-1]) if len(b) else '-':8s} n={len(b):4d} bad={b.mean()*100:5.1f}%  ex_med={T[a+'_ex'].median():6.1f}")
