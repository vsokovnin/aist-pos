# План исполнения аудита модели AIST POS

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Провести аудит модели (13 задач × 18 способностей × 5 уровней) по спеку: слепая передеривация матрицы, грамматика ступеней, защита скоринга, публичная методология, механические гейты.

**Architecture:** Детерминированные скрипты (стдлиб-python, идиома репозитория: самопроверка + `fail()`) делают всё воспроизводимое: входы, сверку, сертификацию, гейты. Агентные Workflow делают только то, что требует суждения: деривация, судейство, атаки. Каждая правка контента модели проходит STOP-гейт решения Виктора (propose-before-promotion).

**Tech Stack:** Python 3 stdlib (без PyYAML — проверено, его нет), Workflow structured outputs, bash-гейты в `scripts/pack.sh`.

**Spec:** `specs/2026-08-13-model-audit-design.md`

## Global Constraints

- Язык пользовательского слоя — по `docs/glossary.md` (термины «Пользователю», запрещённые не печатать).
- Python — только stdlib; машинные файлы деривации — **JSON** (`derivation/*.json`), не YAML: PyYAML в системе нет. Это поправка спека (§9 спека говорил `.yaml`) — вносится Task 1.
- Контент модели (`rubric/*`, `docs/*`) меняется только после решения Виктора; шаги STOP помечены явно — исполнитель останавливается и ждёт.
- После каждой контентной правки `./scripts/pack.sh` обязан оставаться зелёным (это общий тест-харнес репо).
- Коммит в конце каждой задачи; пуша и релиза нет без явного слова Виктора.
- `derivation/`, `specs/` НЕ добавлять в `ITEMS` пакета (`scripts/pack.sh:124-139`) — они не для пользователя.
- Числа «13 задач», «18 способностей» могут измениться по ходу; тексты держит существующий числовой гейт `pack.sh:22-34` — при смене чисел он сам укажет файлы для правки.

---

### Task 1: Входы аудита — `scripts/audit/inputs.py`

**Files:**
- Create: `scripts/audit/inputs.py`
- Modify: `specs/2026-08-13-model-audit-design.md` (поправка `.yaml`→`.json` в §9)

**Interfaces:**
- Produces: `load_jobs() -> list[dict(id,title,short,promise)]` (без `needs`!), `load_needs() -> dict[job_id][cap_id]=level`, `load_catalog() -> list[dict(id,title,levels{1..5})]`. Их используют Task 4, 5, 8, 10.

- [ ] **Step 1: Написать скрипт с самопроверкой**

```python
#!/usr/bin/env python3
"""Входы аудита: задачи без needs, текущая матрица, каталог способностей.

Единственный парсер входов — merge/certify/workflow берут данные отсюда,
чтобы правила чтения рубрики не разъехались по файлам.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def fail(msg):
    sys.exit("ОШИБКА: " + msg)


def _jobs_raw():
    return json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))["jobs"]


def load_jobs():
    """Задачи для слепой деривации — поле needs отрезано намеренно."""
    jobs = [{k: j[k] for k in ("id", "title", "short", "promise")} for j in _jobs_raw()]
    if not jobs:
        fail("каталог задач пуст")
    return jobs


def load_needs():
    return {j["id"]: dict(j["needs"]) for j in _jobs_raw()}


def load_catalog():
    text = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    declared = int(re.search(r"\n  capabilities_count: (\d+)", text).group(1))
    caps = []
    for block in re.split(r"\n  - id: ", "\n" + text.partition("capabilities:")[2])[1:]:
        cid = block.split("\n", 1)[0].strip()
        title = re.search(r'\n    title: "(.*?)"', block)
        levels = dict(re.findall(r'^      (L[1-5]): "(.*)"$', block, re.M))
        if not (title and len(levels) == 5):
            fail("способность %s неполна (title или не 5 уровней)" % cid)
        caps.append({"id": cid, "title": title.group(1),
                     "levels": {i: levels["L%d" % i] for i in range(1, 6)}})
    if len(caps) != declared:
        fail("способностей %d, meta обещает %d" % (len(caps), declared))
    return caps


if __name__ == "__main__":
    jobs, needs, cat = load_jobs(), load_needs(), load_catalog()
    ids = {c["id"] for c in cat}
    for j, nn in needs.items():
        for cap in nn:
            if cap not in ids:
                fail("в needs задачи %s способность %s, которой нет в рубрике" % (j, cap))
    if any("needs" in j for j in jobs):
        fail("needs просочился в слепые входы")
    print("%d задач · %d способностей · матрица согласована" % (len(jobs), len(cat)))
```

- [ ] **Step 2: Прогнать самопроверку**

Run: `python3 scripts/audit/inputs.py`
Expected: `13 задач · 18 способностей · матрица согласована`

- [ ] **Step 3: Поправить спек: `derivation/{job}.yaml` → `derivation/{job}.json`** (§2 таблица и §9; причина — stdlib-only, зафиксирована в Global Constraints).

- [ ] **Step 4: Commit**

```bash
git add scripts/audit/inputs.py specs/2026-08-13-model-audit-design.md
git commit -m "аудит: парсер входов (задачи без needs, каталог, матрица); спек: json вместо yaml"
```

---

### Task 2: Расхождение направлений — STOP + гейт

**Files:**
- Modify: `rubric/aist-pos-rubric.yaml` (одна строка — какая, решит Виктор)
- Modify: `scripts/pack.sh` (новый гейт после строки 34)

- [ ] **Step 1: STOP — вопрос Виктору.** «Подключение сервисов» (`connectors`): в списке направления «Входящие и связи» (`rubric/aist-pos-rubric.yaml:21`), а в самой способности `cluster: files` (`:150`) — «Файлы, структура, доступ». Сборщики читают поле `cluster`, значит фактически способность живёт в «Файлах». Спросить: оставить в «Файлах» (поправить `:21`) или вернуть во «Входящие» (поправить `:150`)? Ждать ответа, не выбирать самому.

- [ ] **Step 2: Применить решение** — поправить одну строку в рубрике.

- [ ] **Step 3: Добавить гейт направлений в `pack.sh`** после существующего числового гейта (после строки `echo "гейт: $real_caps способностей..."`):

```bash
# Гейт направлений: списки caps[] в шапке совпадают с полем cluster по содержанию.
python3 - "$rubric" <<'PY' || exit 1
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
head, _, tail = text.partition("capabilities:")
declared = {m.group(1): {c.strip() for c in m.group(2).split(",")}
            for m in re.finditer(r"- id: (\w+)\n    title: .*\n    caps: \[(.*?)\]", head)}
real = {}
for b in re.split(r"\n  - id: ", "\n" + tail)[1:]:
    cid = b.split("\n", 1)[0].strip()
    m = re.search(r"\n    cluster: (\w+)", b)
    if m:
        real.setdefault(m.group(1), set()).add(cid)
if declared != real:
    print("СБОРКА ОСТАНОВЛЕНА: направления в шапке и в способностях разошлись")
    for cl in sorted(set(declared) | set(real)):
        d, r = declared.get(cl, set()), real.get(cl, set())
        if d != r:
            print("  · %s: в шапке %s, по полю cluster %s" % (cl, sorted(d), sorted(r)))
    sys.exit(1)
print("гейт: направления согласованы (шапка ≡ поле cluster)")
PY
```

- [ ] **Step 4: Проверить гейт дважды.** `./scripts/pack.sh` → зелёный. Затем временно вернуть старую строку рубрики → `./scripts/pack.sh` → «СБОРКА ОСТАНОВЛЕНА… разошлись» → вернуть правку.

- [ ] **Step 5: Commit**

```bash
git add rubric/aist-pos-rubric.yaml scripts/pack.sh
git commit -m "аудит: направление connectors по решению Виктора; гейт содержания направлений"
```

---

### Task 3: Критерий отбора задач (Ф0) — STOP

**Files:**
- Create: `derivation/criterion.md` (позже уедет разделом в `docs/methodology.md`, Task 16)

- [ ] **Step 1: Обратный ход из 13 задач.** Прочитать все `promise` из `rubric/job-sets.json` и написать черновик критерия: (а) формула включения — «повторяющаяся рабочая задача руководителя, выполнение которой частично или полностью поручается агенту»; (б) 3–5 признаков отсечения, выведенных из фактического состава (не разовый проект; есть наблюдаемый результат-артефакт; повторяемость ≥ раз в квартал; исполнима связкой человек+агент без найма людей); (в) для каждой из 13 задач — одна строка «проходит критерий, потому что…». Признаки выводить из реального списка, не из головы.

- [ ] **Step 2: STOP — критерий Виктору.** Показать черновик целиком, спросить правки. Ждать. Применить правки.

- [ ] **Step 3: Commit**

```bash
git add derivation/criterion.md
git commit -m "аудит Ф0: критерий отбора задач в каталог (утверждён Виктором)"
```

---

### Task 4: Слепая деривация — Workflow и прогон

**Files:**
- Create: `scripts/audit/derive-workflow.js` (текст Workflow-скрипта; исполняется тулом Workflow с `scriptPath`)
- Create: `derivation/raw/{job}-{1,2,3}.json` × 13 задач (результаты)

**Interfaces:**
- Consumes: `inputs.py` (Task 1) — исполнитель готовит `args` так: `python3 -c "import json,sys; sys.path.insert(0,'scripts/audit'); import inputs; print(json.dumps({'jobs': inputs.load_jobs(), 'catalog': inputs.load_catalog()}, ensure_ascii=False))"`
- Produces: файлы raw-дериваций схемы `{job_id, agent_n, operations[], cells[], gaps[]}` — их читают Task 5, 8, 10.

- [ ] **Step 1: Написать Workflow-скрипт**

```javascript
export const meta = {
  name: 'blind-derive',
  description: 'Слепая деривация задач: операции -> способности -> сценарии отказа',
  phases: [{ title: 'Derive', detail: '3 независимых агента на задачу' }],
}
// args: {jobs: [{id,title,short,promise}], catalog: [{id,title,levels}]}
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['job_id', 'operations', 'cells', 'gaps'],
  properties: {
    job_id: { type: 'string' },
    operations: { type: 'array', minItems: 2, items: { type: 'object', additionalProperties: false,
      required: ['name', 'input', 'output'],
      properties: { name: { type: 'string' }, input: { type: 'string' }, output: { type: 'string' } } } },
    cells: { type: 'array', minItems: 1, items: { type: 'object', additionalProperties: false,
      required: ['operation', 'cap_id', 'level', 'failure_scenario'],
      properties: { operation: { type: 'string' }, cap_id: { type: 'string' },
        level: { type: 'integer', minimum: 1, maximum: 5 },
        failure_scenario: { type: 'string', minLength: 40 } } } },
    gaps: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['operation', 'missing', 'failure_scenario'],
      properties: { operation: { type: 'string' }, missing: { type: 'string' },
        failure_scenario: { type: 'string', minLength: 40 } } } },
  },
}
const catalogText = args.catalog.map(c =>
  `- ${c.id} «${c.title}»\n` + [1, 2, 3, 4, 5].map(i => `  уровень ${i}: ${c.levels[i]}`).join('\n')
).join('\n')
const prompt = (j) => `Ты аудитор модели зрелости. Задача руководителя, которую он хочет поручить ИИ-агенту:

«${j.title}» — ${j.short}
Обещание задачи: ${j.promise}

Каталог из ${args.catalog.length} способностей с уровнями 1-5 (ЗАКРЫТЫЙ словарь):
${catalogText}

Сделай строго три вещи.
1. Разложи задачу на наблюдаемые операции (шаги с входом и выходом). Не абстракции: у каждого шага видно, что взяли и что получили.
2. Для каждой операции укажи, какие способности каталога и на каком МИНИМАЛЬНОМ уровне ей нужны. К каждой ячейке — сценарий отказа: «без способности X на уровне N этот шаг ломается вот так» — конкретно, с наблюдаемым последствием для руководителя. Уровень бери из формулировок каталога: требуемое поведение должно быть написано в формулировке этого уровня, не выше и не ниже.
3. Если операция не покрывается НИКАКОЙ способностью каталога — не изобретай новую, зафиксируй в gaps со сценарием отказа.

Правила: минимальность (не требуй уровень 4, если операции хватает 3); никаких способностей «на всякий случай» — только со сценарием отказа; job_id="${j.id}".`
const runs = await parallel(args.jobs.flatMap(j =>
  [1, 2, 3].map(n => () =>
    agent(prompt(j), { label: `derive:${j.id}#${n}`, phase: 'Derive', schema: SCHEMA })
      .then(r => ({ ...r, agent_n: n })))))
return runs.filter(Boolean)
```

- [ ] **Step 2: Пилот — одна задача.** Вызвать Workflow с `scriptPath` и `args = {jobs: [первая задача], catalog: [...]}`. Проверить глазами: операции наблюдаемые (не «понять контекст», а «собрать встречи из календаря на сегодня»), сценарии отказа конкретные, уровни сослатся на формулировки. Кривой формат → поправить промпт, повторить пилот.

- [ ] **Step 3: Полный прогон батчами по 4–5 задач** (3 вызова Workflow; 12–15 агентов на вызов). Каждый результат сохранить: `derivation/raw/{job_id}-{agent_n}.json` (`json.dump(..., ensure_ascii=False, indent=2)`).

- [ ] **Step 4: Проверка полноты.** `ls derivation/raw | wc -l` → 39 (13×3); скриптом убедиться, что все `cap_id` в файлах ∈ каталогу (иначе агент нарушил словарь — перегнать эту задачу).

- [ ] **Step 5: Commit**

```bash
git add scripts/audit/derive-workflow.js derivation/raw
git commit -m "аудит Ф1: слепые деривации 13 задач, по 3 независимых агента"
```

---

### Task 5: Сверка — `scripts/audit/merge.py`

**Files:**
- Create: `scripts/audit/merge.py`
- Create: `derivation/findings.json` (результат)

**Interfaces:**
- Consumes: `inputs.load_needs()`, файлы `derivation/raw/*.json`.
- Produces: `derivation/findings.json` — список `{n, job_id, cap_id|null, cls, votes, levels_seen, needs_level, scenarios[], verdict:null, rationale:null, decision:null}`, `cls ∈ {missing, extra, level, gap}`. Читают Task 6, 7.

- [ ] **Step 1: Написать merge.py**

```python
#!/usr/bin/env python3
"""Сверка слепых дериваций с текущей матрицей -> очередь находок.

Правила (спек §4.2, уточнение: кандидат «не хватает» при поддержке >=2 из 3,
а не только 3 из 3 — двое независимых заслуживают разбора судьёй):
  missing: >=2 агентов вывели способность, в needs её нет
  extra:   в needs есть, не вывел ни один
  level:   в needs есть; преобладающий уровень агентов != уровню needs
  gap:     агент зафиксировал операцию вне каталога
Уровень агента по способности = max по его ячейкам этой способности.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail, load_needs  # noqa: E402

RAW = ROOT / "derivation" / "raw"


def agent_levels(runs, cap):
    out = []
    for r in runs:
        lv = [c["level"] for c in r["cells"] if c["cap_id"] == cap]
        if lv:
            out.append(max(lv))
    return out


def scenarios(runs, cap):
    return [c["failure_scenario"] for r in runs for c in r["cells"] if c["cap_id"] == cap]


def main():
    needs = load_needs()
    findings = []
    for job_id in sorted(needs):
        files = sorted(RAW.glob("%s-*.json" % job_id))
        if len(files) != 3:
            fail("у задачи %s не 3 деривации, а %d" % (job_id, len(files)))
        runs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
        derived = {c["cap_id"] for r in runs for c in r["cells"]}
        for cap in sorted(derived - set(needs[job_id])):
            lv = agent_levels(runs, cap)
            if len(lv) >= 2:
                findings.append(dict(job_id=job_id, cap_id=cap, cls="missing",
                                     votes=len(lv), levels_seen=lv, needs_level=None,
                                     scenarios=scenarios(runs, cap)))
        for cap in sorted(set(needs[job_id]) - derived):
            findings.append(dict(job_id=job_id, cap_id=cap, cls="extra",
                                 votes=0, levels_seen=[], needs_level=needs[job_id][cap],
                                 scenarios=[]))
        for cap in sorted(set(needs[job_id]) & derived):
            lv = agent_levels(runs, cap)
            top, cnt = Counter(lv).most_common(1)[0]
            if cnt >= 2 and top != needs[job_id][cap]:
                findings.append(dict(job_id=job_id, cap_id=cap, cls="level",
                                     votes=len(lv), levels_seen=lv,
                                     needs_level=needs[job_id][cap],
                                     scenarios=scenarios(runs, cap)))
        for r in runs:
            for g in r["gaps"]:
                findings.append(dict(job_id=job_id, cap_id=None, cls="gap",
                                     votes=1, levels_seen=[], needs_level=None,
                                     scenarios=[g["failure_scenario"]],
                                     detail="%s: %s" % (g["operation"], g["missing"])))
    for i, f in enumerate(findings, 1):
        f.update(n=i, verdict=None, rationale=None, decision=None)
    out = ROOT / "derivation" / "findings.json"
    out.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    by = Counter(f["cls"] for f in findings)
    print("находок %d: %s" % (len(findings), dict(by)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Проверка на фикстуре.** До прогона на живых данных: скопировать один настоящий raw-файл трижды в `/tmp`-копию `derivation/raw` c правкой (у копии №3 удалить одну способность из cells, у №2 поднять уровень другой) и убедиться руками, что классы вычислились как ожидалось. Затем прогнать на живых: `python3 scripts/audit/merge.py`.

- [ ] **Step 3: Commit**

```bash
git add scripts/audit/merge.py derivation/findings.json
git commit -m "аудит Ф1: сверка дериваций с матрицей, очередь находок"
```

---

### Task 6: Судьи находок — Workflow

**Files:**
- Create: `scripts/audit/judge-workflow.js`
- Modify: `derivation/findings.json` (заполняются `verdict`, `rationale`)

**Interfaces:**
- Consumes: `findings.json` (Task 5), обещания задач + каталог (Task 1).
- Produces: у каждой находки `verdict ∈ {CONFIRMED, REJECTED}` + `rationale`. Читает Task 7.

- [ ] **Step 1: Написать Workflow судей**

```javascript
export const meta = {
  name: 'judge-findings',
  description: 'Судья по каждой находке: подтверждается ли сценарий отказа',
  phases: [{ title: 'Judge' }],
}
// args: {findings: [...], jobs: {id: {title,short,promise}}, catalog: {cap_id: {title,levels}}}
const VERDICT = {
  type: 'object', additionalProperties: false, required: ['verdict', 'rationale'],
  properties: { verdict: { enum: ['CONFIRMED', 'REJECTED'] }, rationale: { type: 'string', minLength: 60 } },
}
const capText = (id) => {
  if (!id) return '(находка про дыру каталога — способности нет)'
  const c = args.catalog[id]
  return `«${c.title}»\n` + [1, 2, 3, 4, 5].map(i => `уровень ${i}: ${c.levels[i]}`).join('\n')
}
const CLS = {
  missing: 'агенты считают, что задаче нужна способность, которой нет в матрице',
  extra: 'способность есть в матрице, но ни один из трёх агентов её не вывел',
  level: 'преобладающий уровень агентов расходится с уровнем в матрице',
  gap: 'агент считает, что операция задачи не покрыта каталогом способностей',
}
const out = await parallel(args.findings.map(f => () => {
  const j = args.jobs[f.job_id]
  return agent(`Ты судья аудита модели зрелости. Единственный тест: подтверждается ли потребность СЦЕНАРИЕМ ОТКАЗА, согласующимся с обещанием задачи и формулировками уровней. Правдоподобие без сценария = REJECTED.

Задача: «${j.title}» — ${j.promise}
Класс находки: ${f.cls} — ${CLS[f.cls]}
Способность: ${capText(f.cap_id)}
Уровень в матрице: ${f.needs_level ?? '—'} · уровни агентов: ${JSON.stringify(f.levels_seen)} · голосов: ${f.votes}
Сценарии отказа от агентов:
${f.scenarios.map(s => '- ' + s).join('\n') || '- (нет — для extra это норма: способность не вывел никто)'}
${f.detail ? 'Деталь: ' + f.detail : ''}

Для missing/gap: CONFIRMED = хотя бы один сценарий показывает конкретную поломку задачи без этой способности. Для extra: CONFIRMED = способность действительно не нужна (попробуй сам построить сценарий отказа задачи без неё; построил убедительный — REJECTED с этим сценарием в rationale). Для level: CONFIRMED = уровень агентов обоснован формулировкой уровня лучше, чем уровень матрицы.`,
    { label: `judge:${f.n}:${f.job_id}/${f.cap_id ?? 'gap'}`, phase: 'Judge', schema: VERDICT })
    .then(v => ({ n: f.n, ...v }))
}))
return out.filter(Boolean)
```

- [ ] **Step 2: Прогнать, вписать вердикты.** Вызвать Workflow (`args` собрать скриптом из `findings.json` + `inputs.py`); результат вписать в `findings.json` по полю `n`.

- [ ] **Step 3: Commit**

```bash
git add scripts/audit/judge-workflow.js derivation/findings.json
git commit -m "аудит Ф1: вердикты судей по находкам"
```

---

### Task 7: Решения Виктора и применение — STOP + `scripts/audit/apply.py`

**Files:**
- Create: `scripts/audit/apply.py`
- Modify: `derivation/findings.json` (поле `decision`), `rubric/job-sets.json` (поле `needs`)

- [ ] **Step 1: STOP — очередь Виктору.** Показать находки со статусом CONFIRMED (и REJECTED одной строкой каждую — на случай несогласия с судьёй), сгруппировав по задаче: класс, голоса, лучший сценарий отказа, вердикт, обоснование. По каждой спросить решение: принять / отклонить / изменить (для level — какой уровень). Вопросы прозой, порциями по задаче. Записать `decision: {"take": "accept"|"reject", "note": "...", "level": N?}` в `findings.json`. **Находки класса gap и missing, требующие НОВОЙ способности или задачи, — отдельный разговор: они меняют состав модели** (включая красный тест по `git` — спек §8.1); решение Виктора зафиксировать в `findings.json` и, если состав меняется, остановить план и вернуться в brainstorming — это ratchet-условие.

- [ ] **Step 2: Написать и прогнать apply.py**

```python
#!/usr/bin/env python3
"""Применяет решения Виктора из findings.json к rubric/job-sets.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail  # noqa: E402


def main():
    fpath = ROOT / "derivation" / "findings.json"
    findings = json.loads(fpath.read_text(encoding="utf-8"))
    undecided = [f["n"] for f in findings if f["verdict"] == "CONFIRMED" and not f["decision"]]
    if undecided:
        fail("нет решения Виктора по находкам: %s" % undecided)
    jpath = ROOT / "rubric" / "job-sets.json"
    data = json.loads(jpath.read_text(encoding="utf-8"))
    jobs = {j["id"]: j for j in data["jobs"]}
    changed = 0
    for f in findings:
        if not f["decision"] or f["decision"]["take"] != "accept":
            continue
        needs = jobs[f["job_id"]]["needs"]
        if f["cls"] == "missing":
            needs[f["cap_id"]] = f["decision"].get("level") or max(f["levels_seen"])
        elif f["cls"] == "extra":
            needs.pop(f["cap_id"], None)
        elif f["cls"] == "level":
            needs[f["cap_id"]] = f["decision"]["level"]
        elif f["cls"] == "gap":
            continue  # gap меняет состав модели — руками, вне этого скрипта
        changed += 1
    jpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("применено решений: %d" % changed)


if __name__ == "__main__":
    main()
```

Run: `python3 scripts/audit/apply.py && python3 scripts/audit/inputs.py && ./scripts/pack.sh`
Expected: применено N; входы согласованы; pack зелёный (если гейт рецептов упал — матрица теперь требует `to_L4`, которого нет: дописать рецепт в рубрику по образцу существующих `to_L4` и показать Виктору).

- [ ] **Step 3: Commit**

```bash
git add scripts/audit/apply.py derivation/findings.json rubric/job-sets.json rubric/aist-pos-rubric.yaml
git commit -m "аудит Ф1: решения Виктора применены к матрице needs"
```

---

### Task 8: Канонические трассы — Workflow консолидации + валидатор

**Files:**
- Create: `scripts/audit/consolidate-workflow.js`, `scripts/audit/validate-traces.py`
- Create: `derivation/{job}.json` × 13

**Interfaces:**
- Produces: канонический файл на задачу `{job_id, operations[], cells[], decisions:[n,...]}` где `cells` покрывают ровно финальный `needs`. Читают Task 10 и гейт трассировки.

- [ ] **Step 1: Написать Workflow консолидации**

```javascript
export const meta = {
  name: 'consolidate-traces',
  description: 'Каноническая трасса: операции без дублей, ячейки ровно по финальной матрице',
  phases: [{ title: 'Consolidate' }],
}
// args: {jobs: [{job, title, needs, runs: [raw1, raw2, raw3], decisions: [n, ...]}]}
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['job_id', 'operations', 'cells', 'decisions'],
  properties: {
    job_id: { type: 'string' },
    operations: { type: 'array', minItems: 2, items: { type: 'object', additionalProperties: false,
      required: ['name', 'input', 'output'],
      properties: { name: { type: 'string' }, input: { type: 'string' }, output: { type: 'string' } } } },
    cells: { type: 'array', minItems: 1, items: { type: 'object', additionalProperties: false,
      required: ['operation', 'cap_id', 'level', 'failure_scenario'],
      properties: { operation: { type: 'string' }, cap_id: { type: 'string' },
        level: { type: 'integer', minimum: 1, maximum: 5 },
        failure_scenario: { type: 'string', minLength: 40 } } } },
    decisions: { type: 'array', items: { type: 'integer' } },
  },
}
const out = await parallel(args.jobs.map(x => () =>
  agent(`Канонизируй трассу задачи «${x.title}». Состав и уровни ЗАФИКСИРОВАНЫ решениями аудита — не переоценивай их. Финальная матрица needs: ${JSON.stringify(x.needs)}. Номера решений: ${JSON.stringify(x.decisions)} — верни в decisions как есть.

Три независимых деривации (операции и ячейки со сценариями отказа):
${JSON.stringify(x.runs)}

Сделай: (1) слей операции трёх дериваций в один список без дублей — одинаковые по смыслу шаги объедини, имя выбери самое конкретное; (2) для КАЖДОЙ пары способность-уровень из needs выбери лучшую операцию и лучший сценарий отказа из дериваций; если уровень изменён решением и готового сценария под него нет — напиши сценарий сам, строго под формулировку этого уровня; (3) ячеек ровно столько, сколько пар в needs; job_id="${x.job}".`,
    { label: `consolidate:${x.job}`, phase: 'Consolidate', schema: SCHEMA })))
return out.filter(Boolean)
```

Args готовит исполнитель скриптом из `inputs.py` + `findings.json` (runs — содержимое `derivation/raw/{job}-*.json`).

- [ ] **Step 2: Валидатор**

```python
#!/usr/bin/env python3
"""Каноническая трасса согласована с матрицей: cells ≡ needs, сценарии непусты."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail, load_needs  # noqa: E402

for job_id, nn in sorted(load_needs().items()):
    p = ROOT / "derivation" / ("%s.json" % job_id)
    if not p.exists():
        fail("нет канонической трассы %s" % job_id)
    t = json.loads(p.read_text(encoding="utf-8"))
    got = {}
    for c in t["cells"]:
        got[c["cap_id"]] = max(got.get(c["cap_id"], 0), c["level"])
        if len(c["failure_scenario"]) < 40:
            fail("%s/%s: сценарий отказа пуст или куцый" % (job_id, c["cap_id"]))
        opnames = {o["name"] for o in t["operations"]}
        if c["operation"] not in opnames:
            fail("%s/%s: ячейка ссылается на несуществующую операцию" % (job_id, c["cap_id"]))
    if got != nn:
        fail("%s: трасса %s != needs %s" % (job_id, got, nn))
print("трассы согласованы с матрицей: %d задач" % len(load_needs()))
```

- [ ] **Step 3: Прогнать оба.** Workflow батчами → файлы → `python3 scripts/audit/validate-traces.py` → зелёный (красный → перегнать конкретную задачу).

- [ ] **Step 4: Commit**

```bash
git add scripts/audit/consolidate-workflow.js scripts/audit/validate-traces.py derivation/*.json
git commit -m "аудит Ф1: канонические трассы задач, валидатор трасса≡матрица"
```

---

### Task 9: Пас Б — атаки на сведённую матрицу

**Files:**
- Create: `scripts/audit/attack-workflow.js`
- Modify: `derivation/findings.json` (новые находки паса Б), возможно `rubric/job-sets.json`

- [ ] **Step 1: Workflow атак** — по задаче 4 агента-атакующих, у каждого ОДИН вызов из четырёх: чего не хватает / что лишнее / уровень занижен / завышен. Вход: задача + её финальный `needs` + каноническая трасса + каталог. Схема выхода: `{attacks: [{cap_id, claim, failure_scenario_or_counterexample}]}` (пустой список = атака не нашлась — это валидный результат, в промпте сказать прямо: «не выдумывай атаку ради атаки»). 13×4 = 52 агента, батчами по 3–4 задачи.

- [ ] **Step 2: Судья + STOP.** Непустые атаки прогнать через judge-workflow (Task 6, тот же скрипт — атаки конвертируются в находки с `cls` по типу вызова), CONFIRMED — Виктору тем же порядком, что Task 7; решения применить `apply.py`; затронутые трассы перегнать консолидацией (Task 8) и перевалидировать.

- [ ] **Step 3: Commit**

```bash
git add scripts/audit/attack-workflow.js derivation
git commit -m "аудит Ф1: состязательный пас по матрице, решения применены"
```

---

### Task 10: Сертификация — `scripts/audit/certify.py` + гейт трассировки

**Files:**
- Create: `scripts/audit/certify.py`
- Create: `derivation/certification-report.md`
- Modify: `scripts/pack.sh` (гейт трассировки)

- [ ] **Step 1: Написать certify.py** — механические тесты спека §6: 1 (в findings нет `gap` без решения), 2 (каждая способность ∈ ≥1 `needs` — про `git` к этому моменту решение принято в Task 7), 3-механика (для каждой способности с разными уровнями у разных задач — напечатать пары «задача:уровень ← операция из трассы»; это вход агентной проверки Task 12; ✗ только если у пары нет трасс), 5 (переиспользовать логику рецептов: `to_L3` у всех, `to_L4` где needs ≥4 — тот же regex, что в `pack.sh:72-73`), 6 (нормализованное имя операции ↦ ровно одна способность по всем трассам; нормализация: lowercase+trim; коллизии печатать списком — ограничение крудости названо в отчёте), 7 (смоук: нет задач с требованием уровня 5; «все на 3» даёт ≥1 полностью готовую задачу; задачи с 4 перечислены), 8-метрика (доля ячеек финального needs, которую в raw вывели ≥2 агентов). Каждый тест печатает ✓/✗ и детали; любой ✗ → exit 1. Отчёт — в `derivation/certification-report.md` (дату передавать аргументом, в скрипте не генерить).

- [ ] **Step 2: Гейт трассировки в pack.sh** (после гейта направлений):

```bash
# Гейт трассировки: каждая ячейка needs подтверждена канонической трассой.
python3 "$repo/scripts/audit/validate-traces.py" || {
  echo "СБОРКА ОСТАНОВЛЕНА: матрица разошлась с трассами деривации"; exit 1; }
```

- [ ] **Step 3: Прогнать.** `python3 scripts/audit/certify.py 2026-XX-XX && ./scripts/pack.sh` → всё зелёное. Красное → это не сбой плана, а находка: вернуть в соответствующую задачу (7/8/9), решить, перегнать.

- [ ] **Step 4: Commit**

```bash
git add scripts/audit/certify.py scripts/pack.sh derivation/certification-report.md
git commit -m "аудит: сертификация (тесты 1,2,5,6,7 + сходимость), гейт трассировки в сборке"
```

---

### Task 11: Воспроизводимость (тест 8)

**Files:**
- Create: `derivation/raw-rerun/` (2 задачи × 3 агента), раздел в `certification-report.md`

- [ ] **Step 1: Выбрать 2 задачи** с наибольшим числом принятых правок (по `findings.json`) — там воспроизводимость информативнее всего.

- [ ] **Step 2: Перегнать их слепой деривацией** (Task 4 workflow, свежие агенты) → `derivation/raw-rerun/`. Прогнать merge-логику против ОБНОВЛЁННОГО `needs`: пустая очередь находок (или только REJECTED-класс) = матрица воспроизвелась. Непустая — вернуться в Task 7 с новыми находками.

- [ ] **Step 3: Вписать результат в отчёт сертификации, commit**

```bash
git add derivation/raw-rerun derivation/certification-report.md
git commit -m "аудит: повторный слепой прогон двух задач — воспроизводимость матрицы"
```

---

### Task 12: Грамматика ступеней (Ф2) — STOP

**Files:**
- Create: `docs/level-grammar.md`

- [ ] **Step 1: Написать документ.** Содержание (пользовательский слой по глоссарию): семантика ступеней — таблица «ступень → кто действует → что верно»: 1 = руками и в голове, системы нет; 2 = кусочно и без порядка, полагаться нельзя; 3 = заведено и работает: записано/подключено/само выполняется в базовом контуре; 4 = под присмотром: человек видит сбои и правит правило; 5 = самонастройка: система замечает и чинит себя, человек решает только новое. Плюс: форма вопроса — развилка двух исходов, слова вопроса не повторяются в вариантах дословно; таблица территорий — по каждой способности одна фраза «про что» и одна «не про что» (границы, найденные в Ф1 тестом 6, сюда же). Каждый пункт грамматики иллюстрировать одной существующей формулировкой рубрики, которая ей уже соответствует.

- [ ] **Step 2: STOP — Виктору.** Грамматика — конституция рубрики; правки внести, утверждение дословное.

- [ ] **Step 3: Агентная кросс-проверка трасс против грамматики (тесты 3 и 4 спека §6).** Workflow: (тест 3) для каждой пары «одна способность, разные уровни у разных задач» из вывода `certify.py` — судья с трассами обеих задач: различие обосновано разными операциями, или уровни надо выровнять? (тест 4) для каждой ячейки всех канонических трасс — сценарий отказа требует ровно того, что означает ступень её уровня по `docs/level-grammar.md` (сценарий про «само по расписанию» в ячейке уровня 3 = нарушение). Схема выхода — как VERDICT из Task 6, плюс `{job_id, cap_id, kind: 'xjob-level'|'rung'}`. CONFIRMED-находки дописать в `derivation/findings.json` теми же полями — их разбор с Виктором идёт общей пачкой в Task 13 Step 3; правки уровней применяются `apply.py` + перегоном затронутых трасс (Task 8).

- [ ] **Step 4: Commit**

```bash
git add docs/level-grammar.md derivation/findings.json
git commit -m "аудит Ф2: грамматика ступеней (утверждена); кросс-проверка трасс против грамматики"
```

---

### Task 13: Проход по 18 (Ф2) — STOP + гейт эха

**Files:**
- Modify: `rubric/aist-pos-rubric.yaml` (ask/levels по решениям), `scripts/pack.sh` (гейт эха)
- Create: `scripts/audit/echo-check.py`

- [ ] **Step 1: Workflow ревизии** — по способности один агент: вход = блок способности + `docs/level-grammar.md`; выход = `{cap_id, violations: [{where, rule, current, proposed}]}`, где `rule` — пункт грамматики. Правило промпта: «предлагай минимальную правку, сохраняющую голос рубрики; формулировка без нарушения не трогается». 18 агентов, батчами.

- [ ] **Step 2: echo-check.py** — механическая половина проверки:

```python
#!/usr/bin/env python3
"""Эхо вопрос-варианты: общих 2-грамм быть не должно."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT  # noqa: E402


def norm(s):
    s = s.lower().replace("ё", "е")
    return [w for w in re.sub(r"[^а-я0-9 ]", " ", s).split() if len(w) > 2]


def bigrams(ws):
    return set(zip(ws, ws[1:]))


def run():
    text = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    bad = []
    for b in re.split(r"\n  - id: ", "\n" + text.partition("capabilities:")[2])[1:]:
        cid = b.split("\n", 1)[0].strip()
        ask = re.search(r'\n    ask: "(.*?)"\n', b, re.S)
        if not ask:
            continue
        a = bigrams(norm(ask.group(1)))
        for lvl, t in re.findall(r'^      (L[1-5]): "(.*)"$', b, re.M):
            hit = a & bigrams(norm(t))
            if hit:
                bad.append("%s/%s: %s" % (cid, lvl, sorted(hit)))
    if bad:
        print("эхо вопрос-вариант:")
        [print("  ·", x) for x in bad]
        sys.exit(1)
    print("эха нет: вопрос и варианты не делят 2-грамм")


if __name__ == "__main__":
    run()
```

- [ ] **Step 3: STOP — пачка правок Виктору.** Свести находки агентов + echo-check в один список по способностям (для 02 — включить решённое в чате направление: предмет «вводные», не «материалы»; согласование с рецептом). По каждой правке — решение Виктора.

- [ ] **Step 4: Применить, пересобрать, включить гейт.** Правки в рубрику → `python3 scripts/audit/echo-check.py` зелёный → в `pack.sh` строка гейта (`python3 "$repo/scripts/audit/echo-check.py" || exit 1`) → `./scripts/pack.sh` зелёный → пересборки затронутых страниц: `python3 scripts/make-playbook.py playbook.html`, обновить артефакт-страницу опросника (скрипт в скретчпаде сессии).

- [ ] **Step 5: Commit**

```bash
git add rubric/aist-pos-rubric.yaml scripts/audit/echo-check.py scripts/pack.sh playbook.html
git commit -m "аудит Ф2: рубрика приведена к грамматике ступеней, гейт эха в сборке"
```

---

### Task 14: Защита скоринга (Ф3) — STOP

**Files:**
- Create: `derivation/scoring-defense.md` (черновик; финал уедет в methodology, Task 16)

- [ ] **Step 1: Черновик.** Таблица «минимум (CMMI staged) / среднее / медиана»: для каждой — как выглядит выдача для типового профиля новичка (много 1–2, пара 3) и практика (все 3, пара 4); главный аргумент выбора среднего+флага из `rubric/stage-map.yaml:7-10` (первая стадия как приговор = стоп-сигнал для аудитории руководителей); границы округления (профиль 2.5 → стадия 3 — показать, что дробная оценка видна пользователю по `workflows/assess.md:76`); явный ответ на атаку «слабое звено определяет зрелость»: диагностика не потеряна, а перенесена во флаг `weak_link`, который показывается всегда.

- [ ] **Step 2: Состязательная проверка** — Workflow: 3 агента-атакующих (роли: методолог CMMI, психометрист, скептик-практик) атакуют черновик; CONFIRMED-слабости вправить в текст.

- [ ] **Step 3: STOP — Виктору.** Утвердить текст. Commit:

```bash
git add derivation/scoring-defense.md
git commit -m "аудит Ф3: защита скоринга (среднее + флаг слабого звена) против альтернатив"
```

---

### Task 15: Позиционирование (Ф4, ресёрч)

**Files:**
- Create: `derivation/positioning.md`

- [ ] **Step 1: Внешний ресёрч строго через Exa** (правило workspace: веб-ресёрч только Exa, не WebSearch; глубокий — вызовом `Skill exa`). Вопрос ресёрча: «существующие рамки оценки зрелости работы руководителя/личной продуктивности с ИИ-агентами (2024–2026): maturity-модели AI-адопции, personal AI maturity, agentic maturity» + классика (CMMI, ISO/IEC 33000, PKM-модели). Каждое утверждение — со ссылкой.

- [ ] **Step 2: Раздел «чем отличаемся»** — по осям: предмет (личная система руководителя, не организация), деривация (из задач с трассировкой, не экспертный консенсус), проверяемость (сертификационный скрипт публичен), честность границ (самооценка, не измерение). Без претензий на превосходство — только отличия и их причины. Commit:

```bash
git add derivation/positioning.md
git commit -m "аудит Ф4: позиционирование против существующих рамок (exa-ресёрч, с источниками)"
```

---

### Task 16: Методология (Ф4) — сборка + финальный STOP

**Files:**
- Create: `docs/methodology.md`
- Modify: `CHANGELOG.md`, `SKILL.md` (номер версии), артефакт-страница опросника

- [ ] **Step 1: Собрать `docs/methodology.md`** в порядке вопросов эксперта (спек §5.3): критерий задач (из `derivation/criterion.md`) → деривация состава (сжатое описание протокола Ф1 + сходимость из отчёта + ссылка на `derivation/` в репозитории) → грамматика ступеней (ссылка на `docs/level-grammar.md`) → скоринг (из `derivation/scoring-defense.md`) → границы применимости (структурированная самооценка; дословно: «модель не претендует на психометрическую точность — это структурированная самооценка со встроенной проверкой согласованности») → позиционирование (из `derivation/positioning.md`). Язык — пользовательский слой глоссария.

- [ ] **Step 2: Проверить пакетную согласованность.** `./scripts/pack.sh` зелёный (числовой гейт проверит и methodology.md — он в `docs/*.md`); `python3 scripts/audit/certify.py <дата>` зелёный.

- [ ] **Step 3: STOP — финальное ревью Виктора:** methodology.md целиком + отчёт сертификации. Правки внести.

- [ ] **Step 4: Версия и итог.** Поднять версию в `SKILL.md` + строка в `CHANGELOG.md` («аудит модели: трассируемая деривация матрицы, грамматика ступеней, методология, гейты»); пересобрать и обновить артефакт-страницу опросника из финальной рубрики. Релиз/пуш — только по слову Виктора. Commit:

```bash
git add docs/methodology.md CHANGELOG.md SKILL.md
git commit -m "аудит Ф4: публичная методология; версия поднята"
```

---

## Порядок и STOP-точки

Последовательность: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16. Task 3 можно параллелить с 4–6 (не зависит). STOP-точки (решения Виктора): 2 (направление connectors), 3 (критерий), 7 (находки, включая судьбу `git`), 9 (атаки), 12 (грамматика), 13 (правки рубрики), 14 (скоринг), 16 (методология). Изменение состава модели (новая способность/задача) на любой STOP — ratchet: остановка плана, возврат в brainstorming.
