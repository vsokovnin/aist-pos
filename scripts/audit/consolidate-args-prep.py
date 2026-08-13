#!/usr/bin/env python3
"""Сборщик args для consolidate-workflow: задачи, needs, 3 деривации и номера accepted decisions.

Готовит аргументы для Workflow консолидации трасс: для каждой задачи собирает
три независимых деривации, финальную матрицу needs и номера находок с решением "принять".
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import inputs
from inputs import fail, load_jobs, load_needs

# AUDIT_ROOT подменяет корень для чтения findings и raw, как в merge.py
AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "")) if os.environ.get("AUDIT_ROOT") else None
ROOT = Path(__file__).resolve().parent.parent.parent


def main():
    parser = argparse.ArgumentParser(description="Подготовить args для consolidate-workflow")
    parser.add_argument("--jobs", type=str, default=None, help="Фильтр задач (comma-separated)")
    args = parser.parse_args()

    # Выбрать корень для чтения findings и raw
    findings_root = AUDIT_ROOT if AUDIT_ROOT else ROOT
    findings_path = findings_root / "derivation" / "findings.json"

    # Загрузить findings; если файла нет, начинаем с пустого списка
    try:
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        findings = []
    except json.JSONDecodeError as e:
        fail(f"findings.json невалидный JSON: {e}")

    # Загрузить задачи и needs
    jobs_list = load_jobs()
    needs_dict = load_needs()

    # Фильтр по --jobs
    jobs_filter = set(args.jobs.split(",")) if args.jobs else None
    if jobs_filter:
        jobs_list = [j for j in jobs_list if j["id"] in jobs_filter]
        # Проверить, что все запрошенные id'ы найдены
        found_ids = {j["id"] for j in jobs_list}
        missing_ids = jobs_filter - found_ids
        if missing_ids:
            fail(f"задачи не найдены: {', '.join(sorted(missing_ids))}")

    # Собрать результат
    output_jobs = []
    for job in jobs_list:
        job_id = job["id"]

        # Загрузить 3 деривации
        raw_dir = findings_root / "derivation" / "raw"
        raw_files = sorted(raw_dir.glob(f"{job_id}-*.json"))
        if len(raw_files) != 3:
            fail(f"у задачи {job_id} не 3 деривации, а {len(raw_files)}")

        runs = [json.loads(f.read_text(encoding="utf-8")) for f in raw_files]

        # Собрать номера decisions с take=="accept" для этого job
        decisions = [
            f["n"] for f in findings
            if f.get("job_id") == job_id and (f.get("decision") or {}).get("take") == "accept"
        ]

        output_jobs.append({
            "job": job_id,
            "title": job["title"],
            "needs": needs_dict[job_id],
            "runs": runs,
            "decisions": decisions,
        })

    output = {"jobs": output_jobs}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
