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
    ParsedReviewOutput,
    ReviewGateEvaluation,
    ReviewTarget,
    REVIEW_GATE_STAGES,
    build_review_packet,
    build_target_command,
    choose_review_target,
    evaluate_review_gate_result,
    load_review_policy,
    parse_review_output,
)


@dataclass(frozen=True)
class CCLoopReviewResult:
    stage: str
    target: ReviewTarget
    needs_cc_reaudit: bool
    output_path: Path
    manifest_path: Path
    returncode: int
    parsed: ParsedReviewOutput
    evaluation: ReviewGateEvaluation


def _default_output_path(stage: str) -> Path:
    output_dir = Path.home() / ".hermes" / "reviews"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return output_dir / f"hermes-cc-loop-{stage}-{stamp}.txt"


def _default_manifest_path() -> Path:
    return Path.home() / ".hermes" / "reviews" / "manifest.jsonl"


def _append_manifest(path: Path, entry: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(entry), ensure_ascii=False, sort_keys=True) + "\n")


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
    manifest_path: str | Path | None = None,
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
    parsed = parse_review_output(review_text)
    evaluation = evaluate_review_gate_result(
        stage,
        parsed,
        returncode=int(completed.returncode),
        needs_cc_reaudit=needs_cc_reaudit,
    )
    manifest_out = Path(manifest_path).expanduser() if manifest_path else _default_manifest_path()
    header = (
        f"stage={stage}\n"
        f"target={target.kind}:{target.name}\n"
        f"reason={target.reason}\n"
        f"needs_cc_reaudit={str(needs_cc_reaudit).lower()}\n"
        f"returncode={completed.returncode}\n"
        f"decision={parsed.decision}\n"
        f"risk_level={parsed.risk_level}\n"
        f"can_continue={str(evaluation.can_continue).lower()}\n"
        f"must_fix={str(evaluation.must_fix).lower()}\n"
        f"needs_reaudit={str(evaluation.needs_reaudit).lower()}\n"
        f"manifest={manifest_out}\n\n"
    )
    out_path.write_text(header + review_text, encoding="utf-8")
    _append_manifest(
        manifest_out,
        {
            "timestamp": (now or datetime.now()).isoformat(timespec="seconds"),
            "stage": stage,
            "target": f"{target.kind}:{target.name}",
            "reason": target.reason,
            "needs_cc_reaudit": needs_cc_reaudit,
            "returncode": int(completed.returncode),
            "output_path": str(out_path),
            "decision": parsed.decision,
            "risk_level": parsed.risk_level,
            "can_continue": evaluation.can_continue,
            "must_fix": evaluation.must_fix,
            "needs_reaudit": evaluation.needs_reaudit,
            "evaluation_reason": evaluation.reason,
            "blocking_items": parsed.blocking_items,
            "needs_followup": parsed.needs_followup,
            "needs_cc_reaudit_from_output": parsed.needs_cc_reaudit,
            "summary": parsed.summary,
            "packet_keys": sorted(str(key) for key in fields.keys()),
        },
    )

    return CCLoopReviewResult(
        stage=stage,
        target=target,
        needs_cc_reaudit=needs_cc_reaudit,
        output_path=out_path,
        manifest_path=manifest_out,
        returncode=int(completed.returncode),
        parsed=parsed,
        evaluation=evaluation,
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
            manifest_path=getattr(args, "manifest", None),
            now=now,
            timeout=args.timeout,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"stage={result.stage}")
    print(f"target={result.target.kind}:{result.target.name}")
    print(f"needs_cc_reaudit={str(result.needs_cc_reaudit).lower()}")
    print(f"returncode={result.returncode}")
    print(f"decision={result.parsed.decision}")
    print(f"risk_level={result.parsed.risk_level}")
    print(f"can_continue={str(result.evaluation.can_continue).lower()}")
    print(f"must_fix={str(result.evaluation.must_fix).lower()}")
    print(f"needs_reaudit={str(result.evaluation.needs_reaudit).lower()}")
    print(f"output={result.output_path}")
    print(f"manifest={result.manifest_path}")
    if getattr(args, "strict_exit", False) and result.returncode == 0 and not result.evaluation.can_continue:
        raise SystemExit(2)
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
    parser.add_argument("--manifest", help="Where to append review history JSONL; defaults to ~/.hermes/reviews/manifest.jsonl")
    parser.add_argument("--now", help="Override local time for deterministic tests, ISO format")
    parser.add_argument("--timeout", type=int, default=600, help="Reviewer command timeout seconds")
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit with code 2 when the reviewer command succeeds but the structured gate blocks continuation",
    )
    parser.set_defaults(func=cmd_cc_loop)
