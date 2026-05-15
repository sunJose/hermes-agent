# CC闭环 Core Skills

This is the minimal skill set for the CC闭环 development flow. Do not bulk-import agent-skills; adapt only what improves the Hermes/Codex/Claude loop.

## Core 5

1. Planning and task breakdown
   - Hermes equivalent: `writing-plans`
   - Trigger: named multi-step flow, feature plan, refactor, migration, upgrade.
   - Output: plan, acceptance criteria, risk boundary, review packet.

2. Code review
   - Hermes equivalent: `requesting-code-review` plus `review-gate` / `cc-loop`.
   - Trigger: plan review, stage review after 3-5 slices, final review, high-risk decision.
   - Output: pass/needs changes, blockers, risks, next action.

3. Systematic debugging
   - Hermes equivalent: `systematic-debugging`.
   - Trigger: failing test, unexpected CLI behavior, regression, flaky smoke.
   - Output: reproduction, hypothesis, fix, regression test.

4. Test-driven development
   - Hermes equivalent: `test-driven-development`.
   - Trigger: behavior change or bugfix.
   - Output: failing test first when practical, minimal implementation, passing test.

5. Project context and documentation
   - Hermes equivalent: AGENTS.md / CLAUDE.md / `documentation-and-adrs`.
   - Trigger: project-specific rules, handoff templates, durable workflow conventions.
   - Output: concise context docs, not large prompt dumps.

## Non-goals for v1

- No full agent-skills repository import.
- No automatic skill installer.
- No core-loop integration.
- No autonomous Codex spawning until wrapper behavior is stable and reviewed.
- No business data, secrets, or private `.ai-center` content copied into this repo.

## Governance rule

Before adding any new skill to the core set, check:

1. Does it reduce repeated steering in CC闭环?
2. Does it overlap an existing Hermes skill?
3. Is it safe to load often?
4. Does it have clear trigger conditions and verification steps?
5. Can it stay outside repo as a user/private skill instead?

If uncertain, keep it as a doc reference first, not an active skill.
