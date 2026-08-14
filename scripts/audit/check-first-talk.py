#!/usr/bin/env python3
"""Гейт: первый разговор согласован с каталогом задач и рубрикой.

Первый разговор спрашивает про рабочие задачи, а не про способности, и из каждого ответа
вынимает сразу несколько уровней. Гейт следит, чтобы эта вытяжка не разошлась с матрицей:

  · вопрос привязан к существующей задаче каталога;
  · способности, которые ставит вариант ответа, существуют в рубрике;
  · набор способностей вопроса совпадает с порогом входа его задачи — ни лишних, ни забытых;
  · по каждой способности уровни по вариантам не убывают, и все лежат в 1–5;
  · шесть вопросов вместе покрывают все способности, стоящие в пороге входа хотя бы одной задачи.

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
    byid = {j["id"]: j for j in jobs["jobs"]}
    entry_caps = {c for j in jobs["jobs"] for c in j["needs"]}
    bad = []
    measured = set()

    if not quick.get("conflict_rule"):
        bad.append("не записано правило на случай, когда ответы про одну способность разошлись")

    for q in quick["questions"]:
        jid = q.get("job")
        if jid not in byid:
            bad.append("вопрос привязан к задаче %s, которой нет в каталоге" % jid)
            continue
        if not q.get("ask"):
            bad.append("%s: нет текста вопроса" % jid)
        opts = q.get("options") or []
        if len(opts) < 2:
            bad.append("%s: вариантов ответа меньше двух" % jid)
        seen = {}
        for i, o in enumerate(opts, 1):
            if not o.get("t"):
                bad.append("%s: у варианта %d нет текста" % (jid, i))
            for cap, lvl in (o.get("sets") or {}).items():
                if cap not in caps:
                    bad.append("%s: вариант %d ставит уровень неизвестной способности %s"
                               % (jid, i, cap))
                    continue
                if not isinstance(lvl, int) or not 1 <= lvl <= 5:
                    bad.append("%s: вариант %d ставит %s уровень %r вне 1–5" % (jid, i, cap, lvl))
                if cap in seen and lvl < seen[cap]:
                    bad.append("%s: у способности %s уровень падает от варианта %d к %d — "
                               "варианты должны идти снизу вверх" % (jid, cap, i - 1, i))
                seen[cap] = lvl
                measured.add(cap)
        need = set(byid[jid]["needs"])
        extra = set(seen) - need
        missing = need - set(seen)
        if extra:
            bad.append("%s: вопрос ставит уровни способностям, которых задаче для запуска "
                       "не нужно: %s" % (jid, ", ".join(sorted(extra))))
        if missing:
            bad.append("%s: задаче нужны %s, а варианты ответа их не ставят"
                       % (jid, ", ".join(sorted(missing))))

    uncovered = entry_caps - measured
    if uncovered:
        bad.append("вопросы не меряют способности, нужные другим задачам: %s"
                   % ", ".join(sorted(uncovered)))

    if bad:
        print("первый разговор разошёлся с каталогом:")
        for b in bad:
            print("  ·", b)
        sys.exit(1)

    n_once = sum(1 for c in measured
                 if sum(1 for q in quick["questions"]
                        if c in {k for o in q["options"] for k in (o.get("sets") or {})}) == 1)
    print("гейт: первый разговор — вопросов %d, меряют способностей %d из %d порога входа "
          "(без перепроверки: %d)"
          % (len(quick["questions"]), len(measured), len(entry_caps), n_once))


if __name__ == "__main__":
    main()
