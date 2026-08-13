#!/usr/bin/env python3
"""Сертификация матрицы способностей — механические тесты §6 спека
(с поправкой §4.6 от 2026-08-13: три яруса — вход/надёжность/гигиена).

Тесты (нумерация как в задаче, не как в спеке):
  1. Покрытие          — у каждой дыры каталога есть решение.
  2. Минимальность      — каждая способность нужна хотя бы одному ярусу.
  3. Межзадачная согласованность уровней — разные уровни входа трассируются в разные операции.
  4. Целостность лестницы — на каждый требуемый уровень ≥4 (вход или надёжность) есть рецепт.
  5. Уникальность территории — крудая эвристика, никогда не ✗ (см. отчёт).
  6. Смоук — уровень 5 не требуется на входе; профиль «всё на 3» закрывает часть задач.
  7. Сходимость — метрика, не тест: доля ячеек входа, выведенных ≥2 из 3 дериваторов.

Любой ✗ -> exit 1. ⚠/ℹ не проваливают прогон — это находки и метрики для отчёта.
"""
import glob
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT, fail, load_catalog, load_needs  # noqa: E402

RUBRIC = ROOT / "rubric" / "aist-pos-rubric.yaml"
DERIVATION = ROOT / "derivation"
PLACEHOLDER_OP = "(ярус надёжности)"


def _jobs_full():
    return json.loads((ROOT / "rubric" / "job-sets.json").read_text(encoding="utf-8"))


def _recipes():
    text = RUBRIC.read_text(encoding="utf-8")
    blocks = re.split(r"\n  - id: ", "\n" + text.partition("capabilities:")[2])[1:]
    out = {}
    for b in blocks:
        cid = b.split("\n", 1)[0].strip()
        out[cid] = set(re.findall(r"\n      (to_L[345]):", b))
    return out


def norm_op(name):
    return " ".join(name.lower().split())


def test_coverage(data):
    gaps = json.loads((DERIVATION / "catalog-gaps.json").read_text(encoding="utf-8"))["gaps"]
    missing = [g for g in gaps if not g.get("decision")]
    lines = ["дыр каталога: %d, без решения: %d" % (len(gaps), len(missing))]
    for g in missing:
        lines.append("  · #%s (%s/%s) — решения нет" % (g["n"], g["job_id"], g["tier"]))
    return ("1. Покрытие", "✓" if not missing else "✗", lines)


def test_minimality(data):
    jobs, hygiene = data["jobs"], data["hygiene"]
    cat = load_catalog()
    entry, reliability = set(), set()
    for j in jobs:
        entry |= set(j.get("needs", {}))
        reliability |= set(j.get("hardens", {}))
    hyg = set(hygiene["caps"])
    missing, single = [], []
    for c in cat:
        cid = c["id"]
        tiers = []
        if cid in entry:
            tiers.append("вход")
        if cid in reliability:
            tiers.append("надёжность")
        if cid in hyg:
            tiers.append("гигиена")
        if not tiers:
            missing.append(cid)
        elif len(tiers) == 1:
            single.append((cid, tiers[0]))
    lines = ["способностей всего: %d, без яруса: %d" % (len(cat), len(missing))]
    for cid in missing:
        lines.append("  · %s — не встречается ни в одном ярусе" % cid)
    if single:
        lines.append("встречаются только в одном ярусе (%d из %d):" % (len(single), len(cat)))
        for cid, t in single:
            lines.append("  · %s — только %s" % (cid, t))
    return ("2. Минимальность", "✓" if not missing else "✗", lines)


def test_cross_job_levels(data):
    needs = load_needs()
    by_cap = defaultdict(dict)
    for job, nn in needs.items():
        for cap, lvl in nn.items():
            by_cap[cap][job] = lvl
    varying = {c: jl for c, jl in by_cap.items() if len(set(jl.values())) > 1}
    lines = []
    ok = True
    if not varying:
        lines.append("нет способностей с разными уровнями входа у разных задач")
    for cap, jl in sorted(varying.items()):
        lines.append("%s:" % cap)
        for job, lvl in sorted(jl.items()):
            trace = json.loads((DERIVATION / ("%s.json" % job)).read_text(encoding="utf-8"))
            match = [c for c in trace["cells"] if c["cap_id"] == cap and c["level"] == lvl]
            if match:
                lines.append("  · %s:%d ← %s" % (job, lvl, match[0]["operation"]))
            else:
                lines.append("  · %s:%d — операция в трассе не найдена" % (job, lvl))
                ok = False
    return ("3. Межзадачная согласованность уровней", "✓" if ok else "✗", lines)


def _load_accepted_gaps():
    p = DERIVATION / "accepted-gaps.json"
    if not p.exists():
        return {}
    reg = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for e in reg.get("ladder", []):
        out[(e["cap"], e["level"])] = e
    return out


def test_ladder(data):
    jobs = data["jobs"]
    recipes = _recipes()
    accepted = _load_accepted_gaps()
    need_level = defaultdict(dict)
    for j in jobs:
        for cap, lvl in j.get("needs", {}).items():
            if lvl >= 4:
                need_level[cap].setdefault(lvl, []).append(("вход", j["id"]))
        for cap, lvl in j.get("hardens", {}).items():
            if lvl >= 4:
                need_level[cap].setdefault(lvl, []).append(("надёжность", j["id"]))
    lines, warn_lines = [], []
    ok = True
    for cap in sorted(need_level):
        for lvl in sorted(need_level[cap]):
            sources = ", ".join("%s/%s" % (t, j) for t, j in need_level[cap][lvl])
            key = "to_L%d" % lvl
            has = key in recipes.get(cap, set())
            if has:
                lines.append("  ✓ %s L%d (%s) — рецепт %s есть" % (cap, lvl, sources, key))
                continue
            entry = accepted.get((cap, lvl))
            if entry:
                warn_lines.append(
                    "  ⚠ %s L%d (%s) — рецепта %s нет, дыра ПРИНЯТА %s (%s): %s"
                    % (cap, lvl, sources, key, entry["accepted"], entry["decision_by"],
                       entry["why"]))
            else:
                lines.append(
                    "  ✗ %s L%d (%s) — рецепта %s нет, в derivation/accepted-gaps.json не "
                    "зарегистрирована" % (cap, lvl, sources, key))
                ok = False
    lines.extend(warn_lines)
    return ("4. Целостность лестницы", "✓" if ok else "✗", lines)


def test_territory(data):
    op_to_caps = defaultdict(set)
    op_to_hits = defaultdict(list)
    skip = {"findings.json", "attacks.json", "catalog-gaps.json"}
    for p in sorted(DERIVATION.glob("*.json")):
        if p.name in skip:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):   # служебные файлы-списки трассами не являются
            continue
        job = d.get("job_id")
        if not job:
            continue
        for key in ("cells", "hardens_cells"):
            for c in d.get(key, []):
                if c["operation"] == PLACEHOLDER_OP:
                    continue
                n = norm_op(c["operation"])
                op_to_caps[n].add(c["cap_id"])
                op_to_hits[n].append("%s/%s" % (job, c["cap_id"]))
    collisions = {op: caps for op, caps in op_to_caps.items() if len(caps) > 1}
    cross_job = 0
    lines = ["операций всего: %d, легли на >1 способность: %d" % (len(op_to_caps), len(collisions))]
    for op, caps in sorted(collisions.items()):
        jobs_involved = {h.split("/")[0] for h in op_to_hits[op]}
        cross = len(jobs_involved) > 1
        if cross:
            cross_job += 1
        lines.append("  ⚠ «%s» → %s (%s: %s)" % (
            op, sorted(caps), "МЕЖ задачами" if cross else "внутри одной задачи",
            ", ".join(op_to_hits[op])))
    lines.append(
        "из них между разными задачами (проверяемое пересечение территории): %d" % cross_job)
    return ("5. Уникальность территории", "⚠", lines)


def test_smoke(data):
    needs = load_needs()
    lines = []
    ok = True
    lvl5 = sorted(j for j, nn in needs.items() if max(nn.values()) >= 5)
    if lvl5:
        ok = False
        lines.append("  ✗ (а) требуют уровень 5 на пороге входа: %s" % ", ".join(lvl5))
    else:
        lines.append("  ✓ (а) ни одна задача не требует уровня 5 на пороге входа")
    closed = sorted(j for j, nn in needs.items() if max(nn.values()) <= 3)
    mark = "✓" if closed else "✗"
    if not closed:
        ok = False
    lines.append("  %s (б) профиль «все способности на 3» закрывает %d/%d задач: %s" % (
        mark, len(closed), len(needs), ", ".join(closed)))
    need4 = {j: {c: l for c, l in nn.items() if l >= 4}
             for j, nn in needs.items() if max(nn.values()) >= 4}
    lines.append("  (в) задачи, требующие ≥4 на пороге входа: %s" % ", ".join(
        "%s(%s)" % (j, ",".join("%s=%d" % (c, l) for c, l in cl.items()))
        for j, cl in sorted(need4.items())))
    return ("6. Смоук", "✓" if ok else "✗", lines)


def convergence(data):
    needs = load_needs()
    total, converged = 0, 0
    per_job = {}
    for job, nn in sorted(needs.items()):
        files = sorted(glob.glob(str(DERIVATION / "raw" / ("%s-*.json" % job))))
        if len(files) != 3:
            fail("у задачи %s не 3 raw-деривации, а %d" % (job, len(files)))
        runs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
        jc = 0
        for cap in nn:
            votes = sum(1 for r in runs if any(c["cap_id"] == cap for c in r["cells"]))
            total += 1
            if votes >= 2:
                converged += 1
                jc += 1
        per_job[job] = (jc, len(nn))
    pct = 100.0 * converged / total if total else 0.0
    lines = ["сошлось (≥2 из 3 дериваторов независимо вывели способность, уровень не "
              "сверяется): %d/%d (%.1f%%)" % (converged, total, pct)]
    for job, (c, n) in sorted(per_job.items()):
        lines.append("  · %s: %d/%d" % (job, c, n))
    return ("7. Сходимость (метрика, не тест)", "ℹ", lines)


LIMITS = """- **Тест 5 (уникальность территории)** — крудая эвристика: нормализация только
  lowercase + схлопнутые пробелы, без учёта синонимов и перефразировок. Намеренно
  никогда не ✗ (по заданию); реальная проверяемая находка — коллизии МЕЖДУ разными
  задачами, они посчитаны отдельно внутри раздела. Совпадения операций внутри одной
  задачи на несколько способностей — ожидаемая норма (одна операция кормит несколько
  ячеек сразу), не дефект.
- **Тесты 3 и 4 из §6 спека (межзадачная согласованность уровней и согласованность
  с грамматикой ступеней)** — в спеке помечены «полумеханический» и «агентный»:
  здесь закрыта только механическая часть (сверка с трассой); содержательное
  agentic-ревью — в Task 13 («проход по 18»).
- **Психометрия исключена из охвата** — сертификация проверяет внутреннюю
  согласованность матрицы (трассируемость, полноту рецептов, отсутствие дыр без
  решения), не психометрическую валидность шкал (надёжность, дискриминантность
  и т.п.) — методология сама называет это границей (см. §5.3 спека, раздел
  «границы применимости»).
- **Сходимость (пункт 7)** — публикуемая метрика, а не критерий приёмки; порог
  «сколько процентов достаточно» спек не задаёт.
"""


def render_report(date, results, conv):
    out = ["# Сертификация матрицы способностей", "", "Дата: %s" % date, ""]
    any_fail = any(r[1] == "✗" for r in results)
    out.append("Итог: %s" % ("ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ" if any_fail else "все механические тесты зелёные"))
    out.append("")
    for title, verdict, lines in results + [conv]:
        out.append("## %s — %s" % (title, verdict))
        out.append("")
        out.extend(lines)
        out.append("")
    out.append("## Принятые дыры")
    out.append("")
    out.append("Реестр: `derivation/accepted-gaps.json`. Зарегистрированная дыра лестницы "
                "печатается в тесте 4 как ⚠ и не роняет сертификацию; дыра вне реестра — ✗.")
    out.append("")
    accepted = _load_accepted_gaps()
    if accepted:
        for (cap, lvl), e in sorted(accepted.items()):
            out.append("- **%s L%d** (задачи: %s) — принято %s, %s" % (
                cap, lvl, ", ".join(e["jobs"]), e["accepted"], e["decision_by"]))
            out.append("  %s" % e["why"])
    else:
        out.append("реестр пуст")
    out.append("")
    out.append("## Ограничения проверки")
    out.append("")
    out.append(LIMITS)
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) != 2:
        fail("нужна дата отчёта: python3 scripts/audit/certify.py YYYY-MM-DD")
    date = sys.argv[1]
    data = _jobs_full()

    results = [
        test_coverage(data),
        test_minimality(data),
        test_cross_job_levels(data),
        test_ladder(data),
        test_territory(data),
        test_smoke(data),
    ]
    conv = convergence(data)

    for title, verdict, lines in results + [conv]:
        print("\n%s %s" % (verdict, title))
        for l in lines:
            print(l)

    out_path = DERIVATION / "certification-report.md"
    out_path.write_text(render_report(date, results, conv), encoding="utf-8")
    print("\nотчёт: %s" % out_path.relative_to(ROOT))

    if any(r[1] == "✗" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
