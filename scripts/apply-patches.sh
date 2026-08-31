#!/usr/bin/env bash
# Apply the Aurelex deviation patches to the engine/ submodule working tree.
# Contract per AGENTS.md: never edit engine/ in place permanently — each build
# (local or CI) starts from a clean submodule and applies patches/ on top.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$ROOT/engine"

for patch in "$ROOT"/patches/*.patch; do
  [ -e "$patch" ] || continue
  echo "applying $(basename "$patch")"
  git -C "$ENGINE" apply --check "$patch" && git -C "$ENGINE" apply "$patch"
done

echo "patches applied to engine/ (working tree only; not committed)"