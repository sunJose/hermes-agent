# Codex Handoff Template

Use this template when Hermes hands an approved CC闭环 slice to Codex/cx. Keep it small, explicit, and safe. This is a Markdown template only; v1 does not require schema validation or API integration.

## Handoff packet

```text
flow_name: CC闭环
approved_plan_summary: <one paragraph from the cc-approved plan>
task_slice: <one small verifiable task; avoid bundling unrelated edits>
allowed_files:
  - <exact path or directory>
forbidden_actions:
  - git push / force push
  - production config changes
  - destructive deletes or bulk overwrites
  - secrets reads beyond presence checks
  - business repo commits unless Boss explicitly approves
test_commands:
  - <exact command and expected result>
review_gate_after_rounds: 3-5 completed slices, or immediately before high-risk work
stop_conditions:
  - touching run_agent.py/core loop, gateway, memory, cron, auth, or production config
  - failing tests that are not directly caused by the intended change
  - needing external spend, external messages, push, deployment, or mass deletion
  - ambiguous requirement that changes file scope or safety boundary
expected_output:
  - changed_files
  - key_diff_summary
  - tests_run
  - known_risks
```

## Required Codex behavior

1. Read `AGENTS.md` and `CLAUDE.md` first.
2. Do only the requested slice.
3. Prefer tests before implementation for behavior changes.
4. Run the listed checks.
5. Return a concise implementation report with changed files, commands run, failures, and risks.
6. Do not commit or push unless Boss explicitly approves.
7. If a stop condition is hit, stop and report instead of continuing.

## Hermes follow-up

After Codex returns:

1. Verify changed files and test output independently when possible.
2. Update the stage review packet.
3. After 3-5 completed slices, run `hermes cc-loop --stage stage_review --json <packet>`.
4. Treat cc/reviewer blocking issues as new fix slices before continuing.
