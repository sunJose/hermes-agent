#!/usr/bin/env bash
# regression_smoke.sh — 30-second sanity check after cherry-pick or risky edit.
#
# Exits 0 on green, non-zero on first failure. Designed to be cheap and obvious.
# Boss-specific fork; not intended for upstream PR.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
WARN=0

ok()    { printf "  \033[32m✓\033[0m %s\n" "$1"; PASS=$((PASS+1)); }
fail()  { printf "  \033[31m✗\033[0m %s\n" "$1"; FAIL=$((FAIL+1)); }
warn()  { printf "  \033[33m!\033[0m %s\n" "$1"; WARN=$((WARN+1)); }
step()  { printf "\n\033[1m== %s ==\033[0m\n" "$1"; }

step "Environment"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  ok ".venv activated ($(python --version 2>&1))"
elif [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
  ok "venv activated ($(python --version 2>&1))"
else
  fail "no .venv/ or venv/ found in $REPO_ROOT"
fi

if command -v hermes >/dev/null 2>&1; then
  HERMES_BIN="$(command -v hermes)"
  if [[ "$HERMES_BIN" == "$REPO_ROOT/"* ]]; then
    ok "hermes binary inside repo venv: $HERMES_BIN"
  else
    warn "hermes binary outside repo venv: $HERMES_BIN"
  fi
else
  fail "hermes binary not on PATH"
fi

step "Branch / Identity"

BR=$(git rev-parse --abbrev-ref HEAD)
if [[ "$BR" == "boss/v0.11.0-personal" ]]; then
  ok "on working branch ($BR)"
elif [[ "$BR" == "main" ]]; then
  warn "on main — Boss work should land on boss/v0.11.0-personal"
else
  warn "on non-default branch: $BR"
fi

EMAIL=$(git config user.email 2>/dev/null || true)
if [[ -n "$EMAIL" ]]; then
  ok "git user.email set: $EMAIL"
else
  fail "git user.email not configured"
fi

step "Hermes Smoke"

if hermes --version >/dev/null 2>&1; then
  VER=$(hermes --version 2>&1 | head -1)
  ok "hermes --version: $VER"
else
  fail "hermes --version failed"
fi

# Doctor is comprehensive but slow; allow a few seconds, capture exit, don't be
# fatal on warnings.
if hermes doctor >/tmp/hermes_doctor.$$.log 2>&1; then
  ok "hermes doctor green"
else
  warn "hermes doctor non-zero (see /tmp/hermes_doctor.$$.log)"
fi

# MCP server: just import the module (full stdio loop needs a client).
if python -c "from mcp_serve import create_mcp_server; create_mcp_server()" 2>/dev/null; then
  ok "mcp_serve.create_mcp_server() constructible"
else
  fail "mcp_serve import/construct failed"
fi

# SOUL.md must exist and be Boss's customized version (not the original
# template). Cheap heuristic: look for a Chinese marker.
if [[ -f docker/SOUL.md ]] && grep -q "私人技术秘书\|极致务实\|Hermes 性格" docker/SOUL.md; then
  ok "docker/SOUL.md is Boss's customized persona"
elif [[ -f docker/SOUL.md ]]; then
  warn "docker/SOUL.md exists but doesn't look customized"
else
  fail "docker/SOUL.md missing"
fi

step "Quick Tool Discovery"

# Tool registry sanity: import model_tools and count tools. If this hangs,
# something deep is broken.
TOOL_COUNT=$(python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')
try:
    import model_tools
    n = len(getattr(model_tools, 'discover_builtin_tools', lambda: [])())
    print(n)
except Exception as exc:
    print(f'ERR:{exc}', file=sys.stderr)
    print(0)
" 2>&1 | tail -1)

if [[ "$TOOL_COUNT" =~ ^[0-9]+$ ]] && (( TOOL_COUNT > 0 )); then
  ok "tool discovery returned $TOOL_COUNT tools"
else
  warn "tool discovery returned: $TOOL_COUNT"
fi

step "Runtime Import Chain"

# Force the full gateway daemon import chain. This is what catches the
# "cherry-picked fix references symbol from a feat we didn't pick" class of
# regression — those break gateway.run import but leave hermes --version
# / hermes doctor / mcp_serve unaffected. (See 2026-05-07 regression:
# _BUILTIN_PLATFORM_VALUES + EphemeralReply missing → daemon respawn loop.)
if python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')
from gateway.run import start_gateway  # noqa: F401
from gateway.platforms.api_server import APIServerAdapter  # noqa: F401
from gateway.platforms.base import BasePlatformAdapter  # noqa: F401
" 2>/tmp/import_chain.$$.err; then
  ok "gateway daemon import chain"
else
  fail "gateway daemon import chain ($(tail -1 /tmp/import_chain.$$.err 2>/dev/null))"
fi

# Real CLI exit path. Catches missing import sys / sys.exit-time NameError
# class of regression that doesn't show up in --version / doctor.
# Costs ~3-5s; uses --max-turns 1 with a trivial prompt.
if hermes chat -q "ok" -Q --max-turns 1 >/tmp/chat_smoke.$$.log 2>&1; then
  ok "hermes chat -q exit path clean"
else
  EXIT=$?
  if grep -qE "NameError|ImportError|AttributeError" /tmp/chat_smoke.$$.log; then
    fail "hermes chat -q raised $(grep -oE 'NameError|ImportError|AttributeError' /tmp/chat_smoke.$$.log | head -1) (see /tmp/chat_smoke.$$.log)"
  else
    warn "hermes chat -q exited $EXIT (likely network/credentials, not code)"
  fi
fi
rm -f /tmp/import_chain.$$.err

step "External Business Capability Guard"

AI_CENTER_SMOKE="${AI_CENTER_SMOKE:-/Users/macbook/.ai-center/scripts/smoke_check.sh}"
if [[ -x "$AI_CENTER_SMOKE" ]]; then
  if "$AI_CENTER_SMOKE" >/tmp/ai_center_smoke.$$.json 2>&1; then
    ok ".ai-center smoke_check.sh passed"
  else
    fail ".ai-center smoke_check.sh failed (see /tmp/ai_center_smoke.$$.json)"
  fi
else
  warn ".ai-center smoke_check.sh not found/executable at $AI_CENTER_SMOKE"
fi

step "Summary"

printf "\n  pass=%d  warn=%d  fail=%d\n\n" "$PASS" "$WARN" "$FAIL"

# Cleanup
rm -f /tmp/hermes_doctor.$$.log /tmp/ai_center_smoke.$$.json /tmp/chat_smoke.$$.log

if (( FAIL > 0 )); then
  exit 1
fi
exit 0
