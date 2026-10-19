# Release verification

Verified on 2026-10-01 in Linux with Python 3.12.14 and setuptools 84.0.0.
All inputs were synthetic. No real Codex configuration was used.

- `python3 -B -m unittest discover -s tests -v`: **39 tests passed, zero skips**.
  This includes actual symlink, dangling symlink, ancestor escape and hard-link
  rejection, plus simulated Windows reparse-point attributes.
- `python3 -B tools/demo.py`: passed; actual summarized output is in
  [demo.txt](demo.txt). Matching config exits 0; deliberate drift exits 1.
- Built a wheel with `python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir dist .`.
- Installed that wheel using `pip install --no-deps --no-index` into a new venv.
  Ran the installed command outside the source root: version, policy, inspect,
  export, render, matching comparison and drift comparison all passed.
- Built a source distribution and checked it includes tests, examples, bilingual
  documentation and the recorded demo, without temporary runtime output.
- Reviewed source files and packaging inventory. Credential/private-user-path
  pattern checks found no matches; this is not exhaustive secret detection.
- All relative Markdown documentation links resolved locally.
- Confirmed the official `rust-v0.159.3` annotated tag resolves to the documented
  commit and independently calculated its schema Git blob ID.
- CI template action commits were resolved from the official action repositories.

## Hosted verification

The reviewed workflow is included at `.github/workflows/ci.yml`.
On 2026-10-02, the [2026-10-01 Actions run](https://github.com/BohaoWorks/codex-baseline/actions/runs/36834795350)
was verified successful for commit `66a8c325caab692ca6ca74552154433725f82887`:
all four Linux/Windows and Python 3.11/3.14 jobs passed. This result applies
only to that commit; later commits need their own checks.
No runtime model compatibility or effective Codex layered configuration was tested.

## Rendered-size regression — 2026-10-19

Verified locally on Linux with Python 3.12.14 and setuptools 84.0.0, using only
synthetic inputs. This section does not claim a hosted CI result for the change.

- Reproduced a valid 256,492-byte overlay containing 64 distinct Windows paths,
  each 4,003 characters long. With a one-model baseline, backslash escaping
  produced a 384,514-byte config: `render` succeeded, but `compare` rejected it
  against the existing 256 KiB read limit.
- Added regression tests first. The new-output, existing-empty-output and
  262,145-byte cases failed before the fix; the 262,144-byte case and ordinary
  Windows/Unicode round-trip case already passed.
- Added a serialized-byte-size check before any output-directory creation or
  file writes. Oversized renders now exit 2 without exposing paths or contents,
  creating a directory or filling an existing empty one. The read limit is
  unchanged; an exactly 262,144-byte generated config still compares successfully.
- `python -B -m unittest discover -s tests -v`: **42 tests passed, zero skips**.
- `python -B tools/demo.py`: passed, including matching exit 0 and drift exit 1.
- Built a wheel offline with `python -m pip wheel --no-deps --no-build-isolation
  --no-index --wheel-dir WHEEL_DIR .` and installed it into a fresh venv with
  `pip install --no-deps --no-index`.
- Outside the source checkout, ran the same 42 tests and demo against the
  installed package; all passed. The installed `codex-baseline --version` and
  `codex-baseline policy` commands passed. Tool version remains `0.1.0` and the
  supported policy remains `codex-cli-0.159.3-small-v1`.
