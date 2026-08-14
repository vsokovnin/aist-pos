#!/usr/bin/env python3
"""Гейт: ярусы доехали до пользователя.

Собирает страницу из примера профиля и проверяет четыре вещи на собранном файле:
  1. блок «Файлы и данные» есть в разметке вместе со всеми тремя способностями гигиены;
  2. обе подписи осей задачи («заработает», «не будет подводить») есть в разметке;
  3. состав гигиены доехал из каталога в страницу отдельной константой;
  4. у всех задач, где каталог задаёт ярус надёжности, он доехал в страницу.

Чего гейт НЕ проверяет: как это выглядит после отрисовки. Страница рисуется скриптом
в браузере, статическая проверка видит исходник, а не результат. Вёрстка проверяется
живым открытием страницы, а слова агента — живым прогоном оценки.

    python3 scripts/audit/check-tiers-page.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("AUDIT_ROOT", Path(__file__).resolve().parent.parent.parent))

HEADING = "Файлы и данные: сохранность, поиск, доступ"
# Термин словаря — «заработает» / «не будет подводить»; в заголовках он стоит в естественной
# форме, её и проверяем: это то, что человек видит.
AXIS_ENTRY = "Чтобы заработало"
AXIS_HARDENS = "Чтобы не подводило"


def main():
    catalog = json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))
    hygiene = catalog.get("hygiene") or {}
    hyg_caps = hygiene.get("caps") or []
    jobs_with_hardens = [j["id"] for j in catalog["jobs"] if j.get("hardens")]

    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "plan.html"
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "make-page.py"),
             str(ROOT / "examples" / "profile.example.json"), str(page)],
            capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("СТРАНИЦА НЕ СОБРАЛАСЬ:\n" + (r.stdout + r.stderr).strip())
        html = page.read_text(encoding="utf-8")

    bad = []

    if HEADING not in html:
        bad.append("нет заголовка блока «%s»" % HEADING)
    for cap in hyg_caps:
        if ('"%s"' % cap) not in html:
            bad.append("способность гигиены %s не доехала в страницу" % cap)

    for axis in (AXIS_ENTRY, AXIS_HARDENS):
        if axis not in html:
            bad.append("нет подписи оси «%s»" % axis)

    if "const HYGIENE" not in html:
        bad.append("состав гигиены не доехал в страницу отдельной константой")
    else:
        block = html.split("const HYGIENE", 1)[1].split(";", 1)[0]
        for cap in hyg_caps:
            if cap not in block:
                bad.append("в составе гигиены на странице нет %s" % cap)

    missing = [j for j in jobs_with_hardens if ('"%s"' % j) not in html]
    if missing:
        bad.append("задачи без яруса надёжности на странице: " + ", ".join(missing))
    if '"hardens"' not in html:
        bad.append("ярус надёжности не доехал в страницу ни по одной задаче")

    if bad:
        print("ЯРУСЫ НЕ ДОШЛИ ДО ПОЛЬЗОВАТЕЛЯ:")
        for b in bad:
            print("  ·", b)
        sys.exit(1)
    print("ярусы на странице: блок «Файлы и данные», обе оси, %d задач с ярусом надёжности"
          % len(jobs_with_hardens))


if __name__ == "__main__":
    main()
