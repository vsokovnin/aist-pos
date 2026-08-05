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
FIELDS = ["title", "head", "problem", "vision", "hero", "map", "pains", "tasks",
          "jobs", "effect", "not", "need", "privacy", "start"]


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
    for f in ("kicker", "read", "cells"):
        if not data["head"].get(f):
            fail("в шапке плейбука нет поля " + f)
    if len(data["head"]["cells"]) != 3:
        fail("в шапке должно быть ровно три опоры: что на выходе, что от вас, чего не потребуется")
    for c in data["head"]["cells"]:
        if not c.get("label") or not c.get("text"):
            fail("у опоры в шапке должны быть и подпись, и текст")
    m = data["map"]
    for f in ("title", "sub", "job", "capsLabel", "caps", "note", "foot"):
        if not m.get(f):
            fail("в карте модели нет поля " + f)
    jobs_path = ROOT / "rubric" / "job-sets.json"
    if not jobs_path.exists():
        fail("не найден " + str(jobs_path))
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
    job = next((j for j in jobs if j["id"] == m["job"].get("id")), None)
    if job is None:
        fail("в карте показана задача, которой нет в каталоге: " + str(m["job"].get("id")))
    if m["job"]["title"] != job["title"]:
        fail("название задачи в карте разошлось с каталогом: " + m["job"]["title"])
    shown = {c.get("id"): c.get("need") for c in m["caps"]}
    if shown != job["needs"]:
        fail("в карте требуемые уровни разошлись с каталогом задач: показано %s, в каталоге %s"
             % (shown, job["needs"]))
    if m["capsLabel"].count("четырёх") and len(m["caps"]) != 4:
        fail("в подписи карты сказано «из четырёх», а способностей показано " + str(len(m["caps"])))

    for f in ("digestLabel", "digestTitle", "digest", "digestFoot", "after"):
        if not data["hero"].get(f):
            fail("в сцене плейбука нет поля " + f)
    if len(data["hero"]["digest"]) < 3:
        fail("в утренней сводке меньше трёх строк — сцена не выглядит настоящей")
    for p in data["pains"]:
        if not p.get("pain") or not p.get("cost"):
            fail("у боли должны быть и формулировка, и цена")
    for f in ("title", "sub", "hint", "foot"):
        if not data["jobs"].get(f):
            fail("в ленте задач нет поля " + f)
    if data["jobs"].get("items"):
        fail("задачи в плейбуке не переписываются — сборщик берёт их из каталога job-sets.json")
    drawn = set(re.findall(r"^  (\w+):'", tpl_path.read_text(encoding="utf-8"), re.M))
    data["jobs"]["items"] = [{"title": j["title"], "short": j["short"], "icon": j["icon"]} for j in jobs]
    no_icon = sorted({j["icon"] for j in jobs} - drawn)
    if no_icon:
        fail("для задач нет знаков в шаблоне: " + ", ".join(no_icon))

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
