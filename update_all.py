# -*- coding: utf-8 -*-
"""매주 갱신 (2026-10-21, 사용자: '매주 자동 갱신'). 자료 받기 → 월·주 패널 → 신호판·검증판 생성.
게시(claude.ai 링크 유지)는 이 스크립트가 아니라 예약된 Claude 작업이 board.html·history.html 을 올림.
py update_all.py  → logs/update.txt (콘솔은 ASCII 만)
"""
import os, sys, subprocess, datetime
B = os.path.dirname(os.path.abspath(__file__))
STEPS = [["fetch.py"], ["fetch_daily.py"], ["fetch_fx2.py"], ["panel.py"], ["weekly.py"], ["evolve.py"], ["build_history.py"], ["wk_board.py"]]
log = open(os.path.join(B, "logs", "update.txt"), "w", encoding="utf-8")
log.write(f"start {datetime.datetime.now():%Y-%m-%d %H:%M}\n")
ok = True
for st in STEPS:
    r = subprocess.run([sys.executable] + st, cwd=B, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    log.write(f"\n== {st[0]} exit {r.returncode}\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}\n"); log.flush()
    if r.returncode != 0:
        ok = False; print("FAIL", st[0]); break
    print("ok", st[0])
# 캐시(백분위) 지우기는 panel.py 가 새로 만들 때 자동(mtime 비교)
log.write(f"\nend {datetime.datetime.now():%Y-%m-%d %H:%M} {'OK' if ok else 'FAIL'}\n"); log.close()
print("DONE" if ok else "FAILED")
sys.exit(0 if ok else 1)
