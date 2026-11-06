"""Explicit inputs only: no automatic Codex-home discovery or application."""

import argparse
import json
import sys

from . import __version__
from .core import BaselineError, check_version, compare_config, export_baseline, inspect_data, parse_config, render_config
from .policy import BLOCKED, CODEX_VERSION, POLICIES, REFERENCE, RULES


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse diagnostics can echo unknown arguments, including private paths.
        raise BaselineError("invalid command-line arguments; run --help; argument contents omitted")


def parser() -> argparse.ArgumentParser:
    root = _ArgumentParser(prog="codex-baseline", description="Offline Codex baseline compiler. Writes only to an explicit empty output directory.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    policy = commands.add_parser("policy", help="show a pinned, deliberately small allowlist")
    policy.add_argument("--codex-version", default=CODEX_VERSION, help="explicit policy selection; default: " + CODEX_VERSION)
    inspect = commands.add_parser("inspect", help="classify fields without printing values or unknown names")
    inspect.add_argument("--config", required=True)
    inspect.add_argument("--codex-version", required=True, help="explicit compatibility assertion; supported: " + ", ".join(POLICIES))
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
    try:
        args = parser().parse_args(argv)
        status = 0
        if args.command == "policy":
            policy = check_version(args.codex_version)
            result = {"tool_version": __version__, "policy_id": policy.policy_id, "codex_version": policy.codex_version,
                      "documentation": REFERENCE, "schema_url": policy.schema_url,
                      "schema_commit": policy.schema_commit, "schema_blob": policy.schema_blob,
                      "fields": [{"field": ".".join(key), "category": rule.category, "kind": rule.kind,
                                  "choices": list(rule.choices), "reason": rule.reason}
                                 for key, rule in sorted(RULES.items())], "blocked": BLOCKED}
        elif args.command == "inspect":
            check_version(args.codex_version)
            result = inspect_data(parse_config(args.config), version=args.codex_version)
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
