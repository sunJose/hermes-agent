from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli.cc_loop import _default_output_path, add_cc_loop_parser, load_packet_fields, run_review_gate
from hermes_cli.review_gate import add_review_gate_parser


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
    required_packet:
      - task_goal
      - context_summary
      - implementation_plan
      - acceptance_criteria
      - risk_boundary
reviewer_profile:
  name: reviewer
"""


FIELDS = {
    "task_goal": "落地 CC闭环",
    "context_summary": "已有 review-gate MVP",
    "implementation_plan": "先审查 plan 再实现",
    "acceptance_criteria": "测试通过",
    "risk_boundary": "高风险问 cc",
}


def test_load_packet_fields_requires_json_object(tmp_path: Path) -> None:
    packet = tmp_path / "packet.json"
    packet.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="packet JSON must be an object"):
        load_packet_fields(packet)


def test_default_output_path_uses_hermes_reviews_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hermes_cli.cc_loop.Path.home", lambda: tmp_path)

    output_path = _default_output_path("stage_review")

    assert output_path.parent == tmp_path / ".hermes" / "reviews"
    assert output_path.name.startswith("hermes-cc-loop-stage_review-")


def test_review_gate_and_cc_loop_parsers_accept_high_risk_review() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    add_review_gate_parser(subparsers)
    add_cc_loop_parser(subparsers)

    review_args = parser.parse_args([
        "review-gate",
        "--stage",
        "high_risk_review",
        "--field",
        "task_goal=x",
        "--dry-run",
    ])
    cc_args = parser.parse_args([
        "cc-loop",
        "--stage",
        "high_risk_review",
        "--json",
        "packet.json",
    ])

    assert review_args.stage == "high_risk_review"
    assert cc_args.stage == "high_risk_review"


def test_run_review_gate_saves_primary_review_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    out = tmp_path / "review.txt"

    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="【审查结果】✅ 通过\n", stderr="")

    monkeypatch.setattr("hermes_cli.cc_loop.subprocess.run", fake_run)

    result = run_review_gate(
        stage="plan_review",
        fields=FIELDS,
        policy_path=policy,
        output_path=out,
        now=datetime(2026, 5, 15, 10, 0),
        timeout=1,
    )

    assert result.returncode == 0
    assert result.target.kind == "command"
    assert calls[0][:4] == ["claude", "-p", "--tools", ""]
    saved = out.read_text(encoding="utf-8")
    assert "needs_cc_reaudit=false" in saved
    assert "【审查结果】✅ 通过" in saved


def test_run_review_gate_marks_fallback_as_needing_cc_reaudit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    out = tmp_path / "review.txt"

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert "needs_cc_reaudit：true" in cmd[-1]
        return SimpleNamespace(returncode=0, stdout="【审查结果】✅ 通过\n", stderr="")

    monkeypatch.setattr("hermes_cli.cc_loop.subprocess.run", fake_run)

    result = run_review_gate(
        stage="plan_review",
        fields=FIELDS,
        policy_path=policy,
        output_path=out,
        now=datetime(2026, 5, 15, 21, 0),
        timeout=1,
    )

    assert result.needs_cc_reaudit is True
    assert result.target.kind == "profile"
    assert calls[0][:4] == ["hermes", "--profile", "reviewer", "chat"]
    assert "needs_cc_reaudit=true" in out.read_text(encoding="utf-8")
