#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/dist"
out="$root/dist/Raycast Script Commands.alfredworkflow"
rm -f "$out"
(
  cd "$root/workflow"
  zip -X -r "$out" info.plist rsc.py
)
echo "$out"
