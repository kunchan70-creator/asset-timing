# -*- coding: utf-8 -*-
"""자산 시황 판단기 원자료 수집 (2026-10-20). 키 불필요, 무료 공개 자료만.
  야후(월말 종가) · 미 연준 FRED(거시) · 세계은행 원자재(1960~) · 실러 S&P(1871~, 배당 포함)
py fetch.py -> data/raw/*.csv (date,value 월 단위, date=YYYY-MM)
"""
import csv, io, json, os, subprocess, sys, time, datetime
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(B, "data", "raw")
os.makedirs(RAW, exist_ok=True)

YAHOO = {  # 이름: 기호
    "nasdaq": "^IXIC", "ndx": "^NDX", "spx": "^GSPC", "kospi": "^KS11", "nikkei": "^N225",
    "gold_f": "GC=F", "silver_f": "SI=F", "wti_f": "CL=F", "copper_f": "HG=F", "gsci": "^SPGSCI",
    "btc": "BTC-USD", "tlt": "TLT", "ief": "IEF", "dxy": "DX-Y.NYB", "usdkrw": "KRW=X", "vix": "^VIX",
    "eem": "EEM", "hyg": "HYG", "qqq": "QQQ",
    "em_f": "VEIEX", "hy_f": "VWEHX", "reit_f": "FRESX",
    "dji": "^DJI", "sox": "^SOX", "schd": "SCHD", "rut": "^RUT",   # 10-21: 규칙 만들 때 안 본 미국 주식(깨끗한 시험)   # 10-21: 신흥국·하이일드·리츠 장기 펀드(분배금 포함)
}
# FRED: 월평균으로 접음. (자료 시작이 긴 것 위주)
FRED = [
    "TB3MS", "DGS3MO", "DGS2", "DGS10", "GS10", "FEDFUNDS", "T10Y2Y", "T10Y3M",
    "BAA10Y", "AAA10Y", "BAA", "AAA", "BAMLH0A0HYM2", "VIXCLS", "NFCI", "ANFCI", "STLFSI4",
    "UNRATE", "ICSA", "PAYEMS", "INDPRO", "CPIAUCSL", "CPILFESL", "M2SL", "WALCL",
    "DFII10", "T10YIE", "T5YIFR", "DTWEXBGS", "DEXKOUS", "UMCSENT", "PERMIT", "HOUST",
    "IR3TIB01KRM156N", "IRLTLT01KRM156N", "XTEXVA01KRM667S", "LRHUTTTTKRM156S",
    "CFNAI", "TOTALSL", "DRTSCILM", "SAHMREALTIME", "RECPROUSM156N",
    "SPASTT01KRM661N", "INTGSBKRM193N", "IRSTCI01JPM156N", "INTDSRJPM193N", "DEXJPUS", "T10YIE",
    "DCOILWTICO", "GOLDAMGBD228NLBM", "PCOPPUSDM", "CBBTCUSD",
]
WB_URL = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
SHILLER_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"


def curl(url, binary=False, tries=3, ua=True):
    for _ in range(tries):
        try:
            # FRED 는 브라우저 표기(-A)를 붙이면 응답 없이 멈춤(10-20 실측) → ua=False
            r = subprocess.run(["curl", "-s", "-L", "-m", "120"] + (["-A", "Mozilla/5.0"] if ua else []) + [url], capture_output=True, timeout=150)
            if r.stdout:
                return r.stdout if binary else r.stdout.decode("utf-8", "replace")
        except Exception:
            pass
        time.sleep(3)
    return b"" if binary else ""


def save(name, rows):
    """rows: {YYYY-MM: value}"""
    with open(os.path.join(RAW, name + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date", "value"])
        for k in sorted(rows):
            w.writerow([k, rows[k]])


def yahoo(name, sym):
    """일봉을 받아 달마다 마지막 거래일 값(수정주가). 10-21: 월봉은 선물에서 빈 달 46개(날짜 찍힘 충돌)."""
    from urllib.parse import quote
    out = {}
    t = curl(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym)}?period1=-2208988800&period2=9999999999&interval=1d&includeAdjustedClose=true")
    try:
        r = json.loads(t)["chart"]["result"][0]
    except Exception:
        return out
    ind = r["indicators"]
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    off = (r.get("meta") or {}).get("gmtoffset") or 0
    for ts, v in zip(r.get("timestamp") or [], adj):
        if v is None: continue
        d = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=ts + off)
        out[d.strftime("%Y-%m")] = v   # 날짜 순 → 마지막 값이 월말
    return out


def fred(i):
    t = curl(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", ua=False)
    acc = {}
    for r in csv.DictReader(io.StringIO(t)):
        v = r.get(i)
        if v in (None, "", "."): continue
        k = r["observation_date"][:7]
        acc.setdefault(k, []).append(float(v))
    return {k: sum(v) / len(v) for k, v in acc.items()}


EOM = ["DGS10", "DGS20", "DGS30", "DGS2"]   # 10-21: 자산 지수용은 월말 값(월평균은 ETF와 시점 어긋남, IEF 상관 0.72)


def fred_eom(i):
    t = curl(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", ua=False)
    out = {}
    for r in csv.DictReader(io.StringIO(t)):
        v = r.get(i)
        if v in (None, "", "."): continue
        out[r["observation_date"][:7]] = float(v)   # 날짜 순이라 마지막 값 = 월말
    return out


def worldbank():
    import openpyxl
    p = os.path.join(RAW, "_wb.xlsx")
    b = curl(WB_URL, binary=True)
    if b: open(p, "wb").write(b)
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    want = {"wb_gold": "Gold", "wb_silver": "Silver", "wb_crude": "Crude oil, average", "wb_copper": "Copper"}
    ws = wb["Monthly Prices"]
    rows = list(ws.iter_rows(values_only=True))
    hdr_i = next(i for i, r in enumerate(rows) if r and r[0] is None and any(isinstance(c, str) and "Gold" in c for c in r if c))
    hdr = rows[hdr_i]
    res = {}
    for nm, col in want.items():
        j = next(k for k, c in enumerate(hdr) if isinstance(c, str) and c.strip().startswith(col))
        out = {}
        for r in rows[hdr_i + 1:]:
            if not r or not isinstance(r[0], str) or "M" not in r[0]: continue
            try:
                out[r[0][:4] + "-" + r[0][5:7]] = float(r[j])
            except Exception:
                pass
        res[nm] = out
    # 지수(에너지·비에너지·전체 원자재)
    ws = wb["Monthly Indices"]
    rows = list(ws.iter_rows(values_only=True))
    for nm, col in {"wb_energy": "Energy", "wb_nonenergy": "Non-energy", "wb_metals": "Metals & Minerals", "wb_allcomm": "Total Index"}.items():
        out = {}
        j = None
        for r in rows[:15]:
            for k, c in enumerate(r or []):
                if isinstance(c, str) and c.strip().startswith(col) and j is None:
                    j = k
        if j is None: continue
        for r in rows:
            if not r or not isinstance(r[0], str) or "M" not in r[0]: continue
            try:
                out[r[0][:4] + "-" + r[0][5:7]] = float(r[j])
            except Exception:
                pass
        res[nm] = out
    return res


def shiller():
    import xlrd
    p = os.path.join(RAW, "_shiller.xls")
    b = curl(SHILLER_URL, binary=True)
    if b: open(p, "wb").write(b)
    sh = xlrd.open_workbook(p).sheet_by_name("Data")
    price, div, earn, cpi, gs10, cape = {}, {}, {}, {}, {}, {}
    for r in range(8, sh.nrows):
        d = sh.cell_value(r, 0)
        if not isinstance(d, float): continue
        y = int(d); m = int(round((d - y) * 100))
        if not 1 <= m <= 12: continue
        k = f"{y:04d}-{m:02d}"

        def g(c):
            v = sh.cell_value(r, c)
            return float(v) if isinstance(v, float) else None
        for dic, c in ((price, 1), (div, 2), (earn, 3), (cpi, 4), (gs10, 6), (cape, 12)):
            v = g(c)
            if v is not None: dic[k] = v
    return {"sh_price": price, "sh_div": div, "sh_earn": earn, "sh_cpi": cpi, "sh_gs10": gs10, "sh_cape": cape}


def main():
    only = sys.argv[1:]
    for n, s in YAHOO.items():
        if only and "yahoo" not in only: break
        d = yahoo(n, s)
        if d: save("y_" + n, d)   # 10-21 감사: 빈 응답이면 기존 파일 유지
        print("yahoo", n, len(d), min(d) if d else "-", flush=True)
    for i in FRED:
        if only and "fred" not in only: break
        d = fred(i)
        if d: save("f_" + i, d)
        print("fred", i, len(d), min(d) if d else "-", flush=True)
    for i in EOM:
        if only and "fred" not in only: break
        d = fred_eom(i)
        if d: save("e_" + i, d)
        print("fred eom", i, len(d), flush=True)
    try:
        for n, d in worldbank().items():
            save(n, d); print("wb", n, len(d), min(d) if d else "-", flush=True)
    except Exception as e:
        print("wb fail", repr(e)[:200])
    try:
        for n, d in shiller().items():
            save(n, d); print("shiller", n, len(d), min(d) if d else "-", flush=True)
    except Exception as e:
        print("shiller fail", repr(e)[:200])


if __name__ == "__main__":
    main()
