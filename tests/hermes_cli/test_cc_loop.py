from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli.cc_loop import _default_manifest_path, _default_output_path, add_cc_loop_parser, cmd_cc_loop, load_packet_fields, run_review_gate
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


def test_default_manifest_path_uses_hermes_reviews_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hermes_cli.cc_loop.Path.home", lambda: tmp_path)

    assert _default_manifest_path() == tmp_path / ".hermes" / "reviews" / "manifest.jsonl"


def test_run_review_gate_writes_decision_header_and_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    out = tmp_path / "review.txt"
    manifest = tmp_path / "manifest.jsonl"

    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="decision: allow\nrisk_level: low\n【审查结果】✅ 通过\n", stderr="")

    monkeypatch.setattr("hermes_cli.cc_loop.subprocess.run", fake_run)

    result = run_review_gate(
        stage="plan_review",
        fields=FIELDS,
        policy_path=policy,
        output_path=out,
        manifest_path=manifest,
        now=datetime(2026, 5, 15, 10, 0),
        timeout=1,
    )

    saved = out.read_text(encoding="utf-8")
    assert "decision=allow" in saved
    assert "risk_level=low" in saved
    assert result.parsed.decision == "allow"
    assert result.evaluation.can_continue is True
    line = manifest.read_text(encoding="utf-8").strip()
    entry = __import__("json").loads(line)
    assert entry["timestamp"] == "2026-05-15T10:00:00"
    assert entry["stage"] == "plan_review"
    assert entry["target"] == "command:cc"
    assert entry["decision"] == "allow"
    assert entry["risk_level"] == "low"
    assert entry["can_continue"] is True
    assert entry["output_path"] == str(out)
    assert entry["blocking_items"] == []
    assert entry["needs_followup"] is False
    assert entry["needs_cc_reaudit_from_output"] is False
    assert entry["summary"] == "decision: allow"


def test_run_review_gate_manifest_persists_blocking_items_for_denied_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    out = tmp_path / "review.txt"
    manifest = tmp_path / "manifest.jsonl"

    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="decision: deny\nrisk_level: medium\n- blocking: tests missing\n", stderr="")

    monkeypatch.setattr("hermes_cli.cc_loop.subprocess.run", fake_run)

    result = run_review_gate(
        stage="plan_review",
        fields=FIELDS,
        policy_path=policy,
        output_path=out,
        manifest_path=manifest,
        now=datetime(2026, 5, 15, 10, 0),
        timeout=1,
    )

    entry = __import__("json").loads(manifest.read_text(encoding="utf-8").strip())
    assert result.evaluation.can_continue is False
    assert entry["blocking_items"] == ["blocking: tests missing"]
    assert entry["needs_followup"] is True
    assert entry["needs_cc_reaudit_from_output"] is False
    assert entry["summary"] == "decision: deny"


def test_cmd_cc_loop_strict_exit_returns_two_when_gate_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    packet = tmp_path / "packet.json"
    packet.write_text(__import__("json").dumps(FIELDS), encoding="utf-8")
    out = tmp_path / "review.txt"
    manifest = tmp_path / "manifest.jsonl"

    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="decision: deny\nrisk_level: medium\n- blocking: not ready\n", stderr="")

    monkeypatch.setattr("hermes_cli.cc_loop.subprocess.run", fake_run)
    args = SimpleNamespace(
        json=str(packet),
        stage="plan_review",
        policy=str(policy),
        out=str(out),
        manifest=str(manifest),
        now="2026-05-15T10:00:00",
        timeout=1,
        strict_exit=True,
    )

    with pytest.raises(SystemExit) as exc:
        cmd_cc_loop(args)

    assert exc.value.code == 2
    stdout = capsys.readouterr().out
    assert "returncode=0" in stdout
    assert "can_continue=false" in stdout


def test_run_review_gate_blocks_uncertain_high_risk_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        POLICY + "\nhigh_risk_policy:\n  rule: ask rr\n",
        encoding="utf-8",
    )
    out = tmp_path / "review.txt"
    manifest = tmp_path / "manifest.jsonl"

    monkeypatch.setattr("hermes_cli.review_gate.shutil.which", lambda name: "/opt/homebrew/bin/claude" if name == "claude" else None)

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="decision: uncertain\nrisk_level: high\n", stderr="")

    monkeypatch.setattr("hermes_cli.cc_loop.subprocess.run", fake_run)

    result = run_review_gate(
        stage="high_risk_review",
        fields={
            "operation": "push branch",
            "affected_files_or_systems": "git remote",
            "why_needed": "sync changes",
            "rollback_plan": "revert commit",
            "cc_decision_requested": "allow/deny/uncertain",
        },
        policy_path=policy,
        output_path=out,
        manifest_path=manifest,
        now=datetime(2026, 5, 15, 10, 0),
        timeout=1,
    )

    assert result.parsed.decision == "uncertain"
    assert result.evaluation.can_continue is False
    assert result.evaluation.needs_reaudit is True
    assert "can_continue=false" in out.read_text(encoding="utf-8")


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
    assert calls[0][:4] == ["claude", "-p", "--allowedTools", "Read,Grep,Glob,Bash(git diff:*),Bash(git status:*),Bash(git show:*),Bash(git log:*)"]
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
