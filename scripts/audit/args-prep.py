#!/usr/bin/env python3
"""Подготовка аргументов для Workflow: фильтрованные jobs + весь catalog."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inputs import load_jobs, load_catalog, fail


def main():
    """Печатает JSON с jobs (отфильтрованные по --jobs) и catalog."""

    jobs_filter = None

    # Парсим флаг --jobs
    if "--jobs" in sys.argv:
        idx = sys.argv.index("--jobs")
        if idx + 1 >= len(sys.argv):
            fail("флаг --jobs требует аргумента")
        jobs_filter = set(sys.argv[idx + 1].split(","))

    # Загружаем данные
    all_jobs = load_jobs()
    catalog = load_catalog()

    # Фильтруем job'ы, если нужно
    if jobs_filter:
        filtered_jobs = [j for j in all_jobs if j["id"] in jobs_filter]
        # Проверяем, что все запрошенные id'ы найдены
        found_ids = {j["id"] for j in filtered_jobs}
        missing_ids = jobs_filter - found_ids
        if missing_ids:
            fail(f"задачи не найдены: {', '.join(sorted(missing_ids))}")
        jobs_to_output = filtered_jobs
    else:
        jobs_to_output = all_jobs

    # Выводим JSON
    output = {
        "jobs": jobs_to_output,
        "catalog": catalog,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
