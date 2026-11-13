#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Fehler: Python 3 wurde nicht gefunden." >&2
    exit 1
fi

if ! "$PYTHON" -c "from PySide6.QtWidgets import QApplication; import apt" >/dev/null 2>&1; then
    echo "Fehlende Python-Abhängigkeiten. Bitte zuerst ausführen:" >&2
    echo "sudo apt update" >&2
    echo "sudo apt install python3 python3-apt python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets" >&2
    exit 1
fi

exec "$PYTHON" "$ROOT/lunapaket/main.py" "$@"
