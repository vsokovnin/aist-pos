#!/usr/bin/env python3
"""Собирает одностраничное демо оценки для aist.tech/ai-demo-scan.

    python3 scripts/make-demo.py [путь к index.html]

Внутрь страницы кладётся настоящий шаблон плана: человек отвечает на вопросы рубрики,
браузер собирает из ответов профиль и рисует ту же страницу, что выдаёт навык.
Источник вопросов, уровней, рецептов и инструкций — рубрика навыка, поэтому демо
не может разойтись с продуктом.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def load_builder():
    """Помощники сборщика страницы — чтобы каталог задач и рецепты читались одним кодом."""
    spec = importlib.util.spec_from_file_location("mp", ROOT / "scripts" / "make-page.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_rubric():
    """Направления и способности рубрики: вопрос, пять уровней, признак готовности."""
    text = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    head, _, tail = text.partition("capabilities:")
    if not tail:
        fail("в рубрике нет раздела capabilities")

    clusters = []
    for block in re.split(r"\n  - id: ", "\n" + head.partition("clusters:")[2])[1:]:
        cid = block.split("\n", 1)[0].strip()
        title = re.search(r'\n    title: "(.*?)"', block)
        if title:
            clusters.append({"id": cid, "title": title.group(1)})
    if not clusters:
        fail("в рубрике не разобрались направления")

    caps = []
    for block in re.split(r"\n  - id: ", "\n" + tail)[1:]:
        cid = block.split("\n", 1)[0].strip()
        cluster = re.search(r"\n    cluster: (\w+)", block)
        title = re.search(r'\n    title: "(.*?)"', block)
        ask = re.search(r'\n    ask: "(.*?)"\n', block, re.S)
        if not (cluster and title and ask):
            fail("у способности %s нет направления, названия или вопроса" % cid)
        # каждый уровень — своя строка; без ^..$ соседние совпадения съедают общий перевод строки
        levels = re.findall(r'^      (L[1-5]): "(.*)"$', block, re.M)
        by_key = dict(levels)
        if len(by_key) != 5:
            fail("у способности %s не пять уровней, а %d" % (cid, len(by_key)))
        done = re.search(r'\n      to_L3:\n        do: ".*?"\n        how: ".*?"\n'
                         r'        done_when: "(.*?)"\n', block, re.S)
        caps.append({
            "id": cid, "cluster": cluster.group(1), "title": title.group(1),
            "ask": ask.group(1),
            "levels": [by_key["L%d" % i] for i in range(1, 6)],
            "done_when": done.group(1) if done else "",
        })
    known = {c["id"] for c in clusters}
    for c in caps:
        if c["cluster"] not in known:
            fail("способность %s ссылается на неизвестное направление %s" % (c["id"], c["cluster"]))
    return {"clusters": clusters, "caps": caps}


def parse_stages():
    text = (ROOT / "rubric" / "stage-map.yaml").read_text(encoding="utf-8")
    out = {}
    for n, name, desc in re.findall(r'\n  (\d): \{name: "(.*?)",\s+desc: "(.*?)"\}', text):
        out[n] = {"name": name, "desc": desc}
    if len(out) != 5:
        fail("в карте стадий разобрано %d стадий вместо пяти" % len(out))
    return out


def plan_template(mp):
    """Шаблон страницы плана с подставленными рецептами, задачами и инструкциями.

    Блок DATA остаётся маркером: профиль подставляется в браузере из ответов.
    """
    html = (ROOT / "assets" / "plan-template.html").read_text(encoding="utf-8")
    icons = set(re.findall(r"^  (\w+):'", html, flags=re.M))
    jobs = mp.load_jobs(icons)
    need_L4 = {c for j in jobs["jobs"] for c, lvl in j["needs"].items() if lvl >= 4}
    recipes = mp.load_recipes(need_L4)
    guides = mp.load_guides()

    inline = {}
    for cap, by_step in guides.items():
        for key, g in by_step.items():
            item = dict(g)
            item["ask"] = recipes.get(cap, {}).get(key, {}).get("how", "")
            inline[cap + "/" + key] = item

    version = "неизвестна"
    for line in (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break

    blocks = [
        (r"/\* RECIPES \*/.*?/\* конец RECIPES \*/",
         "/* RECIPES */\nconst RECIPES = %s;\n/* конец RECIPES */"
         % json.dumps(recipes, ensure_ascii=False)),
        (r"/\* GUIDES \*/.*?/\* конец GUIDES \*/",
         "/* GUIDES */\nconst GUIDES = %s;\n/* конец GUIDES */"
         % json.dumps(inline, ensure_ascii=False)),
        (r"/\* JOBS \*/.*?/\* конец JOBS \*/",
         "/* JOBS */\nconst JOB_GROUPS = %s;\nconst JOBS = %s;\n/* конец JOBS */"
         % (json.dumps(jobs["groups"], ensure_ascii=False),
            json.dumps(jobs["jobs"], ensure_ascii=False))),
    ]
    for pattern, block in blocks:
        html, n = re.subn(pattern, lambda m: block, html, flags=re.S)
        if n != 1:
            fail("в шаблоне плана не найдены маркеры: " + pattern)
    html = html.replace('const SKILL_VERSION = "dev";',
                        'const SKILL_VERSION = "%s";' % version, 1)
    if "/* DATA */" not in html:
        fail("в шаблоне плана потерялся маркер DATA")
    return html, jobs, version


def js_string(text):
    """Строка для вставки внутрь <script>: закрывающий тег не должен рвать страницу."""
    return json.dumps(text, ensure_ascii=False).replace("</", "<\\/")


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "ai-demo-scan" / "index.html"
    mp = load_builder()
    plan, jobs, version = plan_template(mp)
    rubric = parse_rubric()
    stages = parse_stages()

    if len(rubric["caps"]) != len(mp.CAPS):
        fail("в рубрике %d способностей, а сборщик знает %d"
             % (len(rubric["caps"]), len(mp.CAPS)))

    demo = (ROOT / "assets" / "demo-template.html").read_text(encoding="utf-8")
    subs = [
        (r"/\* PLAN \*/.*?/\* конец PLAN \*/",
         "/* PLAN */\nconst PLAN_TPL = %s;\n/* конец PLAN */" % js_string(plan)),
        (r"/\* RUBRIC \*/.*?/\* конец RUBRIC \*/",
         "/* RUBRIC */\nconst RUBRIC = %s;\n/* конец RUBRIC */"
         % json.dumps(rubric, ensure_ascii=False)),
        (r"/\* STAGES \*/.*?/\* конец STAGES \*/",
         "/* STAGES */\nconst STAGES = %s;\n/* конец STAGES */"
         % json.dumps(stages, ensure_ascii=False)),
        (r"/\* JOBSD \*/.*?/\* конец JOBSD \*/",
         "/* JOBSD */\nconst JOBS_D = %s;\n/* конец JOBSD */"
         % json.dumps(jobs["jobs"], ensure_ascii=False)),
    ]
    for pattern, block in subs:
        demo, n = re.subn(pattern, lambda m: block, demo, flags=re.S)
        if n != 1:
            fail("в шаблоне демо не найдены маркеры: " + pattern)

    external = re.findall(r"https?://[^\s\"')]+", demo)
    if external:
        fail("в демо внешние адреса: " + ", ".join(external[:3]))
    if "</script>" not in demo.split("<script>")[-1]:
        fail("в демо не закрыт тег script — строка шаблона порвала страницу")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(demo, encoding="utf-8")
    print("демо:      %s" % out_path.resolve())
    print("навык:     %s" % version)
    print("вопросов:  %d · направлений: %d · задач: %d"
          % (len(rubric["caps"]), len(rubric["clusters"]), len(jobs["jobs"])))
    print("размер:    %d КБ" % (len(demo.encode("utf-8")) // 1024))


if __name__ == "__main__":
    main()
