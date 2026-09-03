#!/usr/bin/env python3
"""Собирает assessment.html — оценку одной страницей, без навыка и без чата.

    python3 scripts/make-standalone.py [путь к assessment.html]

Человек открывает файл, отвечает на вопросы и тут же, на той же странице, видит результат:
стадию, паутинку, какие задачи каталога у него заработают и первый шаг с готовым запросом.
Всё считается в браузере по тем же данным, что и навык: вопросы из rubric/quickstart.json,
пороги задач из rubric/job-sets.json, формулировки и рецепты из рубрики, стадии из stage-map.

Зачем отдельно от навыка: показ не должен зависеть ни от установки, ни от поведения агента,
ни от того, доедет ли файл до человека. Открыл ссылку — прошёл — увидел.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = {
    "kicker": "AIST POS · оценка зрелости",
    "read": "пара минут",
    "title": "Как ваша работа устроена сегодня",
    "intro": "Вопросы про обычную рабочую неделю, а не про ИИ. Правильных ответов нет: "
             "выбирайте то, как есть сейчас, даже если это «делаю руками». В конце нажмите "
             "кнопку — и увидите, где вы и с чего начать.",
    "skip": "Такой работы у меня нет, или не знаю, что выбрать",
    "count": "Отвечено",
    "button": "Показать результат",
}


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def build(out_path):
    tpl_path = ROOT / "assets" / "standalone-template.html"
    if not tpl_path.exists():
        fail("не найден " + str(tpl_path))
    rub = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    quick = json.loads((ROOT / "rubric" / "quickstart.json").read_text(encoding="utf-8"))
    cat = json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))
    stagemap = (ROOT / "rubric" / "stage-map.yaml").read_text(encoding="utf-8")

    head, _, tail = rub.partition("capabilities:")
    clusters = [{"id": i, "title": t} for i, t in
                re.findall(r"\n  - id: (\w+)\n    title: \"([^\"]+)\"",
                           head.partition("clusters:")[2])]
    caps = []
    for b in re.split(r"\n  - id: ", "\n" + tail)[1:]:
        cid = b.split("\n", 1)[0].strip()
        if "\n    cluster: " not in b:
            continue
        need = re.search(r'\n    need: "(.*?)"\n', b)
        title = re.search(r'\n    title: "(.*?)"\n', b)
        short = re.search(r'\n    short: "(.*?)"\n', b)
        cluster = re.search(r"\n    cluster: (\w+)\n", b)
        steps = {m.group(1): {"do": m.group(2), "how": m.group(3), "done_when": m.group(4)}
                 for m in re.finditer(r'      (to_L[345]):\n        do: "(.*?)"\n'
                                      r'        how: "(.*?)"\n        done_when: "(.*?)"\n', b)}
        rec = steps.get("to_L3")
        if not (need and title and cluster):
            fail("у способности %s нет названия, направления или человеческой формулировки" % cid)
        caps.append({
            "id": cid, "dir": cluster.group(1), "title": title.group(1),
            "short": short.group(1) if short else title.group(1),
            "need": need.group(1),
            "to_L3": rec,
            # шаг может вести и на четвёртый уровень — тогда нужен свой рецепт, а не третий
            "to_L4": steps.get("to_L4"),
        })
    if not caps:
        fail("в рубрике не нашлось ни одной способности")
    no_rec = [c["id"] for c in caps if not c["to_L3"]]
    if no_rec:
        fail("нет рецепта на третий уровень у: " + ", ".join(no_rec))

    stages = {int(n): {"name": nm, "desc": d} for n, nm, d in
              re.findall(r"\n  (\d): \{name: \"([^\"]+)\",\s+desc: \"([^\"]+)\"\}", stagemap)}
    if len(stages) != 5:
        fail("в карте стадий должно быть пять ступеней, найдено %d" % len(stages))

    cap_ids = {c["id"] for c in caps}
    questions = []
    for q in quick["questions"]:
        for o in q["options"]:
            unknown = set(o["sets"]) - cap_ids
            if unknown:
                fail("вопрос %s ставит уровни неизвестным способностям: %s"
                     % (q["id"], ", ".join(sorted(unknown))))
        questions.append({"id": q["id"], "ask": q["ask"],
                          "options": [{"t": o["t"], "sets": o["sets"]} for o in q["options"]]})

    jobs = [{"id": j["id"], "group": j["group"], "title": j["title"],
             "short": j["short"], "promise": j["promise"], "needs": j["needs"]} for j in cat["jobs"]]
    for j in jobs:
        unknown = set(j["needs"]) - cap_ids
        if unknown:
            fail("задача %s требует неизвестные способности: %s" % (j["id"], ", ".join(sorted(unknown))))
    groups = [{"id": g["id"], "title": g["title"], "note": g["note"]} for g in cat["groups"]]

    version = "неизвестна"
    for line in (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break

    data = {"version": version, "ui": UI, "clusters": clusters, "caps": caps,
            "stages": stages, "questions": questions, "jobs": jobs, "groups": groups}
    block = "/* DATA */\nconst D = %s;\n/* конец DATA */" % json.dumps(data, ensure_ascii=False, indent=1)
    html, n = re.subn(r"/\* DATA \*/.*?/\* конец DATA \*/", lambda m: block,
                      tpl_path.read_text(encoding="utf-8"), flags=re.S)
    if n != 1:
        fail("в шаблоне не найдены маркеры DATA")

    # то же, что и на странице вопросов: формулировки доезжают целиком, чужого на странице нет
    def onpage(s):
        return json.dumps(s, ensure_ascii=False)[1:-1] in html
    for q in questions:
        for o in q["options"]:
            if not onpage(o["t"]):
                fail("вариант ответа не доехал целиком: " + o["t"][:40])
    for c in caps:
        if not onpage(c["need"]):
            fail("формулировка способности не доехала целиком: " + c["need"][:40])
    if re.findall(r"https?://[^\s\"')]+", html):
        fail("на странице внешние адреса — она должна работать без сети")

    out_path.write_text(html, encoding="utf-8")
    return version, len(questions), len(caps), len(jobs)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assessment.html"
    v, nq, nc, nj = build(target)
    print("оценка одной страницей:", target.resolve())
    print("версия: %s · вопросов: %d · способностей: %d · задач: %d" % (v, nq, nc, nj))
