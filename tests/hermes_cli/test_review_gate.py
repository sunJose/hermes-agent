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
    is_primary_available,
    is_local_time_between,
    load_review_policy,
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
