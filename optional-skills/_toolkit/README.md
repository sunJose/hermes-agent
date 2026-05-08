# `_toolkit/` — Cross-Skill Shared Modules

> **Purpose**: hold reusable Python modules that multiple skills under
> `optional-skills/` can import. Underscore prefix marks this as a *non-skill
> directory* — Hermes' skill loader scans for `SKILL.md`, and `_toolkit/` has
> none, so curator/loader skip it.
>
> **Origin**: introduced as part of the Crowbar replication project (see
> `~/.hermes/skills/personal/crowbar-project/PLAN.md` Phase 2).

---

## When to put something here

Add a module to `_toolkit/` only when **at least 2 skills** demonstrably need it.
Don't pre-design — the YAGNI rule for this project is hard:

> 第二次用到才抽。第一次直接写在调用 skill 的 `scripts/` 里。

Examples (concrete, not aspirational):

| Module | Trigger to extract |
|---|---|
| `ws_recorder/` | `crowbar-lark` ships `mitm_ws_probe.py`; second skill (e.g. `crowbar-github` if WS path needed) starts to copy it |
| `cookie_extractor/` | A skill needs Keychain / Chrome Cookie Store access for the second time |
| `protobuf_toolkit/` | Two skills both need to decode `.proto`-less Protobuf frames |
| `har_parser/` | Two skills both need to read Chrome DevTools `.har` exports |
| `crypto_detective/` | Two skills both need to identify AES/RSA/HMAC patterns at runtime |

---

## Layout convention

```
optional-skills/_toolkit/
├── README.md                     # this file
├── <module-name>/
│   ├── README.md                 # required: what it does, when to use, public API
│   ├── __init__.py               # exports public surface
│   ├── <module-name>.py          # main implementation (or split into multiple files)
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_<module-name>.py # pytest, runnable in isolation
│   └── fixtures/                 # optional: redacted sample inputs for tests
└── <next-module>/
    └── ...
```

Rules:

1. **Module names use underscores** (`ws_recorder`, not `ws-recorder`) — Python
   import compatibility. Directory name = importable module name.
2. **Each module is self-contained**: stdlib + its declared `pip_dependencies`
   only. **Cross-`_toolkit` imports are forbidden** (avoid hidden coupling).
   If two modules genuinely need to share code, split a third foundation module
   under a clear name.
3. **`__init__.py` exports the public API surface** explicitly via `__all__`.
   Internals stay private (underscore prefix).
4. **Tests live inside the module**, not in repo-level `tests/`. They run with
   `pytest optional-skills/_toolkit/<module>/tests/` standalone.
5. **No `SKILL.md`** anywhere under `_toolkit/`. This directory is libraries,
   not skills.
6. **No global state, no env vars consumed silently**. Modules accept config
   via constructor / function arguments. Calling skill is responsible for
   reading env.
7. **Document the security posture** in module README: what redaction it
   applies, what defaults are safe, what `--unsafe` flags exist and what they
   gate.

---

## How a skill imports a `_toolkit/` module

The repo doesn't have `optional-skills/` on `PYTHONPATH` by default. Each skill
script that needs a toolkit module adds the path explicitly at the top:

```python
# At the top of optional-skills/security/<skill>/scripts/<file>.py
from __future__ import annotations
import sys
from pathlib import Path

# parents[3] climbs: scripts -> <skill> -> security -> optional-skills
_TOOLKIT = Path(__file__).resolve().parents[3] / "_toolkit"
if str(_TOOLKIT) not in sys.path:
    sys.path.insert(0, str(_TOOLKIT))

from ws_recorder import WSRecorder            # toolkit module
from ws_recorder.tls import build_ca_chain    # submodule access
```

If your skill is at a different depth (e.g. directly under
`optional-skills/<skill>/scripts/`, no category dir), use `parents[2]`. Make
the depth adjustment a one-line comment so it's reviewable.

**Why not a conftest / sys.path hook**: keeping the import path local to each
script means the script remains runnable directly (`python scripts/foo.py ...`)
without environment setup. Trade-off accepted.

---

## How a skill cites a `_toolkit/` dependency

In the skill's `SKILL.md`, under a new "Dependencies" section, list the
toolkit modules used and at what version:

```markdown
## Dependencies

- `_toolkit/ws_recorder` (>=0.1)  — authorized WebSocket capture; replaces inline `mitm_ws_probe.py`.
- `_toolkit/cookie_extractor` (>=0.2) — Keychain / Chrome cookie reads.
```

The version comes from the module's `__init__.py` `__version__`. Bump when
breaking change; keep skills pinned by minimum version.

---

## Stability contract

Toolkit modules sit lower in the stack than skills. They must be **more stable**:

- No breaking change without bumping major version + updating all importers in
  the same PR.
- Public API surface is small and obvious. If you find yourself wanting to
  expose 20 functions, the module is doing too much — split it.
- A toolkit module that only one skill uses is **not yet a toolkit module** —
  move it back to that skill until a second consumer appears.
