# codex-baseline

**Keep a small Codex configuration baseline consistent across machines.**

[中文说明](README.zh-CN.md) · [Terminal demo](docs/demo.txt) · [Supported fields](docs/scope.md) · [Safety boundaries](SECURITY.md)

One reviewed TOML baseline, one local overlay, and an explainable drift report.
Python 3.11+, zero runtime dependencies, no account or API key required.
Version **0.1.0** supports a reviewed subset of **Codex CLI 0.159.3** only.
This is an independent project, unaffiliated with OpenAI.

```text
explicit shared.toml ── inspect ── export ── baseline.toml + manifest.json
                                                     │
machine overlay.toml ─────────────────────────────────┤
                                                     ▼
                                                 render
                                                     │
                                         review/config.toml + manifest.json
                                                     │
explicit observed.toml ─────────────────────────── compare
                                          field + origin + reason for drift
```

## Try it in two minutes

Clone the repository and run from its root. These examples use synthetic paths
and a placeholder model; they never contact a model or read your Codex home.
On Windows, use `py` where the commands below say `python`.

```sh
git clone https://github.com/BohaoWorks/codex-baseline.git
cd codex-baseline
python -m codex_baseline inspect --config examples/shared.toml --codex-version 0.159.3
python -m codex_baseline export --config examples/shared.toml --codex-version 0.159.3 --out baseline-demo
python -m codex_baseline render --baseline baseline-demo --overlay examples/mac-overlay.toml --out review-demo
python -m codex_baseline compare --baseline baseline-demo --overlay examples/mac-overlay.toml --config review-demo/config.toml
python -m codex_baseline compare --baseline baseline-demo --overlay examples/mac-overlay.toml --config examples/drifted.toml
```

The final command exits **1** and identifies three differences:

```text
file_opener: changed; source=overlay; machine-local values omitted
model_reasoning_effort: changed; source=baseline; 'low' -> expected 'high'
sandbox_workspace_write.writable_roots: changed; source=overlay; machine-local values omitted
```

Each output directory must be new or empty. To repeat the demo without managing
output folders, run `python tools/demo.py`; it uses and cleans synthetic folders
under this checkout's ignored `work/` directory. [Recorded output](docs/demo.txt)
comes from this script.

## Install

Running `python -m codex_baseline` from a clone requires only the Python standard
library. To install the `codex-baseline` command into your own virtual environment:

```sh
python -m venv .venv
# macOS/Linux:
. .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install .
codex-baseline policy
```

Source installation may fetch the setuptools build backend. The installed CLI
has no dependencies and makes no network requests. No PyPI package is published;
install from this repository or a locally built wheel.

## Commands and contracts

| Command | Result |
| --- | --- |
| `inspect --config FILE --codex-version 0.159.3` | Classifies known fields as portable, machine-local or blocked. Counts unknown fields without printing their names or any values. |
| `export --config FILE --codex-version 0.159.3 --out DIR` | Validates the entire supported input, exports only portable fields, and writes an integrity manifest. |
| `render --baseline DIR [--overlay FILE] --out DIR` | Verifies the baseline hash and policy, then generates a config plus a field-origin manifest for review. |
| `compare --baseline DIR [--overlay FILE] --config FILE` | Reports missing, unexpected and changed fields against the generated expectation. |
| `policy` | Prints the allowlist, constraints, policy identifier and official evidence links. |

The overlay wins **only for fields explicitly present**. Arrays replace the
baseline value; no implicit deletion, defaults, profile resolution or include
processing occurs. Machine-local fields belong in the overlay and are omitted
from export. Compare checks the explicitly supplied file, not Codex's full
effective configuration after project layers, profiles, policies and CLI flags.

Exit codes: **0** accepted/matching, **1** valid configuration with drift,
**2** rejected input or operation. Every report is JSON except concise errors.
Source versions must be explicitly asserted; the tool cannot discover or verify
your installed Codex version. A model identifier passing the subset validator
does not establish that a model or reasoning level is available to your account.

## Deliberately narrow first release

There are **12 portable fields and 2 machine-local fields** in the allowlist;
see [the exact field matrix](docs/scope.md). Blocked sections and unknown fields
stop export and render rather than being silently removed. If your explicit
config contains unsupported sections, inspect it, then create a separate,
reviewed subset input. Do not copy the entire Codex home directory.

No auth/session/database reads, automatic discovery, automatic installation into
Codex home, synchronization daemon, executable commands from config, provider/MCP
templates, AGENTS.md or skill bundles are included. Network settings in generated
TOML express future Codex behavior; this compiler itself stays offline. Generated
approval and sandbox policies may permit powerful actions when manually used
with Codex, so review the generated file before any later application.

Manifests contain no input paths, original content hashes, timestamps or machine
identifiers. Identical supported inputs produce byte-identical bundles. SHA-256
detects accidental changes; it is **not** a signature or proof of provenance.
The policy is pinned to [Codex 0.159.3's official schema](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/core/config.schema.json)
and checked against the [official configuration reference](https://developers.openai.com/codex/config-reference/).

## Why this exists

Real upstream requests describe [fleet baselines and per-machine overrides](https://github.com/openai/codex/issues/26691),
[portable setup with review before application](https://github.com/openai/codex/issues/31130),
and [user settings mixed with generated state](https://github.com/openai/codex/issues/45627).
This release addresses a small CLI configuration portion of those needs. It does
not resolve the upstream issues or offer whole-machine migration.

## Development and maintenance

```sh
python -m unittest discover -s tests -v
python tools/demo.py
python -m pip wheel --no-deps --wheel-dir dist .
```

Tests use synthetic data only. They cover overlay precedence, deterministic
manifests, Unicode paths, malformed TOML, secret-related refusal, unknown nested
keys, hash tampering and filesystem boundaries. Actual symlink tests may be
skipped when the host does not grant symlink creation; reparse-point rejection is
also tested independently.

**CI:** [.github/workflows/ci.yml](.github/workflows/ci.yml) runs synthetic tests,
the demo and installed-package checks on Linux and Windows. The [initial published commit passed all four CI jobs](https://github.com/BohaoWorks/codex-baseline/actions/runs/36834795350)
on 2026-10-01. Check the Actions tab for the result of each later commit.
See the [CI notes](docs/ci/README.md) for permissions and scope.

See [CONTRIBUTING.md](CONTRIBUTING.md) for small, evidence-backed contributions
and [CHANGELOG.md](CHANGELOG.md) for releases. Open a minimal reproducible issue
using synthetic inputs. Do not upload your real configuration or credentials.

MIT licensed. No telemetry, paid services, API calls or runtime subscriptions.
