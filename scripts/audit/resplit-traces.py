#!/usr/bin/env python3
"""Переразложение канонических трасс по ярусам после паса Б.

Ячейка, понижённая из порога в надёжность, не выбрасывается: она уезжает
в hardens_cells вместе со своим сценарием отказа. Ячейки надёжности, добавленные
атаками, берут обоснование из самой атаки (claim + evidence).

Инвариант после прогона: cells ≡ needs, hardens_cells ≡ hardens (по составу).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail, load_needs  # noqa: E402


def main():
    needs = load_needs()
    data = json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))
    hardens = {j["id"]: j.get("hardens", {}) for j in data["jobs"]}
    atk = json.loads((ROOT / "derivation" / "attacks.json").read_text(encoding="utf-8"))
    by_pair = {}
    for a in atk:
        if a.get("verdict") == "UPHELD" and a["kind"] == "hardens":
            by_pair[(a["job_id"], a["cap_id"])] = a

    moved = added = 0
    for job_id, nn in sorted(needs.items()):
        p = ROOT / "derivation" / ("%s.json" % job_id)
        t = json.loads(p.read_text(encoding="utf-8"))
        cells, hcells = [], list(t.get("hardens_cells", []))
        seen_h = {c["cap_id"] for c in hcells}
        for c in t["cells"]:
            if c["cap_id"] in nn:
                cells.append(c)
            elif c["cap_id"] in hardens[job_id] and c["cap_id"] not in seen_h:
                hcells.append({**c, "level": hardens[job_id][c["cap_id"]],
                               "source": "понижено из порога входа пасом Б"})
                seen_h.add(c["cap_id"])
                moved += 1
        for cap, lvl in sorted(hardens[job_id].items()):
            if cap in seen_h:
                continue
            a = by_pair.get((job_id, cap))
            hcells.append({
                "operation": "(ярус надёжности)", "cap_id": cap, "level": lvl,
                "failure_scenario": (a["evidence"] if a else
                                     "перенесено решением о ярусах; сценарий — в derivation/findings.json"),
                "source": ("атака паса Б n%d: %s" % (a["id"], a["claim"])) if a else "типизация находок",
            })
            seen_h.add(cap)
            added += 1
        got = {}
        for c in cells:
            got[c["cap_id"]] = max(got.get(c["cap_id"], 0), c["level"])
        if got != nn:
            fail("%s: после переразложения cells %s != needs %s" % (job_id, got, nn))
        t["cells"], t["hardens_cells"] = cells, hcells
        p.write_text(json.dumps(t, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("перенесено из порога в надёжность: %d ячеек; заведено новых ячеек надёжности: %d" % (moved, added))


if __name__ == "__main__":
    main()
