#!/usr/bin/env python3
"""Применяет ярусы (вход / надёжность / гигиена) к каталогу задач.

Решение Виктора 2026-08-13 (спек §4.6):
  entry      -> needs задачи (порог входа: первая ценность)
  reliability-> hardens задачи (новое поле: чем задача взрослеет)
  hygiene    -> top-level hygiene (слой системы; из needs задач вычищается)

Дыры каталога (gap) сюда не идут — они не способности; выносятся отдельно
в derivation/catalog-gaps.json решением Виктора о расширении модели.
Находки класса extra не применяются автоматически — только решением Виктора.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail  # noqa: E402

HYGIENE_WHY = ("защищает всё построенное сразу, а не отдельную задачу: "
               "тот же сценарий отказа воспроизводится при любой работе с файлами и данными")


def main():
    fpath = ROOT / "derivation" / "findings.json"
    jpath = ROOT / "rubric" / "job-sets.json"
    findings = json.loads(fpath.read_text(encoding="utf-8"))
    data = json.loads(jpath.read_text(encoding="utf-8"))
    jobs = {j["id"]: j for j in data["jobs"]}

    conf = [x for x in findings if x["verdict"] == "CONFIRMED" and x.get("tier")]
    hygiene_caps = sorted({x["cap_id"] for x in conf
                           if x["tier"] == "hygiene" and x["cap_id"]})
    if not hygiene_caps:
        fail("гигиенических способностей не нашлось — типизация не применена?")

    log = defaultdict(list)

    # 1. Порог входа -> needs
    for x in conf:
        if x["tier"] != "entry" or not x["cap_id"]:
            continue
        job = jobs[x["job_id"]]
        if x["cls"] == "missing":
            lvl = max(x["levels_seen"])
            job["needs"][x["cap_id"]] = lvl
            log["entry+"].append("%s +%s%d" % (x["job_id"], x["cap_id"], lvl))
        elif x["cls"] == "level":
            lvl = Counter(x["levels_seen"]).most_common(1)[0][0]
            was = job["needs"].get(x["cap_id"])
            job["needs"][x["cap_id"]] = lvl
            log["entry~"].append("%s %s %s→%d" % (x["job_id"], x["cap_id"], was, lvl))

    # 2. Надёжность -> hardens
    for x in conf:
        if x["tier"] != "reliability" or not x["cap_id"] or x["cls"] == "extra":
            continue
        job = jobs[x["job_id"]]
        lvl = (max(x["levels_seen"]) if x["cls"] == "missing"
               else Counter(x["levels_seen"]).most_common(1)[0][0])
        job.setdefault("hardens", {})[x["cap_id"]] = lvl
        log["hardens"].append("%s %s%d" % (x["job_id"], x["cap_id"], lvl))

    # 3. Гигиена -> слой системы, из needs и hardens вычищается
    for job in data["jobs"]:
        for cap in hygiene_caps:
            if job["needs"].pop(cap, None) is not None:
                log["hyg-needs"].append("%s -%s" % (job["id"], cap))
            if job.get("hardens", {}).pop(cap, None) is not None:
                log["hyg-hardens"].append("%s -%s" % (job["id"], cap))
    data["hygiene"] = {"level": 3, "caps": hygiene_caps, "why": HYGIENE_WHY}

    # порядок ключей задачи: hardens сразу после needs
    for job in data["jobs"]:
        if "hardens" in job:
            h = job.pop("hardens")
            job["hardens"] = dict(sorted(h.items()))
        job["needs"] = dict(sorted(job["needs"].items()))

    jpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("гигиена (слой системы, уровень 3): %s" % ", ".join(hygiene_caps))
    for k in ("entry+", "entry~", "hyg-needs", "hyg-hardens"):
        if log[k]:
            print("%-11s %s" % (k, "; ".join(log[k])))
    print("hardens     %d ячеек в %d задачах"
          % (len(log["hardens"]), sum(1 for j in data["jobs"] if j.get("hardens"))))
    print("\nразмер задач (needs / hardens):")
    for j in data["jobs"]:
        print("  %-10s %d / %d" % (j["id"], len(j["needs"]), len(j.get("hardens", {}))))


if __name__ == "__main__":
    main()
