# -*- coding: utf-8 -*-
"""감시(watch.py) 지킴이 (2026-11-06): 11-06 06시쯤 watch.py 가 기록 없이 사라짐(파이썬 오류 아님 = 판다스 내부 충돌 추정).
꺼지면 30초 뒤 다시 켠다. 이 창을 닫으면 둘 다 끝남(일부러 끄는 방법).
py watch_keep.py"""
import os, sys, time, subprocess, datetime
B = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(B, "logs", "watch.log")
while True:
    t0 = time.time()
    with open(os.path.join(B, "logs", "watch_err.txt"), "a", encoding="utf-8") as err:      # 충돌하면 어디서 죽었는지 여기에
        r = subprocess.run([sys.executable, "-X", "faulthandler", os.path.join(B, "watch.py")], cwd=B, stderr=err)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%m-%d %H:%M} watch exit {r.returncode} after {int(time.time() - t0)}s, restart\n")
    time.sleep(30)
