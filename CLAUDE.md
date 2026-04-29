# Hermes (Boss Personal Fork) — Claude Code Project Config

This is a **personal fork** of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent),
maintained by Boss (sunJose) for private use. **Not intended for upstream PRs.**

For canonical Hermes architecture/dev rules, read `AGENTS.md` first.
This file only documents Boss-specific conventions that override or complement it.

---

## Identity & Tone

- **Default language:** 简体中文 in conversation, English in code/comments.
- **Boss's persona for Hermes itself** lives in `docker/SOUL.md` (committed in this fork).
- **Style:** Direct, high-signal, no fluff. Match the SOUL.md tone in conversation.

## Branch Topology (this fork)

```
upstream/main          NousResearch/hermes-agent (read-only, 682+ ahead of v2026.4.23)
origin/main            sunJose/hermes-agent — mirrors upstream/main, untouched
origin/boss/v0.11.0-personal   ← THE working branch. All Boss work goes here.
```

**Working branch is `boss/v0.11.0-personal`.** Never push to `main` of this fork
unless explicitly instructed — `main` is reserved for tracking upstream during sync.

## Sync Strategy: Upstream Baseline + Thin Personal Layer

This fork should stay close to `upstream/main`. Prefer periodically rebasing or
rebuilding `boss/v0.11.0-personal` on top of `upstream/main`, then replaying only
the small personal layer required for Boss's runtime.

**Never run** `git pull upstream main`, `git merge upstream/main`, or force-push
the working branch without Boss approval.

**Recommended sync workflow:**

```bash
git fetch upstream origin --prune
backup="backup/boss-v0.11.0-before-upstream-$(date +%Y%m%d-%H%M%S)"
git branch "$backup" boss/v0.11.0-personal
git switch -c boss/rebase-test upstream/main
# replay only Boss-specific commits/files, then smoke test
bash scripts/regression_smoke.sh
git push --force-with-lease origin boss/v0.11.0-personal
```

Categories worth absorbing from upstream:
1. Security patches (always)
2. Gateway/Telegram, cron, tools/process/terminal fixes
3. Memory/Honcho, sessions, config/secret handling fixes
4. `delegate` / subagent / MCP/browser stability fixes
5. Skills updates as bundled upstream code — while Boss's private business skills remain outside this repo

Keep the personal layer thin:
- `docker/SOUL.md`
- `CLAUDE.md`
- small fork-maintenance scripts under `scripts/`
- no business data, no secrets, no `.ai-center`, no private `~/.hermes/skills/business` copies

## Required Before Any Commit

1. **Activate venv first**: `source venv/bin/activate` (this fork uses `venv/`, not `.venv/`)
2. **Smoke test**: `bash scripts/regression_smoke.sh` — must pass.
3. **No upstream-style sweeping refactors** — small, scoped commits only.
4. **Identity already set locally** to `sunJose <sunleo888888@gmail.com>` — do not
   override unless asked.

## What Lives Where (Boss-Specific Additions)

| Path | Purpose |
|---|---|
| `docker/SOUL.md` | Boss's Hermes persona (zh-CN, Senior AI engineer + private secretary) |
| `scripts/regression_smoke.sh` | 30-second smoke test — run after any cherry-pick or risky edit |
| `scripts/upstream_digest.sh` | Summarize upstream commits since v0.11.0 by directory |
| external `~/.hermes/skills/business` + `.ai-center` | Boss's private business skills/data; keep outside this repo |
| `CLAUDE.md` | This file — Boss-specific Claude Code config |

## How Claude Code Should Behave Here

1. **Default to `boss/v0.11.0-personal`** when committing.
2. **Run smoke test before claiming "done"** for any non-trivial edit.
3. **Don't auto-`hermes update`** — that pulls 682 commits silently.
4. **Don't push to `origin/main`**. Push to `origin/boss/v0.11.0-personal`.
5. **When asked "升级 Hermes" or "同步上游":**
   - First run `scripts/upstream_digest.sh`
   - Show Boss the digest
   - Wait for Boss to point out which commits to absorb
   - Cherry-pick one by one with smoke test between each
6. **MCP bridge is live**: Boss's Claude Code session has `mcp__hermes__*`
   tools. When Boss asks "问 Hermes ..." or "让 Hermes 分析", route via `messages_send`
   or invoke `hermes chat -q "..." -Q --max-turns N` in Bash.
7. **Skills migration from Helios:** when porting a Helios skill, target
   `skills/<name>/SKILL.md` + entry script. Adapt to
   [agentskills.io](https://agentskills.io) protocol.
8. **Never** modify `~/.hermes/config.yaml` or `~/.hermes/.env` directly via
   edit tools — those are Boss's runtime config, treat as read-only.

## Three-Way Workflow (Hermes + Claude Code + Codex)

- **Hermes (runtime)**: Telegram/Discord gateway, cron jobs, long-running automations, cross-session memory.
- **Claude Code (precision dev)**: Targeted features, debugging, code review, skill writing, this file.
- **Codex Pro 20x (bulk dev)**: Large-scope refactors, exhaustive test generation, parallel investigation.

When asked to "let Hermes handle this", consider whether it should be:
- A `hermes cron` schedule (recurring)
- A `hermes webhook` subscription (event-driven)
- A `hermes chat -q ... --max-turns N` one-shot (immediate)

## Pitfalls Already Hit

- Default git remote `origin` originally pointed at upstream NousResearch — fixed
  2026-04-29: `origin = sunJose/hermes-agent`, `upstream = NousResearch/hermes-agent`.
- Local working tree had uncommitted `docker/SOUL.md` and `web/package-lock.json`
  for an unknown duration — committed to `boss/v0.11.0-personal` 2026-04-29.
- `hermes mcp serve` is **not** the same as "talking to the Hermes agent" —
  it exposes Hermes's IM bridge to MCP clients. To actually converse with the
  agent, use `hermes chat -q ... -Q` or the gateway/api_server.

---

*Last updated: 2026-04-29 by Claude Code, on Boss instruction. Keep this file
under 200 lines — when it grows, prune or split.*
