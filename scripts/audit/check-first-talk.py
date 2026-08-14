#!/usr/bin/env python3
"""Гейт: первый разговор согласован с каталогом задач и рубрикой.

Первый разговор спрашивает про рабочие задачи, а не про способности, и из каждого ответа
вынимает сразу несколько уровней. Гейт следит, чтобы эта вытяжка не разошлась с матрицей:

  · у вопроса есть свой идентификатор, и он не повторяется;
  · вопрос описывает рабочую сцену — слов «агент», «ИИ», «нейросеть», «бот» в нём нет;
  · вопрос про задачу каталога ставит ровно её порог входа — ни лишних способностей, ни забытых;
  · вопрос без задачи ставит только то, что живёт во втором круге или в опоре;
  · по каждой способности уровни по вариантам не убывают, и все лежат в 1–5;
  · вопросы вместе с выводимыми правилом способностями покрывают всю матрицу.

    python3 scripts/audit/check-first-talk.py [корень репозитория]
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else os.environ.get("AUDIT_ROOT", Path(__file__).resolve().parent.parent.parent))

# слова, которые предполагают уже настроенную систему: в тексте вопроса их быть не должно
AGENT_WORDS = re.compile(r"(?:^|[^А-Яа-яA-Za-zЁё])(?:агент\w*|ИИ|нейросет\w*|бот\w*)(?![А-Яа-яA-Za-zЁё])")
RULES = ["render_rule", "conflict_rule", "answer_format", "question_rule", "assumption_rule"]


def main():
    rubric = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    caps = set(re.findall(r"\n  - id: (\w+)\n    cluster: ", "\n" + rubric))
    jobs = json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))
    quick = json.loads((ROOT / "rubric" / "quickstart.json").read_text(encoding="utf-8"))
    byid = {j["id"]: j for j in jobs["jobs"]}
    entry_caps = {c for j in jobs["jobs"] for c in j["needs"]}
    # то, что можно спрашивать вопросом без привязки к задаче: второй круг и опора под всеми
    beyond_entry = ({c for j in jobs["jobs"] for c in (j.get("hardens") or {})}
                    | set((jobs.get("hygiene") or {}).get("caps") or []))
    bad = []
    measured = set()
    seen_ids = set()

    for key in RULES:
        if not quick.get(key):
            bad.append("не записано правило %s" % key)
    if not quick.get("page"):
        bad.append("нет текстов страницы первого разговора — собирать её не из чего")
    derived = set(quick.get("derived") or {})
    for c in derived:
        if c not in caps:
            bad.append("правилом выводится способность %s, которой нет в рубрике" % c)

    for q in quick["questions"]:
        qid = q.get("id")
        if not qid:
            bad.append("у вопроса нет идентификатора")
            continue
        if qid in seen_ids:
            bad.append("идентификатор вопроса %s встречается дважды" % qid)
        seen_ids.add(qid)
        ask = q.get("ask") or ""
        if not ask:
            bad.append("%s: нет текста вопроса" % qid)
        hit = AGENT_WORDS.search(ask)
        if hit:
            bad.append("%s: в тексте вопроса «%s» — вопрос должен описывать рабочую сцену, "
                       "а не предполагать настроенную систему" % (qid, hit.group().strip()))
        opts = q.get("options") or []
        if len(opts) < 2:
            bad.append("%s: вариантов ответа меньше двух" % qid)
        seen = {}
        for i, o in enumerate(opts, 1):
            if not o.get("t"):
                bad.append("%s: у варианта %d нет текста" % (qid, i))
            if "short" in o:
                bad.append("%s: у варианта %d есть сокращённый ярлык — человек не должен видеть "
                           "сокращённых формулировок нигде" % (qid, i))
            for cap, lvl in (o.get("sets") or {}).items():
                if cap not in caps:
                    bad.append("%s: вариант %d ставит уровень неизвестной способности %s"
                               % (qid, i, cap))
                    continue
                if not isinstance(lvl, int) or not 1 <= lvl <= 5:
                    bad.append("%s: вариант %d ставит %s уровень %r вне 1–5" % (qid, i, cap, lvl))
                if cap in seen and lvl < seen[cap]:
                    bad.append("%s: у способности %s уровень падает от варианта %d к %d — "
                               "варианты должны идти снизу вверх" % (qid, cap, i - 1, i))
                seen[cap] = lvl
                measured.add(cap)
        if cap_in_derived := (set(seen) & derived):
            bad.append("%s: способность %s выводится правилом, спрашивать её вопросом нельзя"
                       % (qid, ", ".join(sorted(cap_in_derived))))

        jid = q.get("job")
        if jid is None:
            outside = set(seen) - beyond_entry
            if outside:
                bad.append("%s: вопрос не привязан к задаче, а ставит уровни способностям, "
                           "которых нет ни во втором круге, ни в опоре: %s"
                           % (qid, ", ".join(sorted(outside))))
            continue
        if jid not in byid:
            bad.append("%s: вопрос привязан к задаче, которой нет в каталоге" % qid)
            continue
        need = set(byid[jid]["needs"])
        extra = set(seen) - need
        missing = need - set(seen)
        if extra:
            bad.append("%s: вопрос ставит уровни способностям, которых задаче для запуска "
                       "не нужно: %s" % (qid, ", ".join(sorted(extra))))
        if missing:
            bad.append("%s: задаче нужны %s, а варианты ответа их не ставят"
                       % (qid, ", ".join(sorted(missing))))

    uncovered = entry_caps - measured
    if uncovered:
        bad.append("вопросы не меряют способности, нужные другим задачам: %s"
                   % ", ".join(sorted(uncovered)))
    blind = caps - measured - derived
    if blind:
        bad.append("матрица не заполнится: способности %s ни один вопрос не меряет и ни одно "
                   "правило не выводит" % ", ".join(sorted(blind)))

    if bad:
        print("первый разговор разошёлся с каталогом:")
        for b in bad:
            print("  ·", b)
        sys.exit(1)

    n_once = sum(1 for c in measured
                 if sum(1 for q in quick["questions"]
                        if c in {k for o in q["options"] for k in (o.get("sets") or {})}) == 1)
    print("гейт: первый разговор — вопросов %d, измеряется способностей %d, выводится правилом %d, "
          "матрица закрыта на %d из %d (без перепроверки: %d)"
          % (len(quick["questions"]), len(measured), len(derived),
             len(measured | derived), len(caps), n_once))


if __name__ == "__main__":
    main()
