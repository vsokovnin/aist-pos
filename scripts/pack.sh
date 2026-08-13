#!/usr/bin/env bash
# Собирает единицу установки: dist/aist-pos.skill (zip с папкой aist-pos/ внутри).
# Артефакт для отправки человеку — он ставит его в Claude Cowork одним действием.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
name="${1:-aist-pos}"   # можно собрать под другим именем: ./scripts/pack.sh aist-pos-fresh
version="$(awk -F': *' '/^version:/{print $2; exit}' "$repo/SKILL.md")"
dist="$repo/dist"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

# Гейт целостности: рубрика — единственный источник правды о составе модели.
# Документы, которые называют другое число, ломают оценку молча — поэтому ломаем сборку громко.
rubric="$repo/rubric/aist-pos-rubric.yaml"
declared_caps="$(awk '/^  capabilities_count:/{print $2; exit}' "$rubric")"
declared_cl="$(awk '/^  clusters_count:/{print $2; exit}' "$rubric")"
real_caps="$(grep -c '^    cluster: ' "$rubric")"
real_cl="$(awk '/^clusters:/{f=1;next} /^capabilities:/{f=0} f && /^  - id: /{n++} END{print n+0}' "$rubric")"
[ "$declared_caps" = "$real_caps" ] || { echo "СБОРКА ОСТАНОВЛЕНА: в рубрике $real_caps способностей, meta обещает $declared_caps"; exit 1; }
[ "$declared_cl" = "$real_cl" ] || { echo "СБОРКА ОСТАНОВЛЕНА: в рубрике $real_cl направлений, meta обещает $declared_cl"; exit 1; }
words="один два три четыре пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать двадцать"
right_word="$(echo "$words" | awk -v n="$real_caps" '{print $n}')"
right_cl_word="$(echo "$words" | awk -v n="$real_cl" '{print $n}')"
for f in "$repo/SKILL.md" "$repo/README.md" "$repo"/docs/*.md "$repo"/workflows/*.md "$repo"/templates/*.md; do
  [ -f "$f" ] || continue
  bad="$(grep -oiE '[0-9]+ +(базов[а-я]* )?(способност[а-я]*|направлени[а-я]*)' "$f" \
        | grep -viE "^($real_caps|$real_cl) " || true)"
  badw="$(grep -oiE '(дв[ае]|тр[иё]х?|четыр[её]х?|пят[ьи]|шест[ьи]|сем[ьи]|восем[ьи]|девят[ьи]|десят[ьи]|одиннадцат[ьи]|двенадцат[ьи]|тринадцат[ьи]|четырнадцат[ьи]|пятнадцат[ьи]|шестнадцат[ьи]) +(базов[а-я]* )?(способност[а-я]*|направлени[а-я]*|вопрос[а-я]*)' "$f" \
        | grep -viE "^($right_word|$right_cl_word)" || true)"
  [ -z "$bad" ] && [ -z "$badw" ] || {
    echo "СБОРКА ОСТАНОВЛЕНА: $(basename "$f") называет другое число: $bad $badw"; exit 1; }
done
echo "гейт: $real_caps способностей, $real_cl направлений — документы согласованы"

# Гейт направлений: поле cluster у способностей — единственный источник принадлежности;
# множество его значений должно совпадать с множеством id направлений в шапке.
python3 - "$rubric" <<'PY' || exit 1
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
head, _, tail = text.partition("capabilities:")
declared = set(re.findall(r"\n  - id: (\w+)\n    title: ", head.partition("clusters:")[2]))
real = set(re.findall(r"\n    cluster: (\w+)", tail))
if declared != real:
    print("СБОРКА ОСТАНОВЛЕНА: направления в шапке и в способностях разошлись")
    only_head = sorted(declared - real)
    only_caps = sorted(real - declared)
    if only_head:
        print("  · только в шапке (нет ни одной способности): %s" % ", ".join(only_head))
    if only_caps:
        print("  · только у способностей (нет в шапке): %s" % ", ".join(only_caps))
    sys.exit(1)
print("гейт: направления согласованы (шапка ≡ множество cluster у способностей)")
PY

# Гейт каталога задач: способности задач существуют в рубрике, требуемые уровни в диапазоне.
python3 - "$repo" <<'PY' || exit 1
import json, re, sys
from pathlib import Path
repo = Path(sys.argv[1])
rubric = (repo / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
caps = set(re.findall(r"^  - id: (\w+)$", rubric, flags=re.M))
data = json.loads((repo / "rubric" / "job-sets.json").read_text(encoding="utf-8"))
groups = {g["id"] for g in data["groups"]}
bad = []
for j in data["jobs"]:
    if j["group"] not in groups:
        bad.append("%s: неизвестная группа %s" % (j["id"], j["group"]))
    if not j.get("needs"):
        bad.append("%s: не указано, что нужно" % j["id"])
    for cap, lvl in j.get("needs", {}).items():
        if cap not in caps:
            bad.append("%s: способности %s нет в рубрике" % (j["id"], cap))
        if not isinstance(lvl, int) or not 1 <= lvl <= 5:
            bad.append("%s: у %s уровень %r вне диапазона 1–5" % (j["id"], cap, lvl))
if bad:
    print("СБОРКА ОСТАНОВЛЕНА: каталог задач разошёлся с рубрикой")
    for b in bad:
        print("  ·", b)
    sys.exit(1)
print("гейт: %d задач, %d требуемых уровней — сходятся с рубрикой"
      % (len(data["jobs"]), sum(len(j["needs"]) for j in data["jobs"])))

# Гейт полноты рекомендаций: у каждой способности есть рецепт перехода на третий уровень
# из трёх полей; там, где задача требует четвёртого, — ещё и рецепт перехода на четвёртый.
need4 = {c for j in data["jobs"] for c, lvl in j["needs"].items() if lvl >= 4}
holes = []
for b in re.split(r"\n  - id: ", "\n" + rubric)[1:]:
    cap = b.split("\n", 1)[0].strip()
    if "\n    cluster: " not in b:
        continue
    steps = dict((m.group(1), m.group(0)) for m in re.finditer(
        r"      (to_L[345]):\n        do: \".*?\"\n        how: \".*?\"\n        done_when: \".*?\"\n", b))
    if "to_L3" not in steps:
        holes.append("%s: нет рецепта на третий уровень (do, how, done_when)" % cap)
    if cap in need4 and "to_L4" not in steps:
        holes.append("%s: задача требует четвёртого уровня, рецепта перехода нет" % cap)
if holes:
    print("СБОРКА ОСТАНОВЛЕНА: рекомендации неполные")
    for h in holes:
        print("  ·", h)
    sys.exit(1)
print("гейт: рецепты полны — у каждой способности «что сделать · как сделать · что считать успехом»")

# Гейт инструкций: у каждого рецепта есть пошаговая инструкция той же формы.
guides = json.loads((repo / "rubric" / "guides.json").read_text(encoding="utf-8"))["guides"]
gaps = []
for b in re.split(r"\n  - id: ", "\n" + rubric)[1:]:
    cap = b.split("\n", 1)[0].strip()
    if "\n    cluster: " not in b:
        continue
    for key in re.findall(r"      (to_L[345]):\n        do: ", b):
        g = guides.get(cap, {}).get(key)
        if not g:
            gaps.append("%s/%s: рецепт есть, пошаговой инструкции нет" % (cap, key))
            continue
        for field in ("title", "why", "before", "steps", "check", "pitfalls", "next"):
            if not g.get(field):
                gaps.append("%s/%s: в инструкции нет поля %s" % (cap, key, field))
        for i, st in enumerate(g.get("steps", []), 1):
            for field in ("do", "see", "fix"):
                if not st.get(field):
                    gaps.append("%s/%s: у шага %d нет поля %s" % (cap, key, i, field))
        if len(g.get("steps", [])) > 7:
            gaps.append("%s/%s: шагов %d — больше семи человек не дочитывает, режьте рекомендацию надвое"
                        % (cap, key, len(g["steps"])))
if gaps:
    print("СБОРКА ОСТАНОВЛЕНА: инструкции неполные")
    for g in gaps:
        print("  ·", g)
    sys.exit(1)
print("гейт: инструкций %d — у каждой рекомендации есть пошаговая"
      % sum(len(v) for v in guides.values()))
PY

# Плейбук собирается в пакет готовой страницей: человек читает его до первой оценки.
python3 "$repo/scripts/make-playbook.py" "$repo/playbook.html" >/dev/null || {
  echo "СБОРКА ОСТАНОВЛЕНА: не собрался плейбук"; exit 1; }
echo "гейт: плейбук собран"

mkdir -p "$dist" "$stage/$name"

# В архив идёт только содержимое навыка: ни .git, ни личных данных, ни артефактов сборки.
while IFS= read -r item; do
  cp -R "$repo/$item" "$stage/$name/"
done <<ITEMS
SKILL.md
README.md
LICENSE
playbook.html
workflows
rubric
templates
assets
config
docs
examples
scripts
ITEMS

# pack.sh — инструмент сборки, человеку он не нужен
rm -f "$stage/$name/scripts/pack.sh"
# имя навыка внутри пакета должно совпадать с именем папки
if [ "$name" != "aist-pos" ]; then
  sed -i '' "s/^name: aist-pos$/name: $name/" "$stage/$name/SKILL.md"
fi
find "$stage" -name '.DS_Store' -delete
find "$stage" -name 'aist-pos.config.yaml' -delete

out="$dist/$name.skill"
rm -f "$out"
(cd "$stage" && zip -qr "$out" "$name" -x '*.DS_Store')

echo "версия:  $version"
echo "файл:    $out"
echo "размер:  $(du -h "$out" | cut -f1)"
echo "внутри:  $(unzip -Z1 "$out" | wc -l | tr -d ' ') файлов"
