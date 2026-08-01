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
real_cl="$(grep -c '^    caps: \[' "$rubric")"
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

mkdir -p "$dist" "$stage/$name"

# В архив идёт только содержимое навыка: ни .git, ни личных данных, ни артефактов сборки.
while IFS= read -r item; do
  cp -R "$repo/$item" "$stage/$name/"
done <<ITEMS
SKILL.md
README.md
LICENSE
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
