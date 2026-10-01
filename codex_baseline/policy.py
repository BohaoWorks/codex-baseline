"""Reviewed subset, pinned to an upstream release. No runtime downloads."""

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
import re

CODEX_VERSION = "0.159.3"
POLICY_ID = "codex-cli-0.159.3-small-v1"
SCHEMA_COMMIT = "01fc69f4026735edfdf6789820549727a4867b11"
SCHEMA_BLOB = "af8f05ee51c34ca281ad72b03e3fe22175a88579"
REFERENCE = "https://developers.openai.com/codex/config-reference/"
SCHEMA_URL = (
    "https://github.com/openai/codex/blob/" + SCHEMA_COMMIT
    + "/codex-rs/core/config.schema.json"
)


@dataclass(frozen=True)
class Rule:
    category: str
    kind: str
    reason: str
    choices: tuple[str, ...] = ()


RULES = {
    ("model",): Rule("portable", "identifier", "shared model preference; availability is not verified"),
    ("model_reasoning_effort",): Rule(
        "portable", "enum", "shared reasoning preference; levels depend on the selected model",
        ("low", "medium", "high", "xhigh", "max", "ultra"),
    ),
    ("model_reasoning_summary",): Rule("portable", "enum", "shared summary preference", ("auto", "concise", "detailed", "none")),
    ("model_verbosity",): Rule("portable", "enum", "shared output preference", ("low", "medium", "high")),
    ("approval_policy",): Rule("portable", "enum", "explicit shared approval policy; granular form is outside this subset", ("on-request", "never")),
    ("sandbox_mode",): Rule("portable", "enum", "explicit shared sandbox policy", ("read-only", "workspace-write", "danger-full-access")),
    ("check_for_update_on_startup",): Rule("portable", "bool", "shared update preference"),
    ("hide_agent_reasoning",): Rule("portable", "bool", "shared display preference"),
    ("show_raw_agent_reasoning",): Rule("portable", "bool", "shared display preference"),
    ("sandbox_workspace_write", "network_access"): Rule("portable", "bool", "explicit shared sandbox network policy"),
    ("sandbox_workspace_write", "exclude_slash_tmp"): Rule("portable", "bool", "shared temporary-directory policy"),
    ("sandbox_workspace_write", "exclude_tmpdir_env_var"): Rule("portable", "bool", "shared temporary-directory policy"),
    ("file_opener",): Rule("machine-local", "enum", "installed editor varies by machine", ("vscode", "vscode-insiders", "windsurf", "cursor", "none")),
    ("sandbox_workspace_write", "writable_roots"): Rule("machine-local", "paths", "absolute writable paths stay in the local overlay"),
}

# These are documented upstream sections, deliberately NOT supported for export.
# They are opaque: inspect reports only their names, never their nested keys/values.
BLOCKED = {
    "mcp_servers": "MCP commands, environment and remote authentication are outside this subset",
    "model_providers": "custom providers can contain authentication and endpoint settings",
    "projects": "project trust is machine state",
    "notify": "external commands are outside this subset",
    "history": "history configuration is outside this subset; no history file is read",
    "cli_auth_credentials_store": "authentication configuration is excluded",
    "forced_chatgpt_workspace_id": "account/workspace identifiers are excluded",
    "forced_login_method": "authentication configuration is excluded",
    "plugins": "plugin/runtime state is outside this subset",
    "marketplaces": "marketplace/runtime state is outside this subset",
    "hooks": "hook commands and trust state are outside this subset",
    "skills": "skill files and runtime state are outside this subset",
}


def valid_value(rule: Rule, value: object) -> bool:
    if rule.kind == "bool":
        return type(value) is bool
    if rule.kind == "enum":
        return type(value) is str and value in rule.choices
    if rule.kind == "identifier":
        return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) is not None
    if rule.kind == "paths":
        if type(value) is not list or len(value) > 64:
            return False
        for item in value:
            if type(item) is not str or not item or len(item) > 4096:
                return False
            if any(ord(char) < 32 or ord(char) == 127 for char in item) or any(char in item for char in ("$", "%", "~")):
                return False
            posix, windows = PurePosixPath(item), PureWindowsPath(item)
            if ".." in posix.parts or ".." in windows.parts:
                return False
            if not (posix.is_absolute() or windows.is_absolute()):
                return False
            # No URLs, alternate data streams, or drive-relative paths.
            if ":" in item and not re.match(r"^[A-Za-z]:[/\\][^:]*$", item):
                return False
        return True
    return False
