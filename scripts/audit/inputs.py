#!/usr/bin/env python3
"""Входы аудита: задачи без needs, текущая матрица, каталог способностей.

Единственный парсер входов — merge/certify/workflow берут данные отсюда,
чтобы правила чтения рубрики не разъехались по файлам.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def _jobs_raw():
    return json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))["jobs"]


def load_jobs():
    """Задачи для слепой деривации — поле needs отрезано намеренно."""
    jobs = [{k: j[k] for k in ("id", "title", "short", "promise")} for j in _jobs_raw()]
    if not jobs:
        fail("каталог задач пуст")
    return jobs


def load_needs():
    return {j["id"]: dict(j["needs"]) for j in _jobs_raw()}


def load_catalog():
    text = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    declared = int(re.search(r"\n  capabilities_count: (\d+)", text).group(1))
    caps = []
    for block in re.split(r"\n  - id: ", "\n" + text.partition("capabilities:")[2])[1:]:
        cid = block.split("\n", 1)[0].strip()
        title = re.search(r'\n    title: "(.*?)"', block)
        levels = dict(re.findall(r'^      (L[1-5]): "(.*)"$', block, re.M))
        if not (title and len(levels) == 5):
            fail("способность %s неполна (title или не 5 уровней)" % cid)
        caps.append({"id": cid, "title": title.group(1),
                     "levels": {i: levels["L%d" % i] for i in range(1, 6)}})
    if len(caps) != declared:
        fail("способностей %d, meta обещает %d" % (len(caps), declared))
    return caps


if __name__ == "__main__":
    jobs, needs, cat = load_jobs(), load_needs(), load_catalog()
    ids = {c["id"] for c in cat}
    for j, nn in needs.items():
        for cap in nn:
            if cap not in ids:
                fail("в needs задачи %s способность %s, которой нет в рубрике" % (j, cap))
    if any("needs" in j for j in jobs):
        fail("needs просочился в слепые входы")
    print("%d задач · %d способностей · матрица согласована" % (len(jobs), len(cat)))
