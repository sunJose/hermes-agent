# Review Packet Templates

These templates are the stable handoff format for CR review gates, including
the legacy `CC闭环` command alias. They are intentionally small and mirror the
active review routing policy. In Boss's local setup the policy is stored
outside the repo, typically at
`~/.ai-center/config/agent-review-routing.yaml`; keep repo docs free of private
data and machine-specific absolute paths.

## Routing rules

- Primary reviewer: `cr` / `codex-reviewer`.
- `cc`, `Claude`, and `Claude Code` are legacy input aliases that resolve to
  `cr`; they do not invoke Claude.
- Fallback reviewer: Hermes `reviewer` profile only when `cr` is unavailable or
  within the configured fallback window.
- Any fallback review must include `needs_cr_reaudit: true` so final
  verification can detect whether `cr` still needs to re-check it.
- High-risk operations require a `cr` decision first. If `cr` returns
  `uncertain`, escalate to Boss instead of proceeding.
- Even with `cr` approval, git push/force-push, production changes, mass
  deletion, business-repo commits, and secrets operations still require Boss
  explicit approval.

## plan_review

Use before implementation starts.

Required fields:
- `task_goal`: What the flow is trying to accomplish.
- `context_summary`: Relevant repo, branch, current dirty files, policy/config facts.
- `implementation_plan`: Ordered implementation slices and checkpoints.
- `acceptance_criteria`: Exact conditions required before calling the task done.
- `risk_boundary`: Allowed actions, cr-required actions, Boss-required actions.

Suggested prompt:

```text
请只读审查这个实施计划。重点判断：目标是否清晰、顺序是否正确、验收是否可测、是否过度设计、风险边界是否足够。输出：通过/需修改、阻塞问题、建议修改、是否允许进入实现、高风险判断。
```

## stage_review

Use after 3-5 completed implementation slices. A round means a small verifiable task that produced code/doc changes and ran its relevant check; pure reading or analysis does not count.

Required fields:
- `task_goal`: Original approved flow goal.
- `completed_rounds`: Count and short list of completed slices.
- `changed_files`: File list with create/modify/delete markers.
- `key_diff_summary`: Important behavior and design changes.
- `tests_run`: Commands and results.
- `known_risks`: Remaining risks, assumptions, fallback reviewer notes,
  `needs_cr_reaudit` if applicable.

Suggested prompt:

```text
请只读审查阶段成果。重点判断：是否偏离已批准 plan、是否引入风险、测试是否足够、是否允许继续下一批 3-5 轮。高/中风险问题请列为阻塞项。
```

## final_review

Use before final user-facing delivery.

Required fields:
- `task_goal`: Original approved flow goal.
- `acceptance_criteria`: Checklist with pass/fail status.
- `changed_files`: Final file list.
- `final_diff_summary`: Final behavior summary.
- `verification_results`: Tests, smoke checks, compile checks, review outputs.
- `unresolved_risks`: Open issues, fallback reviews needing `cr` re-audit, and
  anything requiring Boss decision.

Suggested prompt:

```text
请只读终审。判断是否满足验收标准，是否存在阻塞风险，是否可以向 Boss 报告完成。若 fallback reviewer 曾介入，请确认 needs_cr_reaudit 是否已处理。
```

## high_risk_review

Use before high-risk actions, even if the rest of the flow is approved.

Required fields:
- `operation`: Exact proposed high-risk action.
- `affected_files_or_systems`: Files, services, repos, configs, user data, or external systems affected.
- `why_needed`: Why the action is necessary and why safer alternatives are insufficient.
- `rollback_plan`: How to undo or recover.
- `cr_decision_requested`: Specific yes/no/uncertain decision requested from
  `cr`.

Decision semantics:
- `allow`: Hermes may proceed if the action does not also require Boss explicit approval.
- `deny`: Hermes must stop or choose a safer alternative.
- `uncertain`: escalate to Boss; do not proceed by default.

Suggested prompt:

```text
请只读评估这个高风险操作。必须输出 allow / deny / uncertain 三选一，并说明理由、必要性、替代方案、回滚计划是否足够。若判断 uncertain，请明确升级给 Boss，不要默认放行。
```
