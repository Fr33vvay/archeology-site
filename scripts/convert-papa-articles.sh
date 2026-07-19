#!/usr/bin/env bash
# Конвертация исходников Word/ODT в HTML+картинки на хосте (LibreOffice).
# Результат: каждый документ в своём подкаталоге OUT/<stem>/
set -euo pipefail

SRC="${1:-/tmp/papa-articles}"
OUT="${2:-/tmp/papa-html}"

if ! command -v soffice >/dev/null 2>&1; then
  echo "Нужен LibreOffice (soffice). На Ubuntu: sudo apt-get install -y libreoffice-writer-nogui" >&2
  exit 1
fi

mkdir -p "$OUT"
shopt -s nullglob
files=("$SRC"/*.[Dd][Oo][Cc] "$SRC"/*.[Dd][Oo][Cc][Xx] "$SRC"/*.[Oo][Dd][Tt])
if ((${#files[@]} == 0)); then
  echo "В $SRC нет .doc/.docx/.odt" >&2
  exit 1
fi

for f in "${files[@]}"; do
  base="$(basename "$f")"
  # Пропуски — те же, что в management-команде (точные имена)
  case "$base" in
    "Мои статьи в сети.docx"|"Реставрация Летнего дв. Картинки.doc"|"Харлампий — копия.odt"|"Харлампий - копия.odt")
      echo "SKIP $base"
      continue
      ;;
  esac

  stem="${base%.*}"
  dest="$OUT/$stem"
  mkdir -p "$dest"
  if ls "$dest"/*.html >/dev/null 2>&1; then
    echo "EXISTS $stem"
    continue
  fi
  echo "CONVERT $base → $dest"
  if ! soffice --headless --norestore --convert-to html --outdir "$dest" "$f"; then
    echo "FAIL $base" >&2
    continue
  fi
done

echo "Готово: $OUT"
find "$OUT" -name '*.html' | wc -l
