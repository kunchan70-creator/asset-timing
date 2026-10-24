# -*- coding: utf-8 -*-
"""환율 조사용 한국은행 ECOS 자료(키 불필요 sample, 10건씩) — 경상수지·상품수지(월), 기준금리(월). 2026-10-21"""
import json, time, urllib.request, csv, os, sys
sys.stdout.reconfigure(encoding="utf-8")
B = os.path.dirname(os.path.abspath(__file__))
U = "https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/"
def get(u):
    for _ in range(3):
        try: return json.loads(urllib.request.urlopen(u, timeout=30).read().decode("utf-8"))
        except Exception: time.sleep(2)
    return {}
def fetch(stat, it, frm, to="202612"):
    out = {}; s = 1
    while True:
        r = get(f"{U}{s}/{s+9}/{stat}/M/{frm}/{to}/{it}/").get("StatisticSearch", {}).get("row") or []
        if not r: break
        for x in r:
            v = x.get("DATA_VALUE")
            if v not in (None, ""): out[x["TIME"][:4] + "-" + x["TIME"][4:6]] = float(v)
        if len(r) < 10: break
        s += 10; time.sleep(0.12)
    return out
def save(n, d):
    with open(os.path.join(B, "data", "raw", n + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date", "value"]); [w.writerow([k, d[k]]) for k in sorted(d)]
if __name__ == "__main__":
    for n, (st, it, frm) in {"kr_ca": ("301Y013", "000000", "198001"), "kr_goods": ("301Y013", "100000", "198001"),
                             "kr_base": ("722Y001", "0101000", "199905")}.items():
        d = fetch(st, it, frm); save("ecos_" + n, d); print(n, len(d), min(d) if d else "-", max(d) if d else "-", flush=True)
