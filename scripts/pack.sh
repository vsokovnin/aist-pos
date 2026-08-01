#!/usr/bin/env bash
# Собирает единицу установки: dist/aist-pos.skill (zip с папкой aist-pos/ внутри).
# Артефакт для отправки человеку — он ставит его в Claude Cowork одним действием.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
name="aist-pos"
version="$(awk -F': *' '/^version:/{print $2; exit}' "$repo/SKILL.md")"
dist="$repo/dist"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

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
ITEMS

find "$stage" -name '.DS_Store' -delete
find "$stage" -name 'aist-pos.config.yaml' -delete

out="$dist/$name.skill"
rm -f "$out"
(cd "$stage" && zip -qr "$out" "$name" -x '*.DS_Store')

echo "версия:  $version"
echo "файл:    $out"
echo "размер:  $(du -h "$out" | cut -f1)"
echo "внутри:  $(unzip -Z1 "$out" | wc -l | tr -d ' ') файлов"
