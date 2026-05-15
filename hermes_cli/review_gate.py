from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml


DEFAULT_POLICY_PATH = Path.home() / ".ai-center" / "config" / "agent-review-routing.yaml"
REVIEW_GATE_STAGES = ("plan_review", "stage_review", "final_review", "high_risk_review")


@dataclass(frozen=True)
class ReviewTarget:
    kind: str
    name: str
    reason: str


@dataclass(frozen=True)
class ParsedReviewOutput:
    decision: str
    risk_level: str
    blocking_items: list[str]
    needs_followup: bool
    needs_cc_reaudit: bool
    summary: str


@dataclass(frozen=True)
class ReviewGateEvaluation:
    can_continue: bool
    must_fix: bool
    needs_reaudit: bool
    reason: str


def _normalize_decision(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"allow", "通过"}:
        return "allow"
    if normalized in {"deny", "需要修改", "阻塞", "不通过"}:
        return "deny"
    if normalized in {"uncertain", "unknown", "不确定", "需复审", "需要复审"}:
        return "uncertain"
    return None


def _trusted_review_lines(text: str) -> list[str]:
    """Return review lines that can carry the reviewer final verdict.

    Reviewer output often includes markdown code fences or examples of the
    expected schema. Those are untrusted because treating sample
    ``decision: allow`` text as the actual verdict would fail open.
    """
    trusted: list[str] = []
    in_code_fence = False
    in_example_section = False
    for line in text.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        example_header = re.match(
            r"^(?:example|examples|示例|格式示例|输出示例|requested format|期望格式)\s*[:：]?$",
            stripped_line,
            re.I,
        )
        if example_header:
            in_example_section = True
            continue
        conclusion_header = re.match(
            r"^(?:actual conclusion|final conclusion|conclusion|结论|最终结论|实际结论)\s*[:：]?$",
            stripped_line,
            re.I,
        )
        if conclusion_header:
            in_example_section = False
            continue
        if in_example_section:
            continue

        trusted.append(line)
    return trusted


def _has_positive_followup_marker(text: str) -> bool:
    without_negated = re.sub(r"不需要复审|无需复审|无须复审|no\s+reaudit\s+required|no\s+follow-?up\s+required", "", text, flags=re.I)
    return re.search(r"需要复审|需复审|无法判断", without_negated, re.I) is not None


def _has_positive_deny_marker(text: str) -> bool:
    without_negated = re.sub(r"无阻塞|无阻断|no\s+blocking(?:\s+issues)?|no\s+blockers", "", text, flags=re.I)
    deny_markers = ["需要修改", "rejected", "reject", "denied", "deny", "blocking", "阻塞", "不通过", "必须修复"]
    return any(marker in without_negated.lower() for marker in deny_markers)


def parse_review_output(text: str) -> ParsedReviewOutput:
    raw = text or ""
    stripped = raw.strip()
    if not stripped:
        return ParsedReviewOutput("uncertain", "unknown", [], True, False, "empty review output")

    trusted_lines = _trusted_review_lines(stripped)
    trusted_text = "\n".join(trusted_lines)
    lowered = trusted_text.lower()
    decision: str | None = None
    decision_signals: list[str] = []
    risk_level = "unknown"
    needs_cc_reaudit = re.search(r"needs_cc_reaudit\s*[:=：]\s*true", lowered) is not None
    blocking_items: list[str] = []

    for line in trusted_lines:
        clean = line.strip().strip("` *")
        verdict_match = re.match(r"^(?:verdict|流程结论)\s*[:：]\s*(.+)$", clean, re.I)
        if verdict_match:
            verdict = verdict_match.group(1).strip().lower()
            if verdict in {"can_continue", "continue"}:
                decision_signals.append("allow")
            elif verdict in {"must_fix", "blocked", "block"}:
                decision_signals.append("deny")
            elif verdict in {"needs_reaudit", "uncertain"}:
                decision_signals.append("uncertain")
        decision_match = re.match(r"^(?:decision|审查结论|审查结果)\s*[:：]\s*(.+)$", clean, re.I)
        if decision_match:
            normalized_decision = _normalize_decision(decision_match.group(1))
            if normalized_decision:
                decision_signals.append(normalized_decision)
        if re.match(r"^【审查结果】\s*✅\s*通过\s*$", clean):
            decision_signals.append("allow")
        if re.match(r"^【审查结果】\s*(?:⚠️\s*)?需要修改\s*$", clean):
            decision_signals.append("deny")
        risk_match = re.match(r"^(?:risk_level|risk|风险等级)\s*[:：]\s*([a-zA-Z\u4e00-\u9fff_-]+)", clean, re.I)
        if risk_match:
            risk_level = risk_match.group(1).strip().lower()
        item = clean.lstrip("-•* ").strip()
        if re.search(r"\b(blocking|blocker|must fix)\b|阻塞|阻断|必须修复|高风险", item, re.I) and not re.search(r"无阻塞|无阻断|no blocking|no blockers", item, re.I):
            blocking_items.append(item)

    has_followup_marker = _has_positive_followup_marker(trusted_text)
    if decision_signals:
        if "deny" in decision_signals:
            decision = "deny"
        elif "uncertain" in decision_signals or needs_cc_reaudit or has_followup_marker:
            decision = "uncertain"
        elif all(signal == "allow" for signal in decision_signals):
            decision = "allow"
        else:
            decision = "uncertain"

    if decision is None:
        uncertain_markers = ["uncertain", "不确定", "需复审", "需要复审", "无法判断"]
        if _has_positive_deny_marker(trusted_text):
            decision = "deny"
        elif any(marker in lowered for marker in uncertain_markers) and has_followup_marker:
            decision = "uncertain"
        else:
            decision = "uncertain"

    if decision == "allow" and blocking_items:
        decision = "deny"
    needs_followup = decision != "allow" or bool(blocking_items) or needs_cc_reaudit
    summary = next((line.strip() for line in trusted_lines if line.strip()), "")
    return ParsedReviewOutput(decision, risk_level, blocking_items, needs_followup, needs_cc_reaudit, summary)


def evaluate_review_gate_result(
    stage: str,
    parsed: ParsedReviewOutput,
    *,
    returncode: int,
    needs_cc_reaudit: bool,
) -> ReviewGateEvaluation:
    if returncode != 0:
        return ReviewGateEvaluation(False, True, False, f"review command failed: returncode={returncode}")
    if parsed.decision == "deny":
        return ReviewGateEvaluation(False, True, False, "review denied or found blocking issues")
    if needs_cc_reaudit or parsed.needs_cc_reaudit:
        return ReviewGateEvaluation(False, False, True, "fallback reviewer result requires cc reaudit")
    risk = parsed.risk_level.strip().lower().replace("-", "_")
    if risk in {"high", "high_risk", "critical", "高", "高风险"}:
        return ReviewGateEvaluation(False, False, True, "high-risk review requires explicit follow-up approval")
    if parsed.decision != "allow":
        return ReviewGateEvaluation(False, False, True, "review decision is uncertain")
    return ReviewGateEvaluation(True, False, False, "review allowed continuation")


def load_review_policy(path: str | Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    policy_path = Path(path).expanduser()
    if not policy_path.exists():
        raise FileNotFoundError(f"review routing policy not found: {policy_path}")
    with policy_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"review routing policy must be a YAML mapping: {policy_path}")
    return data


def is_local_time_between(now: datetime, window: str) -> bool:
    """Return True if now's local HH:MM is within a window like 20:00-04:00."""
    start_s, end_s = [part.strip() for part in window.split("-", 1)]
    start_h, start_m = [int(part) for part in start_s.split(":", 1)]
    end_h, end_m = [int(part) for part in end_s.split(":", 1)]
    current = now.hour * 60 + now.minute
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _gate(policy: Mapping[str, Any], stage: str) -> Mapping[str, Any]:
    gates = policy.get("review_gates") or {}
    if stage not in gates:
        if stage == "high_risk_review" and isinstance(policy.get("high_risk_policy"), Mapping):
            return {
                "trigger": "Before high-risk actions",
                "primary": "cc",
                "fallback": {"profile": _fallback_profile(policy, {}), "when": ["cc unavailable or no response"]},
                "required_packet": [
                    "operation",
                    "affected_files_or_systems",
                    "why_needed",
                    "rollback_plan",
                    "cc_decision_requested",
                ],
            }
        available = ", ".join(sorted(gates)) or "<none>"
        raise ValueError(f"unknown review gate stage: {stage}; available: {available}")
    gate = gates[stage]
    if not isinstance(gate, Mapping):
        raise ValueError(f"review gate must be a mapping: {stage}")
    return gate


def _fallback_profile(policy: Mapping[str, Any], gate: Mapping[str, Any]) -> str:
    fallback = gate.get("fallback") or {}
    if isinstance(fallback, Mapping) and fallback.get("profile"):
        return str(fallback["profile"])
    reviewer_profile = policy.get("reviewer_profile") or {}
    if isinstance(reviewer_profile, Mapping) and reviewer_profile.get("name"):
        return str(reviewer_profile["name"])
    reviewer_role = (policy.get("roles") or {}).get("reviewer") or {}
    if isinstance(reviewer_role, Mapping) and reviewer_role.get("preferred_profile"):
        return str(reviewer_role["preferred_profile"])
    return "reviewer"


def is_primary_available(primary: str) -> bool:
    """Return whether the configured primary reviewer command is usable.

    The policy uses "cc" to mean Claude/Claude Code, but macOS/Linux often have
    /usr/bin/cc as the C compiler. Never treat that compiler as a reviewer.
    Set HERMES_CC_COMMAND to an explicit Claude command if needed.
    """
    if primary == "cc":
        configured = os.getenv("HERMES_CC_COMMAND", "").strip()
        if configured:
            return shutil.which(shlex.split(configured)[0]) is not None
        return shutil.which("claude") is not None or shutil.which("claude-code") is not None
    return shutil.which(primary) is not None


def _primary_command(primary: str) -> list[str]:
    if primary == "cc":
        configured = os.getenv("HERMES_CC_COMMAND", "").strip()
        if configured:
            command = shlex.split(configured)
            if shutil.which(command[0]):
                return command
            raise RuntimeError(f"Configured HERMES_CC_COMMAND is unavailable: {command[0]}")
        if shutil.which("claude"):
            return ["claude", "-p", "--tools", ""]
        if shutil.which("claude-code"):
            return ["claude-code", "-p"]
        raise RuntimeError("Claude reviewer command is unavailable for primary 'cc'")
    return [primary]


def build_target_command(target: ReviewTarget, packet: str) -> tuple[list[str], str | None]:
    if target.kind == "profile":
        return ["hermes", "--profile", target.name, "chat", "-q", packet], None
    if target.name == "cc":
        return _primary_command(target.name), packet
    return _primary_command(target.name) + [packet], None


def choose_review_target(
    policy: Mapping[str, Any],
    stage: str,
    *,
    now: datetime | None = None,
    primary_available: bool | None = None,
) -> ReviewTarget:
    gate = _gate(policy, stage)
    now = now or datetime.now()
    primary = str(gate.get("primary") or "cc")
    fallback_profile = _fallback_profile(policy, gate)
    fallback = gate.get("fallback") or {}
    fallback_conditions = fallback.get("when") if isinstance(fallback, Mapping) else []
    if not isinstance(fallback_conditions, list):
        fallback_conditions = []

    for condition in fallback_conditions:
        condition_s = str(condition)
        marker = "local_time between "
        if marker in condition_s:
            window = condition_s.split(marker, 1)[1].strip().replace(" and ", "-")
            if is_local_time_between(now, window):
                return ReviewTarget("profile", fallback_profile, condition_s)

    if primary_available is None:
        primary_available = is_primary_available(primary)
    if primary_available:
        return ReviewTarget("command", primary, "primary available")
    return ReviewTarget("profile", fallback_profile, f"{primary} unavailable or no response")


def build_review_packet(
    policy: Mapping[str, Any],
    stage: str,
    fields: Mapping[str, Any],
) -> str:
    gate = _gate(policy, stage)
    required = gate.get("required_packet") or []
    missing = [str(name) for name in required if not str(fields.get(str(name), "")).strip()]
    if missing:
        raise ValueError("missing required packet fields: " + ", ".join(missing))

    lines = [
        "请按 reviewer SOUL.md 的审查格式执行只读审查。",
        f"审查阶段：{stage}",
        f"触发条件：{gate.get('trigger', '')}",
        "",
        "审查包：",
    ]
    for key in required:
        key_s = str(key)
        lines.append(f"{key_s}：{fields.get(key_s, '')}")
    extra_keys = [key for key in fields if key not in required]
    if extra_keys:
        lines.extend(["", "补充信息："])
        for key in extra_keys:
            lines.append(f"{key}：{fields[key]}")
    return "\n".join(lines).strip() + "\n"


def _parse_fields(values: list[str] | None) -> dict[str, str]:
    fields: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"--field must be KEY=VALUE, got: {value}")
        key, field_value = value.split("=", 1)
        fields[key.strip()] = field_value.strip()
    return fields


def _run_target(target: ReviewTarget, packet: str, timeout: int) -> int:
    cmd, stdin = build_target_command(target, packet)
    completed = subprocess.run(cmd, input=stdin, text=True, timeout=timeout, check=False)
    return int(completed.returncode)


def cmd_review_gate(args: argparse.Namespace) -> None:
    policy = load_review_policy(args.policy)
    fields = _parse_fields(args.field)
    if args.json:
        try:
            fields.update(json.loads(Path(args.json).read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON file: {exc}") from exc
    if args.text:
        fields.setdefault("context_summary", args.text)
        fields.setdefault("known_risks", args.text)
        fields.setdefault("unresolved_risks", args.text)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    target = choose_review_target(policy, args.stage, now=now)
    packet = build_review_packet(policy, args.stage, fields)

    if args.dry_run:
        print(f"target={target.kind}:{target.name}")
        print(f"reason={target.reason}")
        print(packet, end="")
        return

    raise SystemExit(_run_target(target, packet, args.timeout))


def add_review_gate_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "review-gate",
        help="Run or dry-run the Hermes/cc/reviewer review gate policy",
        description="Build a standard review packet from agent-review-routing.yaml and route it to cc or the reviewer profile.",
    )
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Path to agent-review-routing.yaml")
    parser.add_argument("--stage", required=True, choices=REVIEW_GATE_STAGES, help="Review gate stage")
    parser.add_argument("--field", action="append", help="Packet field as KEY=VALUE; repeatable")
    parser.add_argument("--json", help="JSON file containing packet fields")
    parser.add_argument("--text", help="Fallback text for context/risk fields")
    parser.add_argument("--now", help="Override local time for deterministic tests, ISO format")
    parser.add_argument("--dry-run", action="store_true", help="Print target and packet without invoking reviewer")
    parser.add_argument("--timeout", type=int, default=600, help="Reviewer command timeout seconds")
    parser.set_defaults(func=cmd_review_gate)
