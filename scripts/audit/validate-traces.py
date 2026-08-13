#!/usr/bin/env python3
"""Каноническая трасса согласована с матрицей: cells ≡ needs, сценарии непусты."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail, load_needs  # noqa: E402

for job_id, nn in sorted(load_needs().items()):
    p = ROOT / "derivation" / ("%s.json" % job_id)
    if not p.exists():
        fail("нет канонической трассы %s" % job_id)
    t = json.loads(p.read_text(encoding="utf-8"))
    got = {}
    for c in t["cells"]:
        got[c["cap_id"]] = max(got.get(c["cap_id"], 0), c["level"])
        if len(c["failure_scenario"]) < 40:
            fail("%s/%s: сценарий отказа пуст или куцый" % (job_id, c["cap_id"]))
        opnames = {o["name"] for o in t["operations"]}
        if c["operation"] not in opnames:
            fail("%s/%s: ячейка ссылается на несуществующую операцию" % (job_id, c["cap_id"]))
    if got != nn:
        fail("%s: трасса %s != needs %s" % (job_id, got, nn))
print("трассы согласованы с матрицей: %d задач" % len(load_needs()))
