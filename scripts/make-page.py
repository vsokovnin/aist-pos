#!/usr/bin/env python3
"""Собирает plan.html из шаблона и профиля человека.

    python3 scripts/make-page.py profile.json plan.html

profile.json — только персональная часть (уровни, шаги, находки осмотра).
Лестницы уровней уже внутри шаблона: их писать не нужно.
"""
import json
import re
import sys
from pathlib import Path

CAPS = ["memory", "context_seed", "naming", "root_file", "git", "source_map",
        "connectors", "capture", "graph", "doc_source", "playbook", "quality",
        "output_form", "research", "decision_log", "handover"]
REQUIRED = ["meta", "stageWas", "stageNow", "directions", "weakNote", "capabilities",
            "moved", "pinned", "mainStep", "nextSteps", "inspection", "signals",
            "reassess", "journal"]
SETS = ["day", "meet", "promises", "draft", "followup", "board", "report",
        "quarter", "market", "dossier", "deck", "assistant"]


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def main():
    if len(sys.argv) != 3:
        fail("нужно два аргумента: profile.json и путь к plan.html")
    profile_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    template = Path(__file__).resolve().parent.parent / "assets" / "plan-template.html"
    if not template.exists():
        fail("не найден шаблон " + str(template))

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("профиль — невалидный JSON: " + str(e))

    missing = [k for k in REQUIRED if k not in data]
    if missing:
        fail("в профиле нет полей: " + ", ".join(missing))

    caps = data["capabilities"]
    ids = [c.get("id") for c in caps]
    if sorted(ids) != sorted(CAPS):
        fail("нужны ровно шестнадцать способностей: " + ", ".join(CAPS))
    for c in caps:
        for key in ("level", "levelNow"):
            if not isinstance(c.get(key), int) or not 1 <= c[key] <= 5:
                fail("у способности %s поле %s должно быть числом от 1 до 5" % (c["id"], key))
        if "ladder" in c:
            fail("лестницы уже в шаблоне — уберите поле ladder у %s" % c["id"])

    unknown = [p for p in data["pinned"] if p not in SETS]
    if unknown:
        fail("в pinned неизвестные наборы: " + ", ".join(unknown))
    for st in data["nextSteps"]:
        if st.get("cap") not in CAPS:
            fail("шаг %s ссылается на неизвестную способность %s" % (st.get("id"), st.get("cap")))
        if not any(c["id"] == st["cap"] and c["levelNow"] < 3 for c in caps):
            fail("шаг %s висит на способности, которая уже закрыта или отсутствует" % st.get("id"))

    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    version = "неизвестна"
    if skill_md.exists():
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
                break

    html = template.read_text(encoding="utf-8")
    block = "/* DATA */\nconst DATA = %s;\n/* конец DATA */" % json.dumps(
        data, ensure_ascii=False, indent=2)
    out, n = re.subn(r"/\* DATA \*/.*?/\* конец DATA \*/", lambda m: block, html, flags=re.S)
    if n != 1:
        fail("в шаблоне не найдены маркеры DATA")

    if "undefined" in out:
        fail("в собранной странице осталось undefined")
    external = re.findall(r"https?://[^\s\"')]+", out)
    if external:
        fail("в странице внешние адреса: " + ", ".join(external[:3]))

    out = out.replace("<head>", "<head>\n<!-- собрано навыком AIST POS %s -->" % version, 1)
    out_path.write_text(out, encoding="utf-8")
    repeat = any(c["level"] != c["levelNow"] for c in caps)
    print("страница:", out_path.resolve())
    print("версия:  %s" % version)
    print("стадия:  %s (%s)" % (data["stageNow"]["n"], data["stageNow"]["name"]))
    print("шагов:   %s · наборов рекомендовано: %s" % (len(data["nextSteps"]), len(data["pinned"])))
    print("серий на радаре:", 2 if repeat else 1)


if __name__ == "__main__":
    main()
