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

  # Normalize the patch to LF. Engine files are forced LF by engine/.gitattributes
  # (and patches here by the repo .gitattributes), but on Windows core.autocrlf
  # can leave a CRLF patch that fails git apply's exact context match.
  lf_patch=$(mktemp)
  tr -d '\r' < "$patch" > "$lf_patch"

  if ! git -C "$ENGINE" apply --check "$lf_patch"; then
    echo "ERROR: patch $(basename "$patch") does not apply to engine/ (engine submodule at $(git -C "$ENGINE" rev-parse --short HEAD))" >&2
    rm -f "$lf_patch"
    exit 1
  fi
  git -C "$ENGINE" apply "$lf_patch"
  rm -f "$lf_patch"
done

echo "patches applied to engine/ (working tree only; not committed)"
