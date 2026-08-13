#!/usr/bin/env python3
"""Сверка слепых дериваций с текущей матрицей -> очередь находок.

Правила (спек §4.2, уточнение: кандидат «не хватает» при поддержке >=2 из 3,
а не только 3 из 3 — двое независимых заслуживают разбора судьёй):
  missing: >=2 агентов вывели способность, в needs её нет
  extra:   в needs есть, не вывел ни один
  level:   в needs есть; преобладающий уровень агентов != уровню needs
  gap:     агент зафиксировал операцию вне каталога
Уровень агента по способности = max по его ячейкам этой способности.

Переменная окружения AUDIT_ROOT (если задана) подменяет корень для чтения
raw/needs и записи findings.json — используется изолированной фикстурной
проверкой, в проде не задаётся.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import inputs  # noqa: E402
from inputs import fail, load_needs  # noqa: E402

if os.environ.get("AUDIT_ROOT"):
    inputs.ROOT = Path(os.environ["AUDIT_ROOT"])
ROOT = inputs.ROOT

RAW = ROOT / "derivation" / "raw"


def agent_levels(runs, cap):
    out = []
    for r in runs:
        lv = [c["level"] for c in r["cells"] if c["cap_id"] == cap]
        if lv:
            out.append(max(lv))
    return out


def scenarios(runs, cap):
    return [c["failure_scenario"] for r in runs for c in r["cells"] if c["cap_id"] == cap]


def main():
    needs = load_needs()
    findings = []
    for job_id in sorted(needs):
        files = sorted(RAW.glob("%s-*.json" % job_id))
        if len(files) != 3:
            fail("у задачи %s не 3 деривации, а %d" % (job_id, len(files)))
        runs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
        derived = {c["cap_id"] for r in runs for c in r["cells"]}
        for cap in sorted(derived - set(needs[job_id])):
            lv = agent_levels(runs, cap)
            if len(lv) >= 2:
                findings.append(dict(job_id=job_id, cap_id=cap, cls="missing",
                                     votes=len(lv), levels_seen=lv, needs_level=None,
                                     scenarios=scenarios(runs, cap)))
        for cap in sorted(set(needs[job_id]) - derived):
            findings.append(dict(job_id=job_id, cap_id=cap, cls="extra",
                                 votes=0, levels_seen=[], needs_level=needs[job_id][cap],
                                 scenarios=[]))
        for cap in sorted(set(needs[job_id]) & derived):
            lv = agent_levels(runs, cap)
            top, cnt = Counter(lv).most_common(1)[0]
            if cnt >= 2 and top != needs[job_id][cap]:
                findings.append(dict(job_id=job_id, cap_id=cap, cls="level",
                                     votes=len(lv), levels_seen=lv,
                                     needs_level=needs[job_id][cap],
                                     scenarios=scenarios(runs, cap)))
        for r in runs:
            for g in r["gaps"]:
                findings.append(dict(job_id=job_id, cap_id=None, cls="gap",
                                     votes=1, levels_seen=[], needs_level=None,
                                     scenarios=[g["failure_scenario"]],
                                     detail="%s: %s" % (g["operation"], g["missing"])))
    for i, f in enumerate(findings, 1):
        f.update(n=i, verdict=None, rationale=None, decision=None)
    out = ROOT / "derivation" / "findings.json"
    out.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    by = Counter(f["cls"] for f in findings)
    print("находок %d: %s" % (len(findings), dict(by)))


if __name__ == "__main__":
    main()
