# Safety boundaries

The CLI is an offline compiler for explicit inputs, not a credential scrubber or
a tool that applies settings to a running Codex installation.

It reads only a named TOML input and, for bundle operations, `baseline.toml` and
`manifest.json` in a named bundle. It does not recursively discover or follow
paths in TOML. It never opens auth files, session trees, databases or histories.
File names such as `auth.toml` and input paths inside `sessions/` or `state/` are
also refused. It never executes input commands or calls any network API.

All supported fields are type checked. Unknown keys (including nested keys),
blocked sections and obvious token/key material cause refusal. URL userinfo,
credential-bearing query parameters, common token prefixes, private-key markers,
Bearer strings and sensitive key names are screened. Comments are parsed away
and never copied. These are **limited heuristics**; arbitrary secret strings,
encoded material or sensitive data hidden in an otherwise valid identifier/path
can evade them. Review every input and output before sharing. No claim of 100%
secret detection is made.

Inspection does not print values or unrecognized field names. Parse and IO errors
omit source text and paths. Drift reports show only validated portable values;
machine-local values are omitted. Baseline metadata does not retain source file
names, local paths, input hashes, time, usernames or device IDs.

Explicit IO paths cannot contain `..`. Existing symlinks, Windows junctions and
other reparse points in a file or any ancestor are refused. Hard-linked inputs,
nonregular inputs and oversized files are refused. A bundle accepts exactly its
two fixed files; user-supplied manifest names never become output paths. Writes
use exclusive creation and require a new or empty output directory. The tool
refuses output paths within `.codex`/`.agents`, as well as the exact HOME,
USERPROFILE root and the entire explicitly configured CODEX_HOME tree. It creates no missing parent directories and
performs no automatic import. Output files request mode `0600` where supported;
Windows permissions follow the host ACL behavior.

Use a private directory that other processes cannot modify. Filesystem checks
and exclusive leaf creation **do not provide complete protection against an
active concurrent attacker replacing ancestors**, especially on Windows. The
hash manifest is unsigned and can be replaced together with its data; it is an
integrity check, not a trust mechanism. A failed write may leave newly created
partial files for manual review; no existing files are removed automatically.

Safety-related configuration values such as `never`, `danger-full-access` or
`network_access = true` are valid values, not recommendations. A baseline or
overlay can weaken a future Codex run's policy. Compare and review both the
generated values and origin manifest before any separate manual application.

## Reporting

Open an issue containing only a minimal synthetic reproducer and affected
version. Do not attach live configuration, credentials, session data or private
paths. If a reproducer itself would expose a vulnerability dangerously, first
ask the maintainer for a private reporting channel without publishing the details.
