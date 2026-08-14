#!/usr/bin/env python3
"""Собирает first-talk.html — страницу первого разговора, на которой человек отвечает сам.

    python3 scripts/make-first-talk.py [путь к first-talk.html]

Зачем страница. Форма в чате режет длинные строки, а формулировки вариантов выверены и
сокращению не подлежат: человек выбирает по тому, что видит. На странице вариант виден целиком,
человек кликает, а в конце забирает ответ одной кнопкой и вставляет его навыку в чат.

Что уезжает на страницу: вопросы и тексты вариантов. Что НЕ уезжает: поле sets — какой вариант
какой уровень ставит. Иначе человек отвечает не про свою работу, а про желаемую оценку.

Содержание правится в rubric/quickstart.json, вёрстка — assets/first-talk-template.html.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_FIELDS = ["kicker", "read", "title", "intro", "skip", "count", "button",
             "outTitle", "outText", "copyOk", "copyFail"]
# вёрстка, которая прячет часть текста: ровно то, из-за чего страница и появилась
CUTTERS = ["text-overflow", "line-clamp", "white-space:nowrap", "white-space: nowrap"]


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def build(out_path):
    data_path = ROOT / "rubric" / "quickstart.json"
    tpl_path = ROOT / "assets" / "first-talk-template.html"
    if not data_path.exists():
        fail("не найден " + str(data_path))
    if not tpl_path.exists():
        fail("не найден " + str(tpl_path))
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("первый разговор — невалидный JSON: " + str(e))

    page = data.get("page")
    if not page:
        fail("в rubric/quickstart.json нет раздела page — текстов страницы")
    missing = [f for f in UI_FIELDS if not page.get(f)]
    if missing:
        fail("в текстах страницы нет полей: " + ", ".join(missing))

    questions = data.get("questions") or []
    if not questions:
        fail("в rubric/quickstart.json нет вопросов")
    payload = {"ui": {f: page[f] for f in UI_FIELDS}, "questions": []}
    for q in questions:
        if not q.get("id") or not q.get("ask") or not q.get("options"):
            fail("у вопроса %s нет идентификатора, текста или вариантов" % q.get("id"))
        for o in q["options"]:
            if "short" in o:
                fail("у варианта есть сокращённый ярлык — на странице показывается только полная "
                     "формулировка, сокращать нечем и незачем")
        payload["questions"].append({
            "id": q["id"],
            "ask": q["ask"],
            "options": [{"t": o["t"]} for o in q["options"]],
        })

    version = "неизвестна"
    skill_md = ROOT / "SKILL.md"
    if skill_md.exists():
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
                break

    tpl = tpl_path.read_text(encoding="utf-8")
    for c in CUTTERS:
        if c in tpl:
            fail("в вёрстке страницы есть «%s» — она обрежет формулировку варианта" % c)

    block = "/* QUIZ */\nconst Q = %s;\n/* конец QUIZ */" % json.dumps(
        payload, ensure_ascii=False, indent=2)
    html, n = re.subn(r"/\* QUIZ \*/.*?/\* конец QUIZ \*/", lambda m: block, tpl, flags=re.S)
    if n != 1:
        fail("в шаблоне страницы не найдены маркеры QUIZ")
    html = html.replace('const SKILL_VERSION = "dev";',
                        'const SKILL_VERSION = "%s";' % version, 1)

    # главная проверка: каждая формулировка доехала до страницы целиком и дословно
    def onpage(s):
        return json.dumps(s, ensure_ascii=False)[1:-1] in html
    for q in questions:
        if not onpage(q["ask"]):
            fail("вопрос про задачу %s не попал на страницу целиком" % q["job"])
        for o in q["options"]:
            if not onpage(o["t"]):
                fail("вариант ответа в вопросе про %s не попал на страницу целиком: %s"
                     % (q["job"], o["t"][:40]))
    if '"sets"' in html:
        fail("на страницу уехало, какой вариант какой уровень ставит — человек не должен это видеть")
    if "undefined" in html:
        fail("на странице осталось undefined")
    external = re.findall(r"https?://[^\s\"')]+", html)
    if external:
        fail("на странице внешние адреса: " + ", ".join(external[:3]))

    out_path.write_text(html, encoding="utf-8")
    return version, len(payload["questions"])


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "first-talk.html"
    v, n = build(target)
    print("первый разговор:", target.resolve())
    print("вопросов:       ", n)
    print("версия:         ", v)
