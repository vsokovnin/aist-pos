#!/usr/bin/env python3
"""Сохранение результатов слепой деривации в derivation/raw."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inputs import load_jobs, load_catalog, fail

ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT / "derivation" / "raw"


def validate_and_save(data_list):
    """Валидирует массив объектов и сохраняет их в derivation/raw."""

    # Загружаем справочники
    jobs = load_jobs()
    catalog = load_catalog()
    job_ids = {j["id"] for j in jobs}
    catalog_ids = {c["id"] for c in catalog}

    # Создаём папку, если её нет
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    saved_files = []

    for obj in data_list:
        # Проверяем job_id
        if "job_id" not in obj:
            fail("отсутствует job_id в объекте")
        job_id = obj["job_id"]
        if job_id not in job_ids:
            fail(f"задача '{job_id}' не найдена в каталоге")

        # Проверяем agent_n
        if "agent_n" not in obj:
            fail(f"отсутствует agent_n в объекте для задачи '{job_id}'")
        agent_n = obj["agent_n"]
        if agent_n not in (1, 2, 3):
            fail(f"задача '{job_id}': agent_n должен быть 1, 2 или 3, получено {agent_n}")

        # Проверяем операции
        if "operations" not in obj or not isinstance(obj["operations"], list):
            fail(f"задача '{job_id}', агент {agent_n}: operations должен быть массивом")

        # Проверяем ячейки способностей
        if "cells" not in obj or not isinstance(obj["cells"], list):
            fail(f"задача '{job_id}', агент {agent_n}: cells должен быть массивом")

        for cell in obj["cells"]:
            cap_id = cell.get("cap_id")
            if cap_id not in catalog_ids:
                fail(f"задача '{job_id}', агент {agent_n}: способность '{cap_id}' не найдена в каталоге")

            level = cell.get("level")
            if not isinstance(level, int) or level < 1 or level > 5:
                fail(f"задача '{job_id}', агент {agent_n}, способность '{cap_id}': level должен быть int 1..5, получено {level}")

            failure_scenario = cell.get("failure_scenario", "")
            if not isinstance(failure_scenario, str) or len(failure_scenario) < 40:
                fail(f"задача '{job_id}', агент {agent_n}, способность '{cap_id}': failure_scenario должен быть строка ≥40 символов, получено {len(failure_scenario)}")

        # Проверяем gaps
        if "gaps" not in obj or not isinstance(obj["gaps"], list):
            fail(f"задача '{job_id}', агент {agent_n}: gaps должен быть массивом")

        for gap in obj["gaps"]:
            failure_scenario = gap.get("failure_scenario", "")
            if not isinstance(failure_scenario, str) or len(failure_scenario) < 40:
                fail(f"задача '{job_id}', агент {agent_n}, gap: failure_scenario должен быть строка ≥40 символов, получено {len(failure_scenario)}")

        # Проверяем, что файл не существует
        target_file = RAW_DIR / f"{job_id}-{agent_n}.json"
        if target_file.exists():
            fail(f"файл уже существует: {target_file.name} (повторный агент?)")

        # Сохраняем файл
        target_file.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        saved_files.append(f"{job_id}-{agent_n}")

    # Выводим итог
    print(f"Записано {len(saved_files)} файлов: {', '.join(saved_files)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        fail("использование: python3 save-raw.py <path.json>")

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        fail(f"файл не найден: {json_path}")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"некорректный JSON: {e}")

    if not isinstance(data, list):
        fail("JSON должен быть массивом объектов")

    validate_and_save(data)
