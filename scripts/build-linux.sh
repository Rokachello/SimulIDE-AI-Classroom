#!/usr/bin/env bash
set -euo pipefail
src_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for ts in "$src_root"/resources/translations/*.ts "$src_root"/resources/translations/qt/*.ts; do
  lrelease "$ts" -qm "$src_root/resources/qm/$(basename "${ts%.ts}").qm"
done
mkdir -p "$src_root/build_AI/objects-build"
cd "$src_root/build_AI/objects-build"
qmake "$src_root/AI.pro" "$@"
make -j"${BUILD_JOBS:-4}"
mkdir -p "$src_root/build_AI/executables/SimulIDE_2.0.0-/data"
cp -R "$src_root/resources/data/." "$src_root/build_AI/executables/SimulIDE_2.0.0-/data/"
