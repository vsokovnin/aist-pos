#!/usr/bin/env python3
"""Применяет решения Виктора из findings.json к rubric/job-sets.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail  # noqa: E402


def main():
    fpath = ROOT / "derivation" / "findings.json"
    findings = json.loads(fpath.read_text(encoding="utf-8"))
    undecided = [f["n"] for f in findings if f["verdict"] == "CONFIRMED" and not f["decision"]]
    if undecided:
        fail("нет решения Виктора по находкам: %s" % undecided)
    jpath = ROOT / "rubric" / "job-sets.json"
    data = json.loads(jpath.read_text(encoding="utf-8"))
    jobs = {j["id"]: j for j in data["jobs"]}
    changed = 0
    for f in findings:
        if not f["decision"] or f["decision"]["take"] != "accept":
            continue
        needs = jobs[f["job_id"]]["needs"]
        if f["cls"] == "missing":
            needs[f["cap_id"]] = f["decision"].get("level") or max(f["levels_seen"])
        elif f["cls"] == "extra":
            needs.pop(f["cap_id"], None)
        elif f["cls"] == "level":
            needs[f["cap_id"]] = f["decision"]["level"]
        elif f["cls"] == "gap":
            continue  # gap меняет состав модели — руками, вне этого скрипта
        changed += 1
    jpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("применено решений: %d" % changed)


if __name__ == "__main__":
    main()
