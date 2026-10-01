# Versioned subset

Tool: `0.1.0`; policy: `codex-cli-0.159.3-small-v1`; source version: `0.159.3`.

Evidence checked on 2026-10-01:

- [Official configuration reference](https://developers.openai.com/codex/config-reference/).
- [Official release rust-v0.159.3](https://github.com/openai/codex/releases/tag/rust-v0.159.3).
- [Schema at commit 01fc69f4026735edfdf6789820549727a4867b11](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/core/config.schema.json), blob `af8f05ee51c34ca281ad72b03e3fe22175a88579`.

The official sources establish key spelling and types. **Portability categories
and the stricter accepted subset are this project's policy**, not an upstream
Codex classification. Schema contents are not vendored. Schema changes require
a separately reviewed policy; no live schema lookup occurs at runtime.

| Field | Category | Accepted subset |
| --- | --- | --- |
| `model` | portable | 1–128 ASCII letters/digits/`_`/`.`/`-`, starting with a letter/digit; secret-like values refused |
| `model_reasoning_effort` | portable | `low`, `medium`, `high`, `xhigh`, `max`, `ultra` |
| `model_reasoning_summary` | portable | `auto`, `concise`, `detailed`, `none` |
| `model_verbosity` | portable | `low`, `medium`, `high` |
| `approval_policy` | portable | `on-request`, `never`; structured granular policy excluded |
| `sandbox_mode` | portable | `read-only`, `workspace-write`, `danger-full-access` |
| `check_for_update_on_startup` | portable | boolean |
| `hide_agent_reasoning` | portable | boolean |
| `show_raw_agent_reasoning` | portable | boolean |
| `sandbox_workspace_write.network_access` | portable | boolean |
| `sandbox_workspace_write.exclude_slash_tmp` | portable | boolean |
| `sandbox_workspace_write.exclude_tmpdir_env_var` | portable | boolean |
| `file_opener` | machine-local | `vscode`, `vscode-insiders`, `windsurf`, `cursor`, `none` |
| `sandbox_workspace_write.writable_roots` | machine-local | up to 64 absolute POSIX/Windows paths, without traversal, variables, URLs, control characters or Windows alternate streams |

Reasoning effort is an open string in the upstream schema. This tool intentionally
accepts only the six advertised examples above. Neither model availability nor
support for a particular model's reasoning effort is tested.

Recognized **blocked** top-level sections: `mcp_servers`, `model_providers`,
`projects`, `notify`, `history`, `cli_auth_credentials_store`,
`forced_chatgpt_workspace_id`, `forced_login_method`, `plugins`, `marketplaces`,
`hooks`, `skills`. Any presence stops export/render. Their children are never
printed or exported. Everything else, including `model_provider`, `features`,
`profiles` and `AGENTS.md` references, is **unknown** in this version and refused.
An empty supported table is refused as an unrecognized structure.

The input limit is 256 KiB, with bounded structural depth/node count. Canonical
TOML orders fields and tables, preserves Unicode and always uses LF newlines.
Baseline manifests record the policy, source version, upstream commit and
baseline SHA-256. Rendered manifests additionally record each field's origin.
All manifest file names and metadata fields are validated against fixed values.
