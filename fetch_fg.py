# -*- coding: utf-8 -*-
"""CNN 공포탐욕지수 (2026-11-01, 사용자: 'RSI+공포탐욕 조합'). CNN 은 최근 1년치만 줌(날짜 지정은 418 거절)
→ 사용자 파일(2011-01~2026-02) + 매주 받는 1년치를 data/daily/cnn_fg.csv 에 이어 붙여 쌓음(이미 있는 날은 CNN 값으로 덮음).
브라우저 User-Agent 없으면 거절됨. 빈 응답이면 저장 안 함.
py fetch_fg.py -> data/daily/cnn_fg.csv (date,value)
"""
import os, sys, json, csv, datetime, subprocess
B = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(B, "data", "daily", "cnn_fg.csv")
SEED = r"C:\Users\Chan\Desktop\DCA 매수 전략 데이터\나스닥_data_2011_2026\fear_greed_cnn.csv"
URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def read(p):
    if not os.path.exists(p): return {}
    with open(p, encoding="utf-8") as f:
        r = csv.reader(f); next(r, None)
        return {a: float(b) for a, b in r if b}


def main():
    rows = read(OUT) or read(SEED)
    t = subprocess.run(["curl", "-s", "-m", "30", "-A", UA, "-H", "Referer: https://edition.cnn.com/", URL], capture_output=True, text=True).stdout
    try:
        h = json.loads(t)["fear_and_greed_historical"]["data"]
    except Exception:
        print("fetch fail, kept", len(rows)); return 1
    new = {datetime.datetime.utcfromtimestamp(x["x"] / 1000).strftime("%Y-%m-%d"): round(float(x["y"]), 1) for x in h}
    rows.update(new)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date", "value"])
        for k in sorted(rows): w.writerow([k, rows[k]])
    print("ok", len(rows), min(rows), max(rows), "new", len(new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
