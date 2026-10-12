#!/usr/bin/env bash
# Compila el articulo LaTeX con tectonic (local) o Docker como respaldo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAPER="$ROOT/paper"
TARGET="${1:-both}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

compile_one() {
  local base="$1"
  echo "=== Compilando $base.tex ==="
  (cd "$PAPER" && tectonic "$base.tex")
  echo "PDF: $PAPER/$base.pdf"
}

case "$TARGET" in
  es|main_es) compile_one main_es ;;
  en|main) compile_one main ;;
  both)
    compile_one main_es
    compile_one main
    ;;
  *)
    echo "Uso: bash paper/compilar.sh [es|en|both]" >&2
    exit 1
    ;;
esac

if [ "$TARGET" = "both" ] || [ "$TARGET" = "es" ]; then
  echo "=== Compilando docs/protocolo_encargado.tex ==="
  (cd "$ROOT/docs" && tectonic protocolo_encargado.tex)
  echo "PDF: $ROOT/docs/protocolo_encargado.pdf"
fi
