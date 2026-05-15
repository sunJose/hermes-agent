from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from hermes_cli.review_gate import (
    REVIEW_GATE_STAGES,
    ReviewTarget,
    build_target_command,
    build_review_packet,
    choose_review_target,
    evaluate_review_gate_result,
    is_primary_available,
    is_local_time_between,
    load_review_policy,
    parse_review_output,
)


POLICY = """
version: 1
roles:
  reviewer:
    preferred_profile: reviewer
review_gates:
  plan_review:
    primary: cc
    fallback:
      profile: reviewer
      when:
        - "local_time between 20:00 and 04:00"
        - "cc unavailable or no response"
    required_packet:
      - task_goal
      - implementation_plan
      - acceptance_criteria
reviewer_profile:
  name: reviewer
  can_substitute_cc_between: "20:00-04:00"
"""


def test_is_local_time_between_handles_midnight_wrap() -> None:
    assert is_local_time_between(datetime(2026, 5, 15, 21, 0), "20:00-04:00")
    assert is_local_time_between(datetime(2026, 5, 15, 2, 30), "20:00-04:00")
    assert not is_local_time_between(datetime(2026, 5, 15, 10, 0), "20:00-04:00")


def test_cc_primary_does_not_resolve_to_system_c_compiler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_CC_COMMAND", raising=False)
    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/usr/bin/cc" if name == "cc" else None)

    assert not is_primary_available("cc")


def test_run_target_never_falls_back_to_system_c_compiler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_CC_COMMAND", raising=False)
    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/usr/bin/cc" if name == "cc" else None)
    from hermes_cli.review_gate import ReviewTarget, _run_target

    with pytest.raises(RuntimeError, match="Claude reviewer command is unavailable"):
        _run_target(ReviewTarget("command", "cc", "forced test"), "packet", 1)


def test_primary_command_uses_explicit_hermes_cc_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_CC_COMMAND", "claude --print")
    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)
    from hermes_cli.review_gate import _primary_command

    assert is_primary_available("cc")
    assert _primary_command("cc") == ["claude", "--print"]


def test_primary_command_defaults_claude_to_print_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_CC_COMMAND", raising=False)
    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)
    from hermes_cli.review_gate import _primary_command

    assert _primary_command("cc") == ["claude", "-p", "--tools", ""]


def test_review_gate_stage_choices_include_high_risk_review() -> None:
    assert REVIEW_GATE_STAGES == ("plan_review", "stage_review", "final_review", "high_risk_review")


def test_build_target_command_is_shared_for_cc_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_CC_COMMAND", raising=False)
    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)

    cmd, stdin = build_target_command(ReviewTarget("command", "cc", "forced test"), "packet")

    assert cmd == ["claude", "-p", "--tools", ""]
    assert stdin == "packet"


def test_build_target_command_uses_profile_chat_query() -> None:
    cmd, stdin = build_target_command(ReviewTarget("profile", "reviewer", "forced test"), "packet")

    assert cmd == ["hermes", "--profile", "reviewer", "chat", "-q", "packet"]
    assert stdin is None


def test_high_risk_review_can_use_policy_high_risk_section() -> None:
    packet = build_review_packet(
        {
            "reviewer_profile": {"name": "reviewer"},
            "review_gates": {},
            "high_risk_policy": {"rule": "ask cc first"},
        },
        "high_risk_review",
        {
            "operation": "restart gateway",
            "affected_files_or_systems": "gateway service",
            "why_needed": "apply config",
            "rollback_plan": "restart previous config",
            "cc_decision_requested": "allow/deny/uncertain",
        },
    )

    assert "审查阶段：high_risk_review" in packet
    assert "operation：restart gateway" in packet


def test_high_risk_review_requires_policy_high_risk_section_when_gate_is_absent() -> None:
    with pytest.raises(ValueError, match="unknown review gate stage: high_risk_review"):
        build_review_packet({"review_gates": {}}, "high_risk_review", {})


def test_parse_review_output_reads_explicit_decision_header() -> None:
    parsed = parse_review_output("""
    Some prose
    decision: allow
    risk_level: low
    【问题列表】
    - 无阻塞问题
    """)

    assert parsed.decision == "allow"
    assert parsed.risk_level == "low"
    assert parsed.needs_followup is False


def test_parse_review_output_maps_blocking_text_to_deny() -> None:
    parsed = parse_review_output("""
    【审查结果】⚠️ 需要修改
    risk_level: high
    【问题列表】
    - 阻塞：manifest 会写入真实 home，必须修复
    - blocking: CLI output removed existing fields
    """)

    assert parsed.decision == "deny"
    assert parsed.risk_level == "high"
    assert parsed.needs_followup is True
    assert parsed.blocking_items == [
        "阻塞：manifest 会写入真实 home，必须修复",
        "blocking: CLI output removed existing fields",
    ]


def test_parse_review_output_blocks_verdict_allow_when_reaudit_is_required() -> None:
    parsed = parse_review_output("""
    确认如果审查文本中同时出现 approve 和 deny 关键词，优先级逻辑是什么
    当前无阻断问题。
    **`verdict: can_continue`**
    **`needs_cc_reaudit: true`**
    """)

    assert parsed.decision == "uncertain"
    assert parsed.blocking_items == []
    assert parsed.needs_cc_reaudit is True


def test_parse_review_output_does_not_allow_ambiguous_mentions_of_pass() -> None:
    ambiguous_texts = [
        "未达到通过标准，建议补充测试",
        "Expected output: decision: allow",
        "Example: verdict: can_continue",
        "请使用 decision: allow 表示通过，但本文未给出结论",
        "这不是结论：✅ 通过 是示例",
        "This mentions approved as an example only, no conclusion.",
    ]

    for text in ambiguous_texts:
        parsed = parse_review_output(text)
        assert parsed.decision == "uncertain", text
        assert parsed.needs_followup is True


def test_parse_review_output_accepts_only_explicit_line_level_allow_signals() -> None:
    assert parse_review_output("decision: allow").decision == "allow"
    assert parse_review_output("**`verdict: can_continue`**").decision == "allow"
    assert parse_review_output("【审查结果】✅ 通过").decision == "allow"


def test_parse_review_output_keeps_decision_protocol_strict() -> None:
    assert parse_review_output("decision: approved").decision == "uncertain"
    assert parse_review_output("decision: pass").decision == "uncertain"
    assert parse_review_output("decision: 可以").decision == "uncertain"


def test_parse_review_output_fails_closed_on_conflicting_structured_signals() -> None:
    assert parse_review_output("verdict: can_continue\ndecision: deny\nrisk_level: low\n").decision == "deny"
    assert parse_review_output("decision: allow\ndecision: deny\n").decision == "deny"
    assert parse_review_output("decision: allow\n【审查结果】需要修改\n").decision == "deny"
    assert parse_review_output("decision: allow\n后文说明：无法判断，需要复审\n").decision == "uncertain"


def test_parse_review_output_ignores_allow_examples_in_code_blocks_and_example_sections() -> None:
    assert parse_review_output("""
    Reviewer says requested format is:
    ```text
    decision: allow
    risk_level: low
    ```
    No final verdict provided.
    """).decision == "uncertain"
    assert parse_review_output("""
    ~~~text
    decision: allow
    risk_level: low
    ~~~
    No final verdict provided.
    """).decision == "uncertain"
    assert parse_review_output("""
    Example:
    verdict: can_continue
    No final verdict provided.
    """).decision == "uncertain"
    assert parse_review_output("""
    Example:
    - blocking: sample only
    Actual conclusion:
    decision: allow
    risk_level: low
    """).decision == "allow"
    assert parse_review_output("""
    Example:
    decision: allow
    Actual conclusion:
    decision: deny
    """).decision == "deny"


def test_parse_review_output_handles_negative_reaudit_and_no_blocking_phrases() -> None:
    parsed = parse_review_output("decision: allow\nrisk_level: low\n不需要复审\n")
    assert parsed.decision == "allow"
    assert parsed.needs_followup is False
    assert parse_review_output("No blocking issues were found, but no explicit final decision.").decision == "uncertain"


def test_evaluate_review_gate_result_blocks_high_risk_even_when_allowed() -> None:
    parsed = parse_review_output("decision: allow\nrisk_level: high\n")
    evaluation = evaluate_review_gate_result("final_review", parsed, returncode=0, needs_cc_reaudit=False)

    assert evaluation.can_continue is False
    assert evaluation.needs_reaudit is True


def test_parse_review_output_fails_safe_to_uncertain_for_empty_or_ambiguous_text() -> None:
    parsed = parse_review_output("")

    assert parsed.decision == "uncertain"
    assert parsed.risk_level == "unknown"
    assert parsed.needs_followup is True
    assert parsed.summary == "empty review output"


def test_evaluate_review_gate_result_blocks_deny_uncertain_reaudit_and_high_risk() -> None:
    allow = parse_review_output("decision: allow\nrisk_level: low\n")
    deny = parse_review_output("decision: deny\nrisk_level: high\n- blocking: unsafe\n")
    uncertain = parse_review_output("decision: uncertain\nrisk_level: medium\n")

    assert evaluate_review_gate_result("final_review", allow, returncode=0, needs_cc_reaudit=False).can_continue
    assert evaluate_review_gate_result("final_review", deny, returncode=0, needs_cc_reaudit=False).must_fix
    assert evaluate_review_gate_result("stage_review", uncertain, returncode=0, needs_cc_reaudit=False).needs_reaudit
    assert evaluate_review_gate_result("final_review", allow, returncode=0, needs_cc_reaudit=True).needs_reaudit
    assert not evaluate_review_gate_result("high_risk_review", uncertain, returncode=0, needs_cc_reaudit=False).can_continue


def test_load_review_policy_rejects_non_mapping(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_review_policy(policy_path)


def test_choose_review_target_uses_reviewer_during_fallback_window(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(POLICY, encoding="utf-8")
    policy = load_review_policy(policy_path)

    target = choose_review_target(
        policy,
        "plan_review",
        now=datetime(2026, 5, 15, 21, 0),
        primary_available=True,
    )

    assert target.kind == "profile"
    assert target.name == "reviewer"
    assert "local_time between 20:00 and 04:00" in target.reason


def test_choose_review_target_uses_primary_when_available_outside_fallback_window(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(POLICY, encoding="utf-8")
    policy = load_review_policy(policy_path)

    target = choose_review_target(
        policy,
        "plan_review",
        now=datetime(2026, 5, 15, 10, 0),
        primary_available=True,
    )

    assert target.kind == "command"
    assert target.name == "cc"


def test_build_review_packet_requires_configured_fields(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(POLICY, encoding="utf-8")
    policy = load_review_policy(policy_path)

    with pytest.raises(ValueError, match="missing required packet fields"):
        build_review_packet(
            policy,
            "plan_review",
            {"task_goal": "实现 review gate"},
        )


def test_build_review_packet_contains_stage_and_packet_fields(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(POLICY, encoding="utf-8")
    policy = load_review_policy(policy_path)

    packet = build_review_packet(
        policy,
        "plan_review",
        {
            "task_goal": "实现 review gate",
            "implementation_plan": "写测试后实现",
            "acceptance_criteria": "测试通过",
        },
    )

    assert "审查阶段：plan_review" in packet
    assert "task_goal：实现 review gate" in packet
    assert "implementation_plan：写测试后实现" in packet
    assert "acceptance_criteria：测试通过" in packet
