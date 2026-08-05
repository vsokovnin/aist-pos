#!/usr/bin/env python3
"""Собирает playbook.html — страницу «что это и зачем», которую человек читает первой.

    python3 scripts/make-playbook.py [путь к playbook.html]

По умолчанию кладёт файл рядом с навыком: playbook.html в корне папки навыка.
Содержание правится в rubric/playbook.json, вёрстка — assets/playbook-template.html.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["title", "lead", "acts", "problem", "pains", "hero", "vision", "stories",
          "effect", "path", "tasks", "how", "need", "not", "privacy", "start"]


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def build(out_path):
    data_path = ROOT / "rubric" / "playbook.json"
    tpl_path = ROOT / "assets" / "playbook-template.html"
    if not data_path.exists():
        fail("не найден " + str(data_path))
    if not tpl_path.exists():
        fail("не найден " + str(tpl_path))
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("плейбук — невалидный JSON: " + str(e))

    missing = [f for f in FIELDS if not data.get(f)]
    if missing:
        fail("в плейбуке нет разделов: " + ", ".join(missing))
    for f in ("chaosLabel", "chaosTitle", "chaosQuestion",
              "digestLabel", "digestTitle", "digest", "digestFoot", "after"):
        if not data["hero"].get(f):
            fail("в сцене плейбука нет поля " + f)
    if len(data["hero"]["digest"]) < 3:
        fail("в утренней сводке меньше трёх строк — сцена не выглядит настоящей")
    for p in data["pains"]:
        if not p.get("pain") or not p.get("cost"):
            fail("у боли должны быть и формулировка, и цена: " + json.dumps(p, ensure_ascii=False))
    if len(data["stories"]["items"]) < 3:
        fail("в плейбуке меньше трёх историй — по одной истории человек не поймёт, про него ли это")

    version = "неизвестна"
    skill_md = ROOT / "SKILL.md"
    if skill_md.exists():
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
                break

    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    block = "/* PLAYBOOK */\nconst PB = %s;\n/* конец PLAYBOOK */" % json.dumps(
        payload, ensure_ascii=False, indent=2)
    html, n = re.subn(r"/\* PLAYBOOK \*/.*?/\* конец PLAYBOOK \*/", lambda m: block,
                      tpl_path.read_text(encoding="utf-8"), flags=re.S)
    if n != 1:
        fail("в шаблоне плейбука не найдены маркеры PLAYBOOK")
    html = html.replace('const SKILL_VERSION = "dev";',
                        'const SKILL_VERSION = "%s";' % version, 1)
    if "undefined" in html:
        fail("в плейбуке осталось undefined")
    external = re.findall(r"https?://[^\s\"')]+", html)
    if external:
        fail("в плейбуке внешние адреса: " + ", ".join(external[:3]))
    out_path.write_text(html, encoding="utf-8")
    return version


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "playbook.html"
    v = build(target)
    print("плейбук:", target.resolve())
    print("версия: ", v)
