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

## Personal Runbook Index

- 管理后台新增站点/租户/环境配置：当用户说 `三个管理后台都新增`,
  `新增站点`, `新增租户`, `新增环境配置`, `新管理后台`, `旧管理后台`,
  `game-lobby-admin`, `admin-stat`, `ark`, or `ark-admin-cron-vue`, use
  `~/.hermes/skills/software-development/admin-tenant-site-config/SKILL.md` and
  `~/.ai-center/runbooks/admin-tenant-site-config.md`.
- 绑渠道/bind-channel：`~/.hermes/skills/personal/bind-channel/SKILL.md`。
- 业务 skill/runbook（含真实域名、租户号、站点分支）一律住在
  `~/.hermes/skills` / `~/.ai-center`，**禁止**放进本仓库——本 fork 是公开仓库
  （2026-06-10 曾因此泄露过真实域名，已改写历史移除）。

## Branch Topology (this fork)

```
upstream/main                    NousResearch/hermes-agent (read-only)
origin/main                      sunJose/hermes-agent — mirrors upstream/main, untouched
origin/boss/v0.14.x-personal     ← THE working branch. All Boss work goes here.
origin/boss/v0.14.x-personal     legacy, frozen — previous baseline before v0.14 rebuild
```

**Working branch is `boss/v0.14.x-personal`.** Never push to `main` of this fork
unless explicitly instructed — `main` is reserved for tracking upstream during sync.

Current baseline: Hermes Agent **v0.16.0 (2026.6.5)**.

## Sync Strategy: Upstream Baseline + Thin Personal Layer

This fork uses an **"upstream baseline + thin personal layer"** model. Do **not**
cherry-pick upstream commits in bulk. While the personal layer stays thin,
**rebase** it onto `upstream/main` — this is now the validated default
(verified 2026-05: 362 upstream commits, 7 personal commits, zero-conflict
rebase in seconds).

**Never run** `git pull upstream main`, `git merge upstream/main`, or force-push
the working branch without Boss approval.

### First principle: keep the personal layer ≤ 10 commits

"Personal layer" = commits that **must live in the fork long-term** because they
can't be upstreamed, plugin-ized, or externalized. When it exceeds 10 commits,
classify and slim down **before** the next sync:
- **Generalizable fix/capability** → submit a PR to upstream
- **Extensible implementation** → move to a Hermes plugin
- **Workflow / knowledge / personal method** → move to `~/.hermes/skills` or `.ai-center`
- **Business context / private data** → forbidden in the Hermes repo
- **Genuinely fork-only** → squash into few, clear commits

≤ 10 is a forcing function, not a mechanical count — it exists to stop the fork
from growing fat again.

### When to sync — event-driven, not calendar-driven

Sync **only** when one of these triggers fires:
1. **A security patch lands upstream** — sync promptly
   (`git log boss/v0.14.x-personal..upstream/main --grep=security -i`)
2. **Boss wants a specific new feature** — sync on demand
3. **Before adding new code to the personal layer** — rebase onto the latest
   `upstream/main` first, then develop on a clean baseline

**All Hermes crons (incl. `upstream-weekly`) were deliberately disabled by Boss
(confirmed 2026-06-11).** There is no automatic upstream watcher: trigger 1
(security patches) is now **manual-only** — when Boss asks about upgrading, or
periodically when convenient, run
`git fetch upstream && git log boss/v0.14.x-personal..upstream/main --grep=security -i --oneline`
yourself. A digest/report, when one exists, is **observation only** — it does
not mean "go sync." **Do not sync** just because upstream has many new commits,
because a feature looks interesting, or because a calendar interval elapsed.

### Read-only pre-sync evaluation

Before any sync, run a read-only assessment (see `scripts/sync_check.sh` when it
exists):
- Confirm remotes: `origin` = personal fork, `upstream` = NousResearch/hermes-agent
- Confirm working tree is clean (`git status --short --branch`)
- `git rev-list --left-right --count HEAD...upstream/main` — ahead/behind
- Count personal-layer commits (`git rev-list upstream/main..HEAD --count`)
- `git cherry -v upstream/main HEAD` — which local commits upstream already absorbed
- Assess file-overlap risk, especially in the **high-conflict zone** below

### Official sync flow (9 steps)

1. `git fetch upstream origin --prune`
2. Confirm current branch is clean
3. Create a backup branch: `backup/boss-v0.14.x-before-resync-$(date +%Y%m%d-%H%M%S)`
4. Create a **temporary worktree** and try the rebase there first
5. On success, run `bash scripts/regression_smoke.sh` in the temp worktree
6. Then perform the real rebase in the main worktree
7. After the real rebase, run smoke + targeted tests
8. Push **only** after Boss's explicit approval
9. Rebased branch push **must** use `--force-with-lease`; never push to `upstream`

### High-conflict zone (watch on every rebase)

Upstream actively refactors these — any personal patch here is fragile:
- `hermes_cli/main.py` (~13k lines, the argparse entry point)
- `cli.py` (interactive CLI + slash-command dispatch)
- `run_agent.py` (core agent loop)
- `model_tools.py` / tools registry
- `gateway/run.py` (platform command dispatch)
- `hermes_cli/commands.py` (slash-command registry)
- `agent/`, `plugins/`, `hermes_cli/plugins.py`

### CC闭环 integration principle

CC闭环 **lives as a Hermes plugin** at `~/.hermes/plugins/cc-loop/` (external
to this fork). Registers `cc-loop` / `rr` / `review-gate` via
`PluginContext.register_cli_command()`. Zero modification to `hermes_cli/main.py`.

**Routing source of truth:** `/Users/macbook/.ai-center/config/agent-review-routing.yaml`
is the only canonical source for review gates, reviewer aliases, active
primary/fallback reviewer, and temporary cc/cr substitutions. This file keeps
implementation notes only. If the routing policy marks `cc` / Claude Code as
disabled, every local instruction that says `cc`, `Claude`, or `Claude Code`
review routes to the configured replacement reviewer (currently `cr` /
`codex-reviewer`) until that policy changes.

Source files: `~/.hermes/plugins/cc-loop/{plugin.yaml, __init__.py,
review_gate.py, cc_loop.py, rr.py, tests/}`. Plugin's `__init__.py` uses
a tiny `_SubparserAdapter` so the original `add_X_parser(subparsers)`
functions work unchanged when handed a single parser by the loader.

**Reviewer invocation:** `review_gate` reads the routing policy to choose the
active reviewer. For legacy `cc`, it passes `stage` to `_primary_command()`,
which appends stage-specific params:
- `plan_review`: `--tools '' --max-turns 1` (pure judgment on packet)
- `stage_review` / `final_review`: read-only tools + `--max-turns 25`
- `high_risk_review`: read-only tools + `--max-turns 30`
- `HERMES_CC_COMMAND` override still gets these params appended (no silent
  bypass). Unknown stage logs warning and falls back to stage_review default.
For `cr` / `codex-reviewer`, the default command is
`codex --profile cr -a never exec --sandbox read-only --skip-git-repo-check --ephemeral`.
The `cr` profile is stored at `$CODEX_HOME/cr.config.toml` and pins the reviewer
model, reasoning effort, and service tier independently from the global Codex
configuration. `HERMES_CODEX_REVIEWER_COMMAND` is only a base command override
and still gets that read-only envelope appended. The actual reviewer mode used
is recorded in cc_loop manifests as `cc_stage_params=...` for after-the-fact audit.

**Fallback caveat:** when the routing policy falls back to
`hermes --profile reviewer chat -q`, that profile's toolset governs what the
fallback reviewer can do. It is a fallback, not the canonical primary reviewer.

**Fresh-machine restore** — 2 steps, in order:

1. Restore the plugin dir to `~/.hermes/plugins/cc-loop/`. Sources, in
   order of preference:
   - `~/.ai-center/plugins-mirror/cc-loop/` — copy the directory back:
     `cp -a ~/.ai-center/plugins-mirror/cc-loop ~/.hermes/plugins/`
     **Mirror is manual now** (the weekly cron is disabled with all other
     crons): after changing cc-loop, run `scripts/sync_cc_loop_plugin.sh`
     yourself. The plugin dir has its own local git (since 2026-06-11) for
     change history/rollback — but that git lives inside the dir, so it is
     not a disaster-recovery source.
   - Time Machine / Backblaze restore of `~/.hermes/plugins/cc-loop/`
   - Future: dedicated git repo `sunJose/hermes-cc-loop` installable via
     `hermes plugins install` (not built yet; upgrade target when the
     plugin stabilizes or needs sharing)
2. `hermes plugins enable cc-loop` — required because user plugins
   default to **not enabled**.

Verify with `hermes rr --help` and `python -m pytest ~/.hermes/plugins/cc-loop/tests`.

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
| `scripts/regression_smoke.sh` | 30-second smoke test — run after any rebase or risky edit |
| `scripts/upstream_digest.sh` | Summarize upstream commits by directory (baseline tag is stale — see SOP step 5) |
| `scripts/cherry_dep_scan.sh` | Missing-symbol scanner — legacy cherry-pick aid, kept for one-off picks |
| `docs/review-gates/review-packet-templates.md` | CC闭环 review packet templates; repo-safe docs only, while active routing policy lives outside the repo |
| external `~/.hermes/skills/business` + `.ai-center` | Boss's private business skills/data; keep outside this repo |
| `CLAUDE.md` | This file — Boss-specific Claude Code config |

## How Claude Code Should Behave Here

1. **Default to `boss/v0.14.x-personal`** when committing.
2. **grill-me / design-discussion mode** — strong triggers: "grill me", "反驳我",
   "先别写代码", "先别做", "只讨论方案", "这个方案靠谱吗". Stop implementation
   and challenge assumptions, risks, non-goals, and acceptance criteria first.
   Weak triggers like "讨论一下" / "你觉得呢" / "有没有更好的" mean "give a
   recommendation with trade-offs" unless Boss explicitly says not to implement.
   Exit on: OK / 可以 / 继续 / 做吧 / 批准 / 开始 / 干 / 帮我弄 / 按这个来 / 就这样.
   Detailed protocol lives in `~/.ai-center/references/grill-me-protocol.md`.
3. **Default 反驳 mindset even outside grill mode** — Boss's proposals get
   challenged first, not appeased. Same rule as docker/SOUL.md "反驳与挑战".
   Agreement must be justified, not just emitted.
4. **Run smoke test before claiming "done"** for any non-trivial edit. The
   only `fail=0` matters.
5. **Don't auto-`hermes update`** — that pulls upstream silently.
6. **Don't push to `origin/main`**. Push to `origin/boss/v0.14.x-personal`.
7. **When asked "升级 Hermes" or "同步上游"** — follow the **rebase model** in
   "Sync Strategy" above. In short:
   - `git fetch upstream` first; use `git log boss/v0.14.x-personal..upstream/main`
     for the real gap. **Don't trust `scripts/upstream_digest.sh`** (stale tag baseline).
   - Run the read-only pre-sync evaluation; if no trigger fired (security /
     needed feature / pre-development rebase), **do not sync**.
   - Follow the 9-step official sync flow: backup branch → temp-worktree trial
     rebase → smoke → real rebase → smoke + tests → Boss-approved
     `--force-with-lease` push.
   - `scripts/regression_smoke.sh` must show `fail=0` (the Runtime Import Chain
     step catches gateway daemon breakage that bypasses `hermes --version`).
     A `fail` caused only by a worktree lacking its own venv is expected.
   - After push, ask Boss to `hermes gateway restart` (never auto).
   - Update `~/.hermes/skills/personal/upgrade-history/SKILL.md` with the
     new entry (event log lives there, not in MEMORY.md).
8. **MCP bridge is live**: Boss's Claude Code session has `mcp__hermes__*`
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
9. **Skills migration from Helios:** when porting **from Helios specifically**,
   target `skills/<name>/SKILL.md` + entry script and adapt to the
   [agentskills.io](https://agentskills.io) protocol.
   **Project-internal advisor modules (e.g. `a-share-assistant/advisor/`) are
   not Hermes skills** — they follow their owning project's conventions.
   Only create a Hermes skill when the capability is meant to be reusable
   across projects/sessions.
10. **Never** modify `~/.hermes/config.yaml` or `~/.hermes/.env` directly via
    edit tools — those are Boss's runtime config, treat as read-only.

## Working Layers

- **Hermes (runtime)**: Telegram/Discord gateway, cron jobs, long-running automations, cross-session memory.
- **Claude Code (precision dev)**: Targeted features, debugging, code review, skill writing, this file.
- **Codex Pro 20x (bulk dev)**: Large-scope refactors, exhaustive test generation, parallel investigation.
- **Passive consumers (advisor + cron briefs)**: **currently disabled** — Boss
  turned off all Hermes crons (confirmed 2026-06-11; the former set was
  `daily-audit`, `daily-commit`, `upstream-weekly`, `holographic-coldscan`,
  `rule-promotion-review`, `rule-action-brief`). Historical reports remain
  under `~/.ai-center/reports/`. If any are re-enabled, the standing rule
  applies: read-only briefs that **must not write back** to source repos,
  rules, skills, or project state unless a separate human-approved workflow
  explicitly says so.

### CC闭环 Flow

When Boss says “批准 CC闭环” or approves a named multi-step development flow:
1. Read `/Users/macbook/.ai-center/config/agent-review-routing.yaml` first; it is the only source of truth for whether `cc` routes to `cc` or to `cr`.
2. Hermes drafts the plan and acceptance criteria first.
3. Send plan/stage/final review packets to the active primary reviewer from the routing policy.
4. Implement in small slices; after 3-5 completed slices, send a stage review packet.
5. High-risk operations use `high_risk_review` from the routing policy. Even with reviewer approval, git push/force-push, production changes, mass deletion, business-repo commits, and secrets operations still require Boss's explicit approval.
6. Run final verification and final review before reporting done. Do not auto-commit or push unless Boss explicitly approves.

**Operational thresholds:**
- Reviewer availability and fallback are defined in
  `/Users/macbook/.ai-center/config/agent-review-routing.yaml`; do not hardcode
  `cc unavailable` logic here.
- If a fallback reviewer is used and the routing policy requires re-audit,
  record the corresponding `needs_*_reaudit` metadata in the review packet.
- Each stage review packet **≤ 8000 tokens** (target 4000-6000). Over → split.
  Include only: goals/context, completed slices, key diff summary, risks,
  test results, reviewer questions. No full large files, no unrelated logs;
  large diffs reference paths + summaries.

When asked to "let Hermes handle this", consider whether it should be:
- A `hermes cron` schedule (recurring)
- A `hermes webhook` subscription (event-driven)
- A `hermes chat -q ... --max-turns N` one-shot (immediate)

## Pitfalls Already Hit

> Historical 2026-04 pitfalls (origin remote misdirection, uncommitted
> SOUL.md/lockfile) are archived in `~/.hermes/skills/personal/upgrade-history/SKILL.md`.

- Holographic memory's `FactRetriever.search/probe/related/reason/contradict`
  never incremented `retrieval_count` — fixed in personal layer. If you
  see facts whose counter looks "frozen", that's why.
- `hermes mcp serve` is **not** the same as "talking to the Hermes agent" —
  it exposes Hermes's IM bridge to MCP clients. To actually converse with the
  agent, use `hermes chat -q ... -Q` or the gateway/api_server.

---

*Last updated: 2026-05-21 — rebase-model sync strategy + 9-step SOP.
Keep this file under 250 lines — when it grows, prune or split.*
