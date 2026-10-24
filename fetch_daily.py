# -*- coding: utf-8 -*-
"""주 단위 판정용 일별 자료 (2026-10-21). 월 자료(fetch.py)와 따로 data/daily/ 에 저장.
야후 일별 종가(수정주가) + FRED 일별·주별 계열.
py fetch_daily.py -> data/daily/<이름>.csv (date,value  date=YYYY-MM-DD)
"""
import csv, io, json, os, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(B, "data", "daily")
os.makedirs(OUT, exist_ok=True)
from fetch import curl, YAHOO

FRED_D = ["DGS2", "DGS10", "DGS30", "DTB3", "DFF", "BAA10Y", "VIXCLS", "DCOILWTICO", "DEXKOUS", "DEXJPUS", "ICSA", "NFCI", "DFII10"]


def save(name, rows):
    with open(os.path.join(OUT, name + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date", "value"])
        for k in sorted(rows): w.writerow([k, rows[k]])


def yahoo_d(sym):
    from urllib.parse import quote
    t = curl(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym)}?period1=-2208988800&period2=9999999999&interval=1d&includeAdjustedClose=true")
    out = {}
    try:
        r = json.loads(t)["chart"]["result"][0]
    except Exception:
        return out
    ind = r["indicators"]; off = (r.get("meta") or {}).get("gmtoffset") or 0
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    for ts, v in zip(r.get("timestamp") or [], adj):
        if v is None: continue
        out[(datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=ts + off)).strftime("%Y-%m-%d")] = v
    return out


def fred_d(i):
    t = curl(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", ua=False)
    out = {}
    for r in csv.DictReader(io.StringIO(t)):
        v = r.get(i)
        if v in (None, "", "."): continue
        out[r["observation_date"]] = float(v)
    return out


if __name__ == "__main__":
    for n, s in YAHOO.items():
        d = yahoo_d(s)
        if d: save("y_" + n, d)
        print("yahoo", n, len(d), min(d) if d else "-", flush=True)
    for i in FRED_D:
        d = fred_d(i)
        if d: save("f_" + i, d)
        print("fred", i, len(d), min(d) if d else "-", flush=True)
