"""Explicit inputs only: no automatic Codex-home discovery or application."""

import argparse
import json
import sys

from . import __version__
from .core import BaselineError, check_version, compare_config, export_baseline, inspect_data, parse_config, render_config
from .policy import BLOCKED, CODEX_VERSION, POLICY_ID, REFERENCE, RULES, SCHEMA_BLOB, SCHEMA_COMMIT, SCHEMA_URL


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="codex-baseline", description="Offline Codex baseline compiler. Writes only to an explicit empty output directory.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("policy", help="show the pinned, deliberately small allowlist")
    inspect = commands.add_parser("inspect", help="classify fields without printing values or unknown names")
    inspect.add_argument("--config", required=True)
    inspect.add_argument("--codex-version", required=True, help=f"explicit compatibility assertion; supported: {CODEX_VERSION}")
    export = commands.add_parser("export", help="export portable fields and their integrity manifest")
    export.add_argument("--config", required=True)
    export.add_argument("--codex-version", required=True)
    export.add_argument("--out", required=True)
    for name in ("render", "compare"):
        command = commands.add_parser(name, help="compile a reviewable config" if name == "render" else "explain drift from a baseline plus overlay")
        command.add_argument("--baseline", required=True, help="directory containing baseline.toml and manifest.json")
        command.add_argument("--overlay", help="explicit machine overlay TOML; present fields replace baseline fields")
        command.add_argument("--out" if name == "render" else "--config", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        status = 0
        if args.command == "policy":
            result = {"tool_version": __version__, "policy_id": POLICY_ID, "codex_version": CODEX_VERSION,
                      "documentation": REFERENCE, "schema_url": SCHEMA_URL,
                      "schema_commit": SCHEMA_COMMIT, "schema_blob": SCHEMA_BLOB,
                      "fields": [{"field": ".".join(key), "category": rule.category, "kind": rule.kind,
                                  "choices": list(rule.choices), "reason": rule.reason}
                                 for key, rule in sorted(RULES.items())], "blocked": BLOCKED}
        elif args.command == "inspect":
            check_version(args.codex_version)
            result = inspect_data(parse_config(args.config))
            del result["_flat"]
            status = 0 if result["accepted"] else 2
        elif args.command == "export":
            result = export_baseline(args.config, args.codex_version, args.out)
        elif args.command == "render":
            result = render_config(args.baseline, args.overlay, args.out)
        else:
            result = compare_config(args.baseline, args.overlay, args.config)
            status = 0 if result["matches"] else 1
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return status
    except BaselineError as error:
        print(f"codex-baseline: {error}", file=sys.stderr)
        return 2
    except (OSError, RecursionError):
        print("codex-baseline: operation failed; input contents omitted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
