#!/usr/bin/env python3
"""Применяет устоявшие атаки паса Б к каталогу задач.

Решение Виктора 2026-08-14: приняты пять принципов (записанный порядок, база
контактов, память, вводные — зрелость; форма результата — вход только там, где
артефакт уходит наружу). Задачи assistant и quarter ВЫНЕСЕНЫ из применения:
у них порог падал до двух способностей, разбираются отдельным заходом.

Понижение из порога = перенос в hardens тем же уровнем (способность не исчезает).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail  # noqa: E402

EXCLUDED = {"assistant", "quarter"}  # решение Виктора: отдельный разбор


def levels_from_claim(claim, cap_id):
    """Уровень, названный атакующим: 'connectors 4', 'capture:4', 'doc_source ур.3'."""
    lvl = r"(?:уров\w*|ур\.?)\s*([1-5])"
    pats = [cap_id + r"\s*[:\s]\s*([1-5])\b", cap_id + r".{0,30}?" + lvl, lvl]
    for p in pats:
        m = re.search(p, claim)
        if m:
            return int(m.group(1))
    # «остаётся на N» — атака требует следующую ступень над названной
    m = re.search(r"остаётся на ([1-4])", claim)
    if m:
        return int(m.group(1)) + 1
    return None


def main():
    apath = ROOT / "derivation" / "attacks.json"
    jpath = ROOT / "rubric" / "job-sets.json"
    atk = json.loads(apath.read_text(encoding="utf-8"))
    data = json.loads(jpath.read_text(encoding="utf-8"))
    jobs = {j["id"]: j for j in data["jobs"]}
    up = [a for a in atk if a.get("verdict") == "UPHELD"]

    demoted, added, deferred = [], [], []
    for a in up:
        job = jobs[a["job_id"]]
        if a["job_id"] in EXCLUDED:
            deferred.append("%s/%s (%s)" % (a["job_id"], a["cap_id"], a["kind"]))
            a["decision"] = {"take": "defer", "note": "решение Виктора: задача вынесена на отдельный разбор"}
            continue
        if a["kind"] in ("extra", "too_high"):
            lvl = job["needs"].pop(a["cap_id"], None)
            if lvl is not None:
                job.setdefault("hardens", {})[a["cap_id"]] = lvl
                demoted.append("%s %s→надёжность(ур%d)" % (a["job_id"], a["cap_id"], lvl))
            a["decision"] = {"take": "accept", "note": "принцип принят Виктором: понижено в ярус надёжности"}
        elif a["kind"] == "hardens":
            lvl = levels_from_claim(a["claim"], a["cap_id"])
            if lvl is None:
                fail("не разобрал уровень в атаке %d (%s/%s)" % (a["id"], a["job_id"], a["cap_id"]))
            cur = job.get("hardens", {}).get(a["cap_id"])
            if cur is None or lvl > cur:
                job.setdefault("hardens", {})[a["cap_id"]] = lvl
                added.append("%s +%s%d" % (a["job_id"], a["cap_id"], lvl))
            a["decision"] = {"take": "accept", "note": "принято: ячейка яруса надёжности"}

    for job in data["jobs"]:
        job["needs"] = dict(sorted(job["needs"].items()))
        if job.get("hardens"):
            job["hardens"] = dict(sorted(job["hardens"].items()))

    jpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apath.write_text(json.dumps(atk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("понижено в надёжность (%d): %s" % (len(demoted), "; ".join(demoted)))
    print("\nдобавлено в надёжность (%d): %s" % (len(added), "; ".join(added)))
    print("\nотложено по решению Виктора (%d): %s" % (len(deferred), "; ".join(deferred)))
    print("\nразмер задач (порог / надёжность):")
    for j in data["jobs"]:
        mark = "  ← отложена" if j["id"] in EXCLUDED else ""
        print("  %-10s %d / %d%s" % (j["id"], len(j["needs"]), len(j.get("hardens", {})), mark))


if __name__ == "__main__":
    main()
