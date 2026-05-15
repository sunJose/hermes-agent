from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from hermes_cli.review_gate import (
    DEFAULT_POLICY_PATH,
    ReviewTarget,
    REVIEW_GATE_STAGES,
    build_review_packet,
    build_target_command,
    choose_review_target,
    load_review_policy,
)


@dataclass(frozen=True)
class CCLoopReviewResult:
    stage: str
    target: ReviewTarget
    needs_cc_reaudit: bool
    output_path: Path
    returncode: int


def _default_output_path(stage: str) -> Path:
    output_dir = Path.home() / ".hermes" / "reviews"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return output_dir / f"hermes-cc-loop-{stage}-{stamp}.txt"


def load_packet_fields(path: str | Path) -> dict[str, Any]:
    packet_path = Path(path).expanduser()
    data = json.loads(packet_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"packet JSON must be an object: {packet_path}")
    return data


def run_review_gate(
    *,
    stage: str,
    fields: Mapping[str, Any],
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    output_path: str | Path | None = None,
    now: datetime | None = None,
    timeout: int = 600,
) -> CCLoopReviewResult:
    policy = load_review_policy(policy_path)
    target = choose_review_target(policy, stage, now=now)
    needs_cc_reaudit = target.kind == "profile"
    packet_fields = dict(fields)
    if needs_cc_reaudit:
        packet_fields.setdefault("needs_cc_reaudit", "true")
    packet = build_review_packet(policy, stage, packet_fields)

    out_path = Path(output_path).expanduser() if output_path else _default_output_path(stage)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd, stdin = build_target_command(target, packet)
    completed = subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    review_text = completed.stdout
    if completed.stderr:
        review_text += ("\n" if review_text else "") + "[stderr]\n" + completed.stderr
    header = (
        f"stage={stage}\n"
        f"target={target.kind}:{target.name}\n"
        f"reason={target.reason}\n"
        f"needs_cc_reaudit={str(needs_cc_reaudit).lower()}\n"
        f"returncode={completed.returncode}\n\n"
    )
    out_path.write_text(header + review_text, encoding="utf-8")

    return CCLoopReviewResult(
        stage=stage,
        target=target,
        needs_cc_reaudit=needs_cc_reaudit,
        output_path=out_path,
        returncode=int(completed.returncode),
    )


def cmd_cc_loop(args: argparse.Namespace) -> None:
    fields = load_packet_fields(args.json)
    now = datetime.fromisoformat(args.now) if args.now else None
    try:
        result = run_review_gate(
            stage=args.stage,
            fields=fields,
            policy_path=args.policy,
            output_path=args.out,
            now=now,
            timeout=args.timeout,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"stage={result.stage}")
    print(f"target={result.target.kind}:{result.target.name}")
    print(f"needs_cc_reaudit={str(result.needs_cc_reaudit).lower()}")
    print(f"output={result.output_path}")
    raise SystemExit(result.returncode)


def add_cc_loop_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "cc-loop",
        help="Run a minimal Hermes/Codex/Claude review loop gate",
        description="MVP wrapper for CC闭环: send a structured packet to the configured review gate and save the review output.",
    )
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Path to agent-review-routing.yaml")
    parser.add_argument("--stage", required=True, choices=REVIEW_GATE_STAGES, help="Review gate stage")
    parser.add_argument("--json", required=True, help="JSON file containing packet fields")
    parser.add_argument("--out", help="Where to save reviewer output; defaults to ~/.hermes/reviews")
    parser.add_argument("--now", help="Override local time for deterministic tests, ISO format")
    parser.add_argument("--timeout", type=int, default=600, help="Reviewer command timeout seconds")
    parser.set_defaults(func=cmd_cc_loop)
