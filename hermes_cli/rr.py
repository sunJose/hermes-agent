from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hermes_cli.cc_loop import cmd_cc_loop
from hermes_cli.review_gate import (
    DEFAULT_POLICY_PATH,
    REVIEW_GATE_STAGES,
    get_required_packet_fields,
    load_review_policy,
    cmd_review_gate,
)

_STAGE_ALIASES = {
    "plan": "plan_review",
    "stage": "stage_review",
    "final": "final_review",
    "risk": "high_risk_review",
    "high-risk": "high_risk_review",
    "high_risk": "high_risk_review",
}


def normalize_rr_stage(stage: str) -> str:
    normalized = _STAGE_ALIASES.get(stage, stage)
    if normalized not in REVIEW_GATE_STAGES:
        allowed = ", ".join(sorted([*REVIEW_GATE_STAGES, *_STAGE_ALIASES]))
        raise ValueError(f"unknown rr stage: {stage}; allowed: {allowed}")
    return normalized


def packet_template_for_stage(stage: str, policy_path: str | Path | None = None) -> dict[str, str]:
    normalized_stage = normalize_rr_stage(stage)
    policy = load_review_policy(policy_path)
    return {field: "" for field in get_required_packet_fields(policy, normalized_stage)}


def cmd_rr_template(args: argparse.Namespace) -> None:
    stage = normalize_rr_stage(args.stage)
    template = packet_template_for_stage(stage, args.policy)
    text = json.dumps(template, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"stage={stage}")
        print(f"template={out}")
        return
    print(text, end="")


def cmd_rr_dry_run(args: argparse.Namespace) -> None:
    stage = normalize_rr_stage(args.stage)
    cmd_review_gate(
        argparse.Namespace(
            policy=args.policy,
            stage=stage,
            field=None,
            json=args.json,
            text=None,
            now=args.now,
            dry_run=True,
            timeout=args.timeout,
        )
    )


def cmd_rr_run(args: argparse.Namespace) -> None:
    stage = normalize_rr_stage(args.stage)
    cmd_cc_loop(
        argparse.Namespace(
            policy=args.policy,
            stage=stage,
            json=args.json,
            out=args.out,
            manifest=args.manifest,
            now=args.now,
            timeout=args.timeout,
            strict_exit=args.strict_exit,
        )
    )


def add_rr_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "rr",
        help="One-click rr/cc review helpers",
        description="Generate review packet templates, preview review packets, or run cc-loop with strict gating.",
    )
    rr_subparsers = parser.add_subparsers(dest="rr_command", required=True)

    template = rr_subparsers.add_parser("template", help="Generate a JSON packet template for a review stage")
    template.add_argument("--policy", help="Path to agent-review-routing.yaml; defaults to HERMES_REVIEW_ROUTING_POLICY, AI_CENTER_HOME, or ~/.ai-center")
    template.add_argument("--stage", required=True, help="Review stage or alias: plan/stage/final/risk")
    template.add_argument("--out", help="Where to write the JSON template; prints to stdout when omitted")
    template.set_defaults(func=cmd_rr_template)

    dry_run = rr_subparsers.add_parser("dry-run", help="Preview target and packet without invoking reviewer")
    dry_run.add_argument("--policy", help="Path to agent-review-routing.yaml; defaults to HERMES_REVIEW_ROUTING_POLICY, AI_CENTER_HOME, or ~/.ai-center")
    dry_run.add_argument("--stage", required=True, help="Review stage or alias: plan/stage/final/risk")
    dry_run.add_argument("--json", required=True, help="JSON file containing packet fields")
    dry_run.add_argument("--now", help="Override local time for deterministic routing, ISO format")
    dry_run.add_argument("--timeout", type=int, default=600, help="Reviewer command timeout seconds")
    dry_run.set_defaults(func=cmd_rr_dry_run)

    run = rr_subparsers.add_parser("run", help="Run cc-loop for a review stage; strict-exit is on by default")
    run.add_argument("--policy", help="Path to agent-review-routing.yaml; defaults to HERMES_REVIEW_ROUTING_POLICY, AI_CENTER_HOME, or ~/.ai-center")
    run.add_argument("--stage", required=True, help="Review stage or alias: plan/stage/final/risk")
    run.add_argument("--json", required=True, help="JSON file containing packet fields")
    run.add_argument("--out", help="Where to save reviewer output; defaults to ~/.hermes/reviews")
    run.add_argument("--manifest", help="Where to append review history JSONL; defaults to ~/.hermes/reviews/manifest.jsonl")
    run.add_argument("--now", help="Override local time for deterministic tests, ISO format")
    run.add_argument("--timeout", type=int, default=600, help="Reviewer command timeout seconds")
    run.add_argument("--strict-exit", dest="strict_exit", action="store_true", default=True, help="Exit 2 when structured gate blocks continuation (default)")
    run.add_argument("--no-strict-exit", dest="strict_exit", action="store_false", help="Preserve reviewer command exit code even when the gate blocks")
    run.set_defaults(func=cmd_rr_run)
