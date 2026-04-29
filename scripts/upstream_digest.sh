#!/usr/bin/env bash
# upstream_digest.sh — group upstream commits since BASE by directory, so Boss
# can decide what to absorb without reading 682 commit messages.
#
# Usage:
#   scripts/upstream_digest.sh                    # since v2026.4.23 → upstream/main
#   scripts/upstream_digest.sh v2026.4.23         # explicit base, default head
#   scripts/upstream_digest.sh v2026.4.23 v2026.5.1  # explicit base + head
#   scripts/upstream_digest.sh --topic mcp_serve  # only commits touching that path
#
# Read-only. Never modifies refs, never auto-fetches unless --fetch given.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Hermes uses calendar versions (vYYYY.M.D), not semver. v2026.4.23 == "v0.11.0".
BASE="v2026.4.23"
HEAD_REF="upstream/main"
TOPIC=""
DO_FETCH=0

while (( $# > 0 )); do
  case "$1" in
    --fetch) DO_FETCH=1; shift ;;
    --topic) TOPIC="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      if [[ -z "${POS_BASE:-}" ]]; then
        POS_BASE="$1"
      elif [[ -z "${POS_HEAD:-}" ]]; then
        POS_HEAD="$1"
      else
        echo "unexpected arg: $1" >&2
        exit 2
      fi
      shift
      ;;
  esac
done

BASE="${POS_BASE:-$BASE}"
HEAD_REF="${POS_HEAD:-$HEAD_REF}"

if (( DO_FETCH )); then
  echo "==> git fetch upstream --tags"
  git fetch upstream --tags
fi

# Validate refs
if ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  echo "Base ref not found: $BASE" >&2
  echo "Hint: scripts/upstream_digest.sh --fetch  to refresh upstream tags" >&2
  exit 1
fi
if ! git rev-parse --verify "$HEAD_REF" >/dev/null 2>&1; then
  echo "Head ref not found: $HEAD_REF" >&2
  echo "Hint: scripts/upstream_digest.sh --fetch  to refresh upstream/main" >&2
  exit 1
fi

RANGE="${BASE}..${HEAD_REF}"
TOTAL=$(git rev-list --count "$RANGE")

printf "\n\033[1mUpstream digest\033[0m  %s  (%d commits)\n\n" "$RANGE" "$TOTAL"

if (( TOTAL == 0 )); then
  echo "  Nothing to absorb. You're caught up."
  exit 0
fi

if [[ -n "$TOPIC" ]]; then
  printf "Filtered to path: \033[33m%s\033[0m\n\n" "$TOPIC"
  git log --oneline --no-merges "$RANGE" -- "$TOPIC" | head -200
  exit 0
fi

# Group commits by top-level directory of the FIRST file changed.
echo "Grouped by top-level path (first changed file per commit):"
echo

TMP_RAW=$(mktemp)
trap 'rm -f "$TMP_RAW"' EXIT

git log --no-merges --format="%H|%s" "$RANGE" | \
while IFS='|' read -r sha subject; do
  first=$(git show --pretty="" --name-only -1 "$sha" | head -1)
  if [[ -z "$first" ]]; then
    top="(empty)"
  elif [[ "$first" == */* ]]; then
    top="${first%%/*}/"
  else
    top="(root)"
  fi
  printf "%s\t%s\t%s\n" "$top" "${sha:0:9}" "$subject"
done > "$TMP_RAW"

# Count per bucket, sort descending.
BUCKETS=$(awk -F'\t' '{print $1}' "$TMP_RAW" | sort | uniq -c | sort -rn | awk '{print $2"\t"$1}')

while IFS=$'\t' read -r bucket count; do
  [[ -z "$bucket" ]] && continue
  printf "\n  \033[1m%-22s\033[0m %d commits\n" "$bucket" "$count"
  awk -F'\t' -v b="$bucket" '$1 == b {print "    " $2 "  " $3}' "$TMP_RAW" | head -5
  if (( count > 5 )); then
    printf "    ... (%d more — use --topic %s to see all)\n" "$((count - 5))" "$bucket"
  fi
done <<< "$BUCKETS"

echo
echo "Tips:"
echo "  scripts/upstream_digest.sh --topic mcp_serve.py    # see all mcp commits"
echo "  scripts/upstream_digest.sh --topic gateway/         # see all gateway commits"
echo "  git cherry-pick <sha>                              # absorb one"
echo "  scripts/regression_smoke.sh                        # verify after each pick"
