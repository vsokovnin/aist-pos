#!/usr/bin/env python3
"""Сборщик args для judge-workflow: находки без вердиктов, словари задач и каталога.

Готовит аргументы для Workflow судей: находки, обещания задач и уровни способностей.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import inputs
from inputs import fail, load_jobs, load_catalog

# AUDIT_ROOT подменяет корень для чтения findings, но job-sets и rubric читаются
# всегда из основного репо (настоящей матрицы)
AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "")) if os.environ.get("AUDIT_ROOT") else None
ROOT = Path(__file__).resolve().parent.parent.parent  # основной репо


def main():
    parser = argparse.ArgumentParser(description="Подготовить args для judge-workflow")
    parser.add_argument("--limit", type=int, default=None, help="Взять первые N неотсуженных находок")
    args = parser.parse_args()

    findings_root = AUDIT_ROOT if AUDIT_ROOT else ROOT
    findings_path = findings_root / "derivation" / "findings.json"
    if not findings_path.exists():
        fail(f"findings.json не найден: {findings_path}")

    try:
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"findings.json невалидный JSON: {e}")

    # Отобрать находки без вердикта
    unverdict = [f for f in findings if f.get("verdict") is None]
    if args.limit is not None:
        unverdict = unverdict[:args.limit]

    if not unverdict:
        print(json.dumps({"findings": [], "jobs": {}, "catalog": {}}, ensure_ascii=False, indent=2))
        return

    # Загрузить задачи и каталог
    jobs_list = load_jobs()
    catalog_list = load_catalog()

    # Преобразовать в словари по id
    jobs_dict = {j["id"]: {k: j[k] for k in ("title", "short", "promise")} for j in jobs_list}
    catalog_dict = {c["id"]: {"title": c["title"], "levels": c["levels"]} for c in catalog_list}

    output = {
        "findings": unverdict,
        "jobs": jobs_dict,
        "catalog": catalog_dict,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
