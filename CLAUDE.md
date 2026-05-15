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
upstream/main                    NousResearch/hermes-agent (read-only)
origin/main                      sunJose/hermes-agent — mirrors upstream/main, untouched
origin/boss/v0.13.x-personal     ← THE working branch. All Boss work goes here.
origin/boss/v0.11.0-personal     legacy, frozen — do not commit here anymore
```

**Working branch is `boss/v0.13.x-personal`.** Never push to `main` of this fork
unless explicitly instructed — `main` is reserved for tracking upstream during sync.

Current baseline: Hermes Agent **v0.13.0 (2026.5.7)**.

## Sync Strategy: Upstream Baseline + Thin Personal Layer

This fork should stay close to `upstream/main`. Prefer periodically rebasing or
rebuilding `boss/v0.13.x-personal` on top of `upstream/main`, then replaying only
the small personal layer required for Boss's runtime.

**Never run** `git pull upstream main`, `git merge upstream/main`, or force-push
the working branch without Boss approval.

**Recommended sync workflow:**

```bash
git fetch upstream origin --prune
backup="backup/boss-v0.13.x-before-upstream-$(date +%Y%m%d-%H%M%S)"
git branch "$backup" boss/v0.13.x-personal
git switch -c boss/rebase-test upstream/main
# replay only Boss-specific commits/files, then smoke test
bash scripts/regression_smoke.sh
git push --force-with-lease origin boss/v0.13.x-personal
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
| `scripts/upstream_digest.sh` | Summarize upstream commits by directory (baseline tag is stale — see SOP step 5) |
| `scripts/cherry_dep_scan.sh` | Catches missing-symbol regressions after a cherry-pick batch |
| `docs/review-gates/review-packet-templates.md` | CC闭环 review packet templates; repo-safe docs only, while active routing policy lives outside the repo |
| external `~/.hermes/skills/business` + `.ai-center` | Boss's private business skills/data; keep outside this repo |
| `CLAUDE.md` | This file — Boss-specific Claude Code config |

## How Claude Code Should Behave Here

1. **Default to `boss/v0.13.x-personal`** when committing.
2. **Run smoke test before claiming "done"** for any non-trivial edit. The
   smoke script still warns when the branch isn't `v0.11.0-personal` — that
   warning is expected; only `fail=0` matters.
3. **Don't auto-`hermes update`** — that pulls upstream silently.
4. **Don't push to `origin/main`**. Push to `origin/boss/v0.13.x-personal`.
5. **When asked "升级 Hermes" or "同步上游"** — full SOP:
   - `git fetch upstream` first; **don't trust `scripts/upstream_digest.sh`** (its
     tag baseline is stale; use `git log boss/v0.13.x-personal..upstream/main`
     for the real gap).
   - Group commits by category (security / runtime hot path / Boss-relevant
     provider/Telegram/MCP); ask Boss / HS for pick list.
   - Cherry-pick in **independent worktree** (`git worktree add ../hermes-cherry-N`),
     not in main checkout. Per-commit smoke between each.
   - **After the batch is done, before merging to `boss/v0.13.x-personal`:**
     - `PRE=$(git rev-parse boss/v0.13.x-personal)` → cherry-pick →
     - `scripts/cherry_dep_scan.sh $PRE..HEAD` — catches missing-symbol
       regressions where a fix references a symbol introduced by a
       feature commit we didn't pick (the 2026-05-07 `_BUILTIN_PLATFORM_VALUES` /
       `EphemeralReply` class). Resolve every ✗ before continuing.
     - `bash scripts/regression_smoke.sh` — must show `fail=0`
       (the Runtime Import Chain step is what catches gateway daemon
       breakage that bypasses `hermes --version` / `hermes doctor`).
   - Only after both are green: ff-merge into `boss/v0.13.x-personal` →
     push → ask Boss to `hermes gateway restart` (never auto).
   - Update `~/.hermes/skills/personal/upgrade-history/SKILL.md` with the
     new entry (event log lives there, not in MEMORY.md).
6. **MCP bridge is live**: Boss's Claude Code session has `mcp__hermes__*`
   tools. When Boss asks "问 Hermes ..." or "让 Hermes 分析", route via `messages_send`
   or invoke `hermes chat -q "..." -Q --max-turns N` in Bash.
   **Two hard guardrails** (full cheat sheet: `docs/claude-code-hermes-bridge.md`):
   - `messages_send` 只是把字塞进会话，**不会让 Hermes 思考**。要 Hermes 真动脑必须
     `Bash: hermes chat -q "..." -Q --max-turns N`。
   - `events_wait` 默认 30 秒就空返回。human-in-the-loop 场景必须显式 `timeout_ms>=120000`，
     否则会误判成"Boss 没回"继续往下跑。
   **委派判断**：重复型 → `hermes cron`；事件型 → `hermes webhook`；长跑一次性 →
   `hermes chat ... --max-turns N` + 完成后 `messages_send` 通知；5 秒能查完的事
   Claude Code 自己干，别绕 MCP。
7. **Skills migration from Helios:** when porting a Helios skill, target
   `skills/<name>/SKILL.md` + entry script. Adapt to
   [agentskills.io](https://agentskills.io) protocol.
8. **Never** modify `~/.hermes/config.yaml` or `~/.hermes/.env` directly via
   edit tools — those are Boss's runtime config, treat as read-only.

## Three-Way Workflow (Hermes + Claude Code + Codex)

- **Hermes (runtime)**: Telegram/Discord gateway, cron jobs, long-running automations, cross-session memory.
- **Claude Code (precision dev)**: Targeted features, debugging, code review, skill writing, this file.
- **Codex Pro 20x (bulk dev)**: Large-scope refactors, exhaustive test generation, parallel investigation.

### CC闭环 Flow

When Boss says “批准 CC闭环” or approves a named multi-step development flow:
1. Hermes drafts the plan and acceptance criteria first.
2. Send the plan to cc/Claude for review before implementation.
3. Implement in small slices; after 3-5 completed slices, send a stage review packet to cc. If cc is unavailable, use the reviewer profile only as fallback and mark `needs_cc_reaudit: true`.
4. High-risk operations must be decided by cc/Claude first. If cc is uncertain, escalate to Boss. Even with cc approval, git push/force-push, production changes, mass deletion, business-repo commits, and secrets operations still require Boss's explicit approval.
5. Run final verification and final review before reporting done. Do not auto-commit or push unless Boss explicitly approves.

When asked to "let Hermes handle this", consider whether it should be:
- A `hermes cron` schedule (recurring)
- A `hermes webhook` subscription (event-driven)
- A `hermes chat -q ... --max-turns N` one-shot (immediate)

## Pitfalls Already Hit

- Default git remote `origin` originally pointed at upstream NousResearch — fixed
  2026-04-29: `origin = sunJose/hermes-agent`, `upstream = NousResearch/hermes-agent`.
- Local working tree had uncommitted `docker/SOUL.md` and `web/package-lock.json`
  for an unknown duration — committed to `boss/v0.11.0-personal` 2026-04-29.
- Holographic memory's `FactRetriever.search/probe/related/reason/contradict`
  never incremented `retrieval_count` — fixed 2026-05-14 (`c6cc289b6`). If you
  see facts whose counter looks "frozen" before that commit, that's why.
- `hermes mcp serve` is **not** the same as "talking to the Hermes agent" —
  it exposes Hermes's IM bridge to MCP clients. To actually converse with the
  agent, use `hermes chat -q ... -Q` or the gateway/api_server.

---

*Last updated: 2026-05-14 by Claude Code, on Boss instruction. Keep this file
under 200 lines — when it grows, prune or split.*
