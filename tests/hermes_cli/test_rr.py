from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli.rr import add_rr_parser, normalize_rr_stage, packet_template_for_stage


POLICY = """
version: 1
roles:
  reviewer:
    preferred_profile: reviewer
review_gates:
  plan_review:
    primary: cc
    required_packet:
      - task_goal
      - context_summary
      - implementation_plan
      - acceptance_criteria
      - risk_boundary
  stage_review:
    primary: cc
    required_packet:
      - task_goal
      - completed_rounds
      - changed_files
      - key_diff_summary
      - tests_run
      - known_risks
  final_review:
    primary: cc
    required_packet:
      - task_goal
      - acceptance_criteria
      - changed_files
      - final_diff_summary
      - verification_results
      - unresolved_risks
high_risk_policy:
  rule: ask cc
reviewer_profile:
  name: reviewer
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    add_rr_parser(subparsers)
    return parser


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("plan", "plan_review"),
        ("stage", "stage_review"),
        ("final", "final_review"),
        ("risk", "high_risk_review"),
        ("high-risk", "high_risk_review"),
        ("plan_review", "plan_review"),
    ],
)
def test_normalize_rr_stage_accepts_short_aliases(alias: str, expected: str) -> None:
    assert normalize_rr_stage(alias) == expected


def test_normalize_rr_stage_rejects_unknown_alias() -> None:
    with pytest.raises(ValueError, match="unknown rr stage"):
        normalize_rr_stage("later")


@pytest.mark.parametrize(
    ("stage", "expected_keys"),
    [
        ("plan", ["task_goal", "context_summary", "implementation_plan", "acceptance_criteria", "risk_boundary"]),
        ("stage", ["task_goal", "completed_rounds", "changed_files", "key_diff_summary", "tests_run", "known_risks"]),
        ("final", ["task_goal", "acceptance_criteria", "changed_files", "final_diff_summary", "verification_results", "unresolved_risks"]),
        ("risk", ["operation", "affected_files_or_systems", "why_needed", "rollback_plan", "cc_decision_requested"]),
    ],
)
def test_packet_template_for_stage_uses_policy_required_fields(tmp_path: Path, stage: str, expected_keys: list[str]) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")

    template = packet_template_for_stage(stage, policy)

    assert list(template) == expected_keys
    assert all(value == "" for value in template.values())


def test_rr_template_command_uses_default_policy_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ai_center = tmp_path / "ai-center"
    policy = ai_center / "config" / "agent-review-routing.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text(POLICY, encoding="utf-8")
    out = tmp_path / "packet.json"
    monkeypatch.setenv("AI_CENTER_HOME", str(ai_center))
    monkeypatch.delenv("HERMES_REVIEW_ROUTING_POLICY", raising=False)

    args = _parser().parse_args(["rr", "template", "--stage", "risk", "--out", str(out)])
    args.func(args)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert list(data) == ["operation", "affected_files_or_systems", "why_needed", "rollback_plan", "cc_decision_requested"]


def test_rr_template_command_writes_json_template(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    out = tmp_path / "packet.json"
    args = _parser().parse_args(["rr", "template", "--stage", "risk", "--policy", str(policy), "--out", str(out)])

    args.func(args)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert list(data) == ["operation", "affected_files_or_systems", "why_needed", "rollback_plan", "cc_decision_requested"]
    stdout = capsys.readouterr().out
    assert f"template={out}" in stdout
    assert "stage=high_risk_review" in stdout


def test_rr_dry_run_builds_complete_review_gate_namespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packet = tmp_path / "packet.json"
    packet.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_cmd_review_gate(ns: argparse.Namespace) -> None:
        captured.update(vars(ns))

    monkeypatch.setattr("hermes_cli.rr.cmd_review_gate", fake_cmd_review_gate)
    args = _parser().parse_args([
        "rr",
        "dry-run",
        "--stage",
        "plan",
        "--json",
        str(packet),
        "--policy",
        "policy.yaml",
        "--now",
        "2026-05-15T10:00:00",
        "--timeout",
        "7",
    ])

    args.func(args)

    assert captured == {
        "policy": "policy.yaml",
        "stage": "plan_review",
        "field": None,
        "json": str(packet),
        "text": None,
        "now": "2026-05-15T10:00:00",
        "dry_run": True,
        "timeout": 7,
    }


def test_rr_run_builds_complete_cc_loop_namespace_with_strict_exit_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packet = tmp_path / "packet.json"
    packet.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_cmd_cc_loop(ns: argparse.Namespace) -> None:
        captured.update(vars(ns))

    monkeypatch.setattr("hermes_cli.rr.cmd_cc_loop", fake_cmd_cc_loop)
    args = _parser().parse_args([
        "rr",
        "run",
        "--stage",
        "final",
        "--json",
        str(packet),
        "--policy",
        "policy.yaml",
        "--out",
        "review.txt",
        "--manifest",
        "manifest.jsonl",
        "--now",
        "2026-05-15T10:00:00",
        "--timeout",
        "9",
    ])

    args.func(args)

    assert captured == {
        "policy": "policy.yaml",
        "stage": "final_review",
        "json": str(packet),
        "out": "review.txt",
        "manifest": "manifest.jsonl",
        "now": "2026-05-15T10:00:00",
        "timeout": 9,
        "strict_exit": True,
    }


def test_rr_run_can_disable_strict_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packet = tmp_path / "packet.json"
    packet.write_text("{}", encoding="utf-8")
    captured = SimpleNamespace(strict_exit=None)

    def fake_cmd_cc_loop(ns: argparse.Namespace) -> None:
        captured.strict_exit = ns.strict_exit

    monkeypatch.setattr("hermes_cli.rr.cmd_cc_loop", fake_cmd_cc_loop)
    args = _parser().parse_args(["rr", "run", "--stage", "plan", "--json", str(packet), "--no-strict-exit"])

    args.func(args)

    assert captured.strict_exit is False
