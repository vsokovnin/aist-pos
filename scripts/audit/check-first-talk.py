#!/usr/bin/env python3
"""Гейт: первый разговор согласован с каталогом задач и рубрикой.

Проверяет, что вопросы, привязанные к шагам задачи, ведут в ту же матрицу:
  · вопрос написан для существующей способности, варианты идут снизу вверх, уровни в 1–5;
  · шаги задачи существуют, и каждый вопрос привязан к существующему шагу;
  · спрашиваем ровно то, что задаче нужно для запуска, — ни лишнего, ни недостающего.

    python3 scripts/audit/check-first-talk.py [корень репозитория]
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else os.environ.get("AUDIT_ROOT", Path(__file__).resolve().parent.parent.parent))


def main():
    rubric = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    caps = set(re.findall(r"\n  - id: (\w+)\n    cluster: ", "\n" + rubric))
    jobs = json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))
    quick = json.loads((ROOT / "rubric" / "quickstart.json").read_text(encoding="utf-8"))
    steps = json.loads((ROOT / "rubric" / "task-steps.json").read_text(encoding="utf-8"))
    byid = {j["id"]: j for j in jobs["jobs"]}
    q = quick["questions"]
    bad = []

    for cap in q:
        if cap not in caps:
            bad.append("вопрос написан для неизвестной способности %s" % cap)
        lv = [o["level"] for o in q[cap]["options"]]
        if not lv or lv != sorted(lv) or any(not 1 <= l <= 5 for l in lv):
            bad.append("%s: варианты идут не снизу вверх или уровень вне 1–5" % cap)
        if not q[cap].get("ask"):
            bad.append("%s: нет текста вопроса" % cap)

    for tid, t in steps["tasks"].items():
        if tid not in byid:
            bad.append("шаги написаны для задачи %s, которой нет в каталоге" % tid)
            continue
        need = set(byid[tid]["needs"])
        asked = set()
        for a in t["asks"]:
            if not 1 <= a["step"] <= len(t["steps"]):
                bad.append("%s: вопрос привязан к шагу %s, а шагов %d"
                           % (tid, a["step"], len(t["steps"])))
            if a["cap"] not in q:
                bad.append("%s: для способности %s нет вариантов ответа" % (tid, a["cap"]))
            if a["cap"] not in need:
                bad.append("%s: спрашиваем про %s, а для запуска задаче она не нужна"
                           % (tid, a["cap"]))
            if not a.get("ask"):
                bad.append("%s: у вопроса к шагу %s нет текста" % (tid, a["step"]))
            asked.add(a["cap"])
        if need - asked:
            bad.append("%s: задаче нужны %s, а вопросов про них нет"
                       % (tid, ", ".join(sorted(need - asked))))

    if bad:
        print("первый разговор разошёлся с каталогом:")
        for b in bad:
            print("  ·", b)
        sys.exit(1)
    print("гейт: первый разговор — задач по шагам %d, вопросов %d, все ведут в матрицу"
          % (len(steps["tasks"]), sum(len(t["asks"]) for t in steps["tasks"].values())))


if __name__ == "__main__":
    main()
