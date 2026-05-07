#!/usr/bin/env bash
# cherry_dep_scan.sh — try to import every module touched by a cherry-pick.
#
# Why this exists: regression_smoke.sh imports a fixed set of modules
# (gateway.run, mcp_serve, model_tools). Cherry-picks can break OTHER
# modules — e.g. the 2026-05-07 batch broke gateway.config + gateway.platforms
# .base via missing _BUILTIN_PLATFORM_VALUES / EphemeralReply.
# This script imports each .py file the patch modified, surfacing
# ImportError/NameError before they bite at runtime.
#
# Usage:
#   scripts/cherry_dep_scan.sh                # scan files modified by HEAD vs HEAD~1
#   scripts/cherry_dep_scan.sh <sha>          # scan files modified by <sha> vs <sha>~1
#   scripts/cherry_dep_scan.sh <ref1>..<ref2> # scan all files modified between refs
#
# Boss-specific fork; complements regression_smoke.sh.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ARG="${1:-HEAD~1..HEAD}"

# Resolve to a range. Bare SHA → that commit's diff vs its parent.
if [[ "$ARG" == *..* ]]; then
  RANGE="$ARG"
else
  RANGE="${ARG}~1..${ARG}"
fi

if ! git rev-parse "$RANGE" >/dev/null 2>&1; then
  echo "error: cannot resolve range $RANGE" >&2
  exit 2
fi

# Collect Python files modified in the range (skip deletions, skip tests).
FILES=$(git diff --name-only --diff-filter=AMR "$RANGE" -- '*.py' | grep -v '^tests/' | sort -u)

if [[ -z "$FILES" ]]; then
  echo "no non-test .py files modified in $RANGE"
  exit 0
fi

echo "Importing $(echo "$FILES" | wc -l | tr -d ' ') module(s) modified in $RANGE..."
echo

# Activate venv if present.
if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

ISSUES=0
PASSES=0

while IFS= read -r f; do
  # Map path to dotted module: gateway/run.py → gateway.run
  # Skip top-level scripts that aren't packages (entry-point scripts).
  if [[ "$f" == */* ]]; then
    mod=$(echo "$f" | sed 's|/__init__\.py$||; s|\.py$||; s|/|.|g')
  elif [[ "$f" == *.py ]]; then
    mod=$(echo "$f" | sed 's|\.py$||')
  else
    continue
  fi

  # Skip clearly non-importable files.
  case "$mod" in
    setup|conftest|*-*) continue ;;
  esac

  if python -c "import importlib, sys; sys.path.insert(0, '$REPO_ROOT'); importlib.import_module('$mod')" 2>/tmp/cherry_import_err.$$; then
    PASSES=$((PASSES+1))
  else
    err=$(tail -1 /tmp/cherry_import_err.$$)
    echo "  ✗ $mod  →  $err"
    ISSUES=$((ISSUES+1))
  fi
done <<< "$FILES"

rm -f /tmp/cherry_import_err.$$

echo
if (( ISSUES == 0 )); then
  echo "✓ all $PASSES modules import cleanly"
  exit 0
else
  echo "✗ $ISSUES module(s) failed to import — fix before relying on cherry-pick"
  exit 1
fi
