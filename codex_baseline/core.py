"""Validation, deterministic TOML, and bundle operations. Standard library only."""

from hashlib import sha256
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import tomllib
from urllib.parse import parse_qsl, urlsplit

from . import __version__
from .policy import BLOCKED, CODEX_VERSION, POLICY_ID, RULES, SCHEMA_COMMIT, valid_value

MAX_INPUT_BYTES = 256 * 1024
MAX_NODES = 2048
MAX_DEPTH = 16
FORMAT = "codex-baseline/1"


class BaselineError(Exception):
    """Messages must never contain untrusted contents or filesystem paths."""


def check_version(version: str) -> None:
    if version != CODEX_VERSION:
        raise BaselineError(f"unsupported Codex version; supported version: {CODEX_VERSION}")


def checked_path(raw: str | Path, *, writing: bool = False) -> Path:
    text = str(raw)
    if not text or "\x00" in text or any(ord(char) < 32 for char in text):
        raise BaselineError("invalid explicit path")
    path = Path(text)
    if ".." in path.parts or ".." in PureWindowsPath(text).parts:
        raise BaselineError("path traversal components are refused")
    path = path.absolute()
    if writing:
        if any(part.casefold() in {".codex", ".agents"} for part in path.parts):
            raise BaselineError("writes to Codex or agent home directories are refused")
        for variable in ("HOME", "USERPROFILE", "CODEX_HOME"):
            home = os.environ.get(variable)
            if home:
                home_path = Path(home).resolve()
                if path == home_path or (variable == "CODEX_HOME" and path.is_relative_to(home_path)):
                    raise BaselineError("writes to a home directory are refused")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise BaselineError("cannot inspect explicit path") from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise BaselineError("symlinks, junctions and reparse points are refused")
    return path


def read_explicit(raw: str | Path, suffix: str) -> bytes:
    path = checked_path(raw)
    if path.suffix.casefold() != suffix or any(
        part.casefold() in {"auth.json", "auth.toml", "sessions", "session", "state", "history.jsonl"}
        for part in path.parts
    ):
        raise BaselineError("only the explicitly requested supported file type may be read")
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink > 1:
            raise BaselineError("input must be a regular file with no hard-link aliases")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
                raise BaselineError("input must be a regular file with no hard-link aliases")
            data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raise BaselineError("cannot read explicit input file") from None
    if len(data) > MAX_INPUT_BYTES:
        raise BaselineError("input exceeds the 256 KiB limit")
    return data


def parse_config(raw: str | Path) -> dict:
    data = read_explicit(raw, ".toml")
    try:
        return tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError, RecursionError):
        raise BaselineError("invalid UTF-8 or TOML; input contents omitted") from None


_SECRET_KEY = re.compile(r"(^|[_-])(api[_-]?key|token|password|secret|credential[s]?|authorization|cookie)([_-]|$)", re.I)
_SECRET_TEXT = re.compile(r"(?:\b(?:sk-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16})\b|-----BEGIN .*PRIVATE KEY-----|\bBearer\s+\S+)", re.I)
_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"<>]+")


def has_sensitive_material(data: dict) -> bool:
    """Conservative heuristics, NOT an exhaustive secret detector."""
    count = 0

    def walk(value: object, depth: int = 0) -> bool:
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise BaselineError("input exceeds structural limits")
        if isinstance(value, dict):
            for key, child in value.items():
                if _SECRET_KEY.search(key) or walk(key, depth + 1) or walk(child, depth + 1):
                    return True
        elif isinstance(value, list):
            return any(walk(child, depth + 1) for child in value)
        elif isinstance(value, str):
            if _SECRET_TEXT.search(value):
                return True
            for match in _URL.finditer(value):
                try:
                    url = urlsplit(match.group())
                    if url.username is not None or url.password is not None:
                        return True
                    for key, _ in parse_qsl(url.query, keep_blank_values=True):
                        if _SECRET_KEY.search(key) or key.casefold() in {"key", "sig", "signature"}:
                            return True
                except ValueError:
                    return True
        return False

    return walk(data)


def inspect_data(data: dict) -> dict:
    fields: list[dict] = []
    unknown_count = 0
    invalid_count = 0
    flat: dict[tuple[str, ...], object] = {}

    def visit(value: object, path: tuple[str, ...]) -> None:
        nonlocal unknown_count, invalid_count
        if path in RULES:
            rule = RULES[path]
            valid = valid_value(rule, value)
            fields.append({"field": ".".join(path), "category": rule.category,
                           "valid": valid, "reason": rule.reason})
            if valid:
                flat[path] = value
            else:
                invalid_count += 1
        elif any(candidate[:len(path)] == path for candidate in RULES):
            if not isinstance(value, dict) or not value:
                unknown_count += 1
            else:
                for key in sorted(value):
                    visit(value[key], (*path, key))
        else:
            unknown_count += 1

    sensitive = has_sensitive_material(data)
    for key in sorted(data):
        if key in BLOCKED:
            fields.append({"field": key, "category": "blocked", "valid": False, "reason": BLOCKED[key]})
        else:
            visit(data[key], (key,))
    fields.sort(key=lambda field: field["field"])
    blocked_count = sum(field["category"] == "blocked" for field in fields)
    return {
        "policy_id": POLICY_ID, "codex_version": CODEX_VERSION,
        "fields": fields, "unknown_count": unknown_count,
        "invalid_count": invalid_count, "blocked_count": blocked_count,
        "sensitive_material_detected": sensitive,
        "accepted": not (unknown_count or invalid_count or blocked_count or sensitive),
        "_flat": flat,
    }


def validated(data: dict, *, baseline: bool = False) -> dict:
    report = inspect_data(data)
    if not report["accepted"]:
        raise BaselineError("configuration refused: blocked, unknown, invalid or potentially sensitive material; run inspect")
    flat = report["_flat"]
    if baseline and any(RULES[key].category != "portable" for key in flat):
        raise BaselineError("baseline contains machine-local fields; use an overlay")
    return flat


def dump_toml(flat: dict) -> bytes:
    lines = ["# Generated by codex-baseline. Review before any manual use."]

    def encode(value: object) -> str:
        if type(value) is bool:
            return "true" if value else "false"
        return json.dumps(value, ensure_ascii=False)

    for key in sorted(key for key in flat if len(key) == 1):
        lines.append(f"{key[0]} = {encode(flat[key])}")
    tables = sorted({key[:-1] for key in flat if len(key) > 1})
    for table in tables:
        lines.extend(["", "[" + ".".join(table) + "]"])
        for key in sorted(key for key in flat if key[:-1] == table):
            lines.append(f"{key[-1]} = {encode(flat[key])}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def write_bundle(raw: str | Path, files: dict[str, bytes]) -> None:
    path = checked_path(raw, writing=True)
    try:
        if path.exists():
            if not path.is_dir() or any(path.iterdir()):
                raise BaselineError("output must be a new directory or an empty directory; overwrite refused")
        else:
            path.mkdir()  # Parent must already exist; never invent target paths.
        for name, data in files.items():
            if name not in {"baseline.toml", "config.toml", "manifest.json"}:
                raise BaselineError("invalid internal output name")
            checked_path(path, writing=True)
            target = path / name
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
    except OSError:
        raise BaselineError("output write refused or failed; any partial files were left for review") from None


def export_baseline(config: str | Path, version: str, output: str | Path) -> dict:
    check_version(version)
    flat = validated(parse_config(config))
    portable = {key: value for key, value in flat.items() if RULES[key].category == "portable"}
    if not portable:
        raise BaselineError("no portable fields to export")
    content = dump_toml(portable)
    manifest = {
        "format": FORMAT, "kind": "baseline", "tool_version": __version__,
        "policy_id": POLICY_ID, "codex_version": CODEX_VERSION,
        "schema_commit": SCHEMA_COMMIT, "files": {"baseline.toml": digest(content)},
    }
    write_bundle(output, {"baseline.toml": content, "manifest.json": json_bytes(manifest)})
    return {"action": "export", "portable_fields": len(portable),
            "machine_local_fields_excluded": len(flat) - len(portable),
            "sha256": digest(content), "policy_id": POLICY_ID}


def load_baseline(raw: str | Path) -> tuple[dict, str]:
    root = checked_path(raw)
    try:
        if not root.is_dir() or {path.name for path in root.iterdir()} != {"baseline.toml", "manifest.json"}:
            raise BaselineError("baseline directory must contain exactly baseline.toml and manifest.json")
    except OSError:
        raise BaselineError("cannot inspect baseline directory") from None
    try:
        def unique_pairs(pairs: list) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise BaselineError("duplicate manifest keys are refused")
                result[key] = value
            return result
        manifest = json.loads(read_explicit(root / "manifest.json", ".json"), object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise BaselineError("invalid manifest JSON; contents omitted") from None
    expected_keys = {"format", "kind", "tool_version", "policy_id", "codex_version", "schema_commit", "files"}
    if not isinstance(manifest, dict) or set(manifest) != expected_keys:
        raise BaselineError("unknown or missing manifest fields")
    expected = {"format": FORMAT, "kind": "baseline", "tool_version": __version__,
                "policy_id": POLICY_ID, "codex_version": CODEX_VERSION, "schema_commit": SCHEMA_COMMIT}
    if any(manifest[key] != value for key, value in expected.items()):
        raise BaselineError("unsupported manifest version or policy")
    files = manifest["files"]
    if not isinstance(files, dict) or set(files) != {"baseline.toml"}:
        raise BaselineError("manifest file names are refused")
    content = read_explicit(root / "baseline.toml", ".toml")
    if files["baseline.toml"] != digest(content):
        raise BaselineError("baseline integrity check failed")
    try:
        data = tomllib.loads(content.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError, RecursionError):
        raise BaselineError("invalid baseline TOML; contents omitted") from None
    return validated(data, baseline=True), digest(content)


def merged_config(baseline: str | Path, overlay: str | Path | None) -> tuple[dict, dict, str]:
    flat, baseline_hash = load_baseline(baseline)
    origins = {key: "baseline" for key in flat}
    if overlay is not None:
        local = validated(parse_config(overlay))
        flat.update(local)
        origins.update({key: "overlay" for key in local})
    return flat, origins, baseline_hash


def render_config(baseline: str | Path, overlay: str | Path | None, output: str | Path) -> dict:
    flat, origins, baseline_hash = merged_config(baseline, overlay)
    content = dump_toml(flat)
    manifest = {"format": FORMAT, "kind": "rendered", "tool_version": __version__,
                "policy_id": POLICY_ID, "codex_version": CODEX_VERSION,
                "baseline_sha256": baseline_hash, "files": {"config.toml": digest(content)},
                "origins": {".".join(key): origins[key] for key in sorted(origins)}}
    write_bundle(output, {"config.toml": content, "manifest.json": json_bytes(manifest)})
    return {"action": "render", "fields": len(flat), "overlay_fields": sum(origin == "overlay" for origin in origins.values()),
            "sha256": digest(content), "policy_id": POLICY_ID}


def compare_config(baseline: str | Path, overlay: str | Path | None, config: str | Path) -> dict:
    expected, origins, baseline_hash = merged_config(baseline, overlay)
    actual = validated(parse_config(config))
    differences = []
    for key in sorted(set(expected) | set(actual)):
        if key in expected and key in actual and expected[key] == actual[key]:
            continue
        change = "unexpected" if key not in expected else "missing" if key not in actual else "changed"
        rule = RULES[key]
        difference = {"field": ".".join(key), "category": rule.category,
                      "change": change, "expected_source": origins.get(key, "unspecified"),
                      "reason": rule.reason}
        if rule.category == "portable":
            difference.update(expected=expected.get(key), actual=actual.get(key))
        else:
            difference["values"] = "machine-local values omitted"
        differences.append(difference)
    return {"action": "compare", "matches": not differences,
            "baseline_sha256": baseline_hash, "differences": differences}
