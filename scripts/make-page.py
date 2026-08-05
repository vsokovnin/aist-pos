#!/usr/bin/env python3
"""Собирает plan.html из шаблона, профиля человека и каталога задач.

    python3 scripts/make-page.py profile.json plan.html

profile.json — только персональная часть (уровни, шаги, находки осмотра, выбранная задача).
Лестницы уровней уже внутри шаблона, каталог задач — в rubric/job-sets.json.
"""
import json
import re
import sys
from pathlib import Path

CAPS = ["memory", "context_seed", "naming", "root_file", "git", "source_map",
        "connectors", "capture", "graph", "doc_source", "playbook", "quality",
        "output_form", "research", "decision_log", "handover", "autonomy",
        "sign_off"]
REQUIRED = ["meta", "stageWas", "stageNow", "directions", "weakNote", "capabilities",
            "moved", "chosen", "mainStep", "inspection", "signals",
            "reassess", "journal"]
ROOT = Path(__file__).resolve().parent.parent


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def load_recipes(need_L4):
    """Рецепты переходов из рубрики: что сделать · как сделать · что считать успехом."""
    text = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    blocks = re.split(r"\n  - id: ", "\n" + text)[1:]
    out = {}
    for b in blocks:
        cap = b.split("\n", 1)[0].strip()
        # в файле есть и список направлений с такими же id — там нет поля cluster
        if cap not in CAPS or "\n    cluster: " not in b:
            continue
        steps = {}
        for m in re.finditer(
                r"      (to_L[345]):\n        do: \"(.*?)\"\n        how: \"(.*?)\"\n"
                r"        done_when: \"(.*?)\"\n", b):
            steps[m.group(1)] = {"do": m.group(2), "how": m.group(3), "done_when": m.group(4)}
        if "to_L3" not in steps:
            fail("у способности %s нет рецепта перехода на третий уровень "
                 "(нужны поля do, how, done_when)" % cap)
        if cap in need_L4 and "to_L4" not in steps:
            fail("способность %s требуется какой-то задаче на четвёртом уровне, "
                 "но рецепта перехода на четвёртый уровень нет" % cap)
        out[cap] = steps
    missing = [c for c in CAPS if c not in out]
    if missing:
        fail("в рубрике нет рецептов для способностей: " + ", ".join(missing))
    return out


def load_guides():
    """Пошаговые инструкции к рекомендациям. Файла нет — инструкции просто не собираются."""
    path = ROOT / "rubric" / "guides.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("файл инструкций — невалидный JSON: " + str(e))
    guides = data.get("guides", {})
    for cap, byStep in guides.items():
        if cap not in CAPS:
            fail("инструкция написана для неизвестной способности " + cap)
        for key, g in byStep.items():
            for field in ("title", "why", "before", "steps", "check", "pitfalls", "next"):
                if not g.get(field):
                    fail("в инструкции %s/%s нет поля %s" % (cap, key, field))
            for i, st in enumerate(g["steps"], 1):
                for field in ("do", "see", "fix"):
                    if not st.get(field):
                        fail("в инструкции %s/%s у шага %d нет поля %s" % (cap, key, i, field))
    return guides


def write_guides(guides, recipes, caps_open, out_dir, version):
    """Собирает по странице на каждую открытую рекомендацию, для которой есть инструкция."""
    tpl_path = ROOT / "assets" / "guide-template.html"
    if not tpl_path.exists():
        fail("не найден шаблон инструкции " + str(tpl_path))
    tpl = tpl_path.read_text(encoding="utf-8")
    written = {}
    for cap, key in caps_open:
        g = guides.get(cap, {}).get(key)
        if not g:
            continue
        payload = dict(g)
        payload["cap"] = cap
        payload["transition"] = key
        payload["kicker"] = "Шаг плана · уровень %s" % key.replace("to_L", "")
        payload["ask"] = recipes[cap][key]["how"]
        block = "/* GUIDE */\nconst GUIDE = %s;\n/* конец GUIDE */" % json.dumps(
            payload, ensure_ascii=False, indent=2)
        page, n = re.subn(r"/\* GUIDE \*/.*?/\* конец GUIDE \*/", lambda m: block, tpl, flags=re.S)
        if n != 1:
            fail("в шаблоне инструкции не найдены маркеры GUIDE")
        page = page.replace("<title>Инструкция</title>",
                            "<title>%s</title>" % g["title"], 1)
        page = page.replace('const SKILL_VERSION = "dev";',
                            'const SKILL_VERSION = "%s";' % version, 1)
        if "undefined" in page:
            fail("в инструкции %s осталось undefined" % cap)
        out_dir.mkdir(parents=True, exist_ok=True)
        name = "%s-%s.html" % (cap, key)
        (out_dir / name).write_text(page, encoding="utf-8")
        written[cap + "/" + key] = "guides/" + name
    return written


def load_jobs(icons):
    """Каталог задач: группы, задачи, требуемый уровень по каждой способности."""
    path = ROOT / "rubric" / "job-sets.json"
    if not path.exists():
        fail("не найден каталог задач " + str(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("каталог задач — невалидный JSON: " + str(e))
    groups = {g["id"] for g in data.get("groups", [])}
    if not groups:
        fail("в каталоге задач нет ни одной группы")
    if not data.get("jobs"):
        fail("в каталоге задач нет ни одной задачи")
    for j in data["jobs"]:
        for key in ("id", "group", "icon", "title", "short", "promise"):
            if not j.get(key):
                fail("у задачи %s нет поля %s" % (j.get("id", "?"), key))
        if j["group"] not in groups:
            fail("задача %s ссылается на неизвестную группу %s" % (j["id"], j["group"]))
        if j["icon"] not in icons:
            fail("у задачи %s значок %s, которого нет в шаблоне" % (j["id"], j["icon"]))
        needs = j.get("needs")
        if not needs:
            fail("у задачи %s не указано, какие способности и до какого уровня нужны" % j["id"])
        for cap, lvl in needs.items():
            if cap not in CAPS:
                fail("задача %s требует неизвестной способности %s" % (j["id"], cap))
            if not isinstance(lvl, int) or not 1 <= lvl <= 5:
                fail("в задаче %s у способности %s требуемый уровень должен быть числом от 1 до 5"
                     % (j["id"], cap))
    return data


def check_factual(data, caps):
    """Оценка по факту: сдвиг только вверх и только с доказательством из системы."""
    if int(data["meta"].get("planVersion", 1)) < 2:
        fail("оценка по факту не бывает первой: сравнивать не с чем, "
             "нужна прошлая оценка и planVersion не меньше двух")
    dropped = [c["id"] for c in caps if c["levelNow"] < c["level"]]
    if dropped:
        fail("в оценке по факту уровень не понижается — отсутствие следа в папке не доказывает "
             "потерю; понижены: " + ", ".join(dropped))
    grown = {c["id"] for c in caps if c["levelNow"] > c["level"]}
    seen = set()
    for m in data["moved"]:
        cap = m.get("cap")
        if cap not in {c["id"] for c in caps}:
            fail("в записи о сдвиге неизвестная способность %r — нужен идентификатор из рубрики"
                 % cap)
        if cap not in grown:
            fail("способность %s записана в сдвиг, но её уровень не вырос" % cap)
        if not str(m.get("proof", "")).strip():
            fail("у сдвига способности %s нет доказательства: в поле proof должен быть след "
                 "в системе, а не рассуждение" % cap)
        seen.add(cap)
    silent = sorted(grown - seen)
    if silent:
        fail("выросли без записи о сдвиге и доказательства: " + ", ".join(silent))
    if data["stageNow"]["n"] < data["stageWas"]["n"]:
        fail("в оценке по факту общая стадия не переигрывается вниз: было %s, стало %s"
             % (data["stageWas"]["n"], data["stageNow"]["n"]))


def main():
    if len(sys.argv) != 3:
        fail("нужно два аргумента: profile.json и путь к plan.html")
    profile_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    template = ROOT / "assets" / "plan-template.html"
    if not template.exists():
        fail("не найден шаблон " + str(template))
    html = template.read_text(encoding="utf-8")

    icons = set(re.findall(r"^  (\w+):'", html, flags=re.M))
    jobs = load_jobs(icons)
    job_ids = [j["id"] for j in jobs["jobs"]]
    need_L4 = {c for j in jobs["jobs"] for c, lvl in j["needs"].items() if lvl >= 4}
    recipes = load_recipes(need_L4)
    guides = load_guides()

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
        fail("нужны ровно %d способностей: %s" % (len(CAPS), ", ".join(CAPS)))
    for c in caps:
        for key in ("level", "levelNow"):
            if not isinstance(c.get(key), int) or not 1 <= c[key] <= 5:
                fail("у способности %s поле %s должно быть числом от 1 до 5" % (c["id"], key))
        if "ladder" in c:
            fail("лестницы уже в шаблоне — уберите поле ladder у %s" % c["id"])

    if data["chosen"] not in job_ids:
        fail("выбранная задача %s не из каталога: %s" % (data["chosen"], ", ".join(job_ids)))
    if "nextSteps" in data:
        fail("поле nextSteps больше не нужно: шаги страница берёт из рубрики")

    mode = data["meta"].get("mode", "full")
    if mode not in ("full", "factual"):
        fail("meta.mode бывает только full (оценка по ответам) или factual (по факту), "
             "а не %r" % mode)
    if mode == "factual":
        check_factual(data, caps)

    version = "неизвестна"
    skill_md = ROOT / "SKILL.md"
    if skill_md.exists():
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
                break

    block = "/* DATA */\nconst DATA = %s;\n/* конец DATA */" % json.dumps(
        data, ensure_ascii=False, indent=2)
    out, n = re.subn(r"/\* DATA \*/.*?/\* конец DATA \*/", lambda m: block, html, flags=re.S)
    if n != 1:
        fail("в шаблоне не найдены маркеры DATA")

    caps_open = []
    for c in caps:
        lvl = c["levelNow"]
        top = max((j["needs"].get(c["id"], 0) for j in jobs["jobs"]), default=0)
        if lvl < top:
            caps_open.append((c["id"], "to_L3" if lvl < 3 else "to_L%d" % (lvl + 1)))
    links = write_guides(guides, recipes, caps_open, out_path.parent / "guides", version)

    for cap, byStep in recipes.items():
        for key, r in byStep.items():
            r["guide"] = links.get(cap + "/" + key, "")

    rblock = ("/* RECIPES */\nconst RECIPES = %s;\n/* конец RECIPES */"
              % json.dumps(recipes, ensure_ascii=False, indent=2))
    out, n = re.subn(r"/\* RECIPES \*/.*?/\* конец RECIPES \*/", lambda m: rblock, out, flags=re.S)
    if n != 1:
        fail("в шаблоне не найдены маркеры RECIPES")

    jblock = ("/* JOBS */\nconst JOB_GROUPS = %s;\nconst JOBS = %s;\n/* конец JOBS */"
              % (json.dumps(jobs["groups"], ensure_ascii=False, indent=2),
                 json.dumps(jobs["jobs"], ensure_ascii=False, indent=2)))
    out, n = re.subn(r"/\* JOBS \*/.*?/\* конец JOBS \*/", lambda m: jblock, out, flags=re.S)
    if n != 1:
        fail("в шаблоне не найдены маркеры JOBS")

    if "undefined" in out:
        fail("в собранной странице осталось undefined")
    external = re.findall(r"https?://[^\s\"')]+", out)
    if external:
        fail("в странице внешние адреса: " + ", ".join(external[:3]))

    out = out.replace("<head>", "<head>\n<!-- собрано навыком AIST POS %s -->" % version, 1)
    out = out.replace('const SKILL_VERSION = "dev";', 'const SKILL_VERSION = "%s";' % version, 1)
    out_path.write_text(out, encoding="utf-8")

    level = {c["id"]: c["levelNow"] for c in caps}
    ready = sum(1 for j in jobs["jobs"]
                if all(level[c] >= n for c, n in j["needs"].items()))
    chosen = next(j for j in jobs["jobs"] if j["id"] == data["chosen"])
    repeat = any(c["level"] != c["levelNow"] for c in caps)
    grown = sum(1 for c in caps if c["levelNow"] > c["level"])
    print("страница:", out_path.resolve())
    print("версия:  %s" % version)
    print("стадия:  %s (%s)" % (data["stageNow"]["n"], data["stageNow"]["name"]))
    print("задач:   %d · готово: %d · выбрана: %s" % (len(job_ids), ready, chosen["title"]))
    open_rungs = sum(1 for c, n in chosen["needs"].items() if level[c] < n)
    print("шагов:   %d открытых у выбранной задачи" % open_rungs)
    print("инструкций собрано: %d" % len(links))
    print("оценка:  %s" % ("%s, выросло способностей: %d"
                           % ("по факту" if mode == "factual" else "повторная", grown)
                           if repeat else "первая"))


if __name__ == "__main__":
    main()
