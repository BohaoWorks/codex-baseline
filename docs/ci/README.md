# CI scope

The workflow is [../../.github/workflows/ci.yml](../../.github/workflows/ci.yml).
`ci.yml` here retains the reviewed reference copy. Both use pinned official
action commits and test Python 3.11/3.14 on Linux and Windows.

The [initial published commit passed all four jobs](https://github.com/BohaoWorks/codex-baseline/actions/runs/36834795350)
on 2026-10-01; see the exact commit in the verification record. Inspect the
Actions run for each later commit before treating its CI as passed. The workflow has read-only repository
permission, no secrets, no deploy/publish steps and bounded execution time.
It runs synthetic tests, the CLI demo, then installs the package and repeats the
behavior tests with `python -B tools/check_installed.py`. This helper copies the
tests into a temporary workspace, clears inherited `PYTHONPATH`, and checks the
imported package against installed-distribution metadata before running tests.
Editable/check-out imports, missing installations, empty suites, and test failures
fail the check. The helper itself installs nothing and uses no network. The
installed command also receives a separate `policy` smoke check.
Local verification is documented in [../verification.md](../verification.md).

This check detects common source/installed-package mix-ups. It trusts the runner
and its installation metadata; it is not an integrity verifier or a defense
against a deliberately modified Python environment. Windows behavior still
needs the exact candidate commit's hosted CI result.
