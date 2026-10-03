# CI scope

The workflow is [../../.github/workflows/ci.yml](../../.github/workflows/ci.yml).
`ci.yml` here retains the reviewed reference copy. Both use pinned official
action commits and test Python 3.11/3.14 on Linux and Windows.

The [initial published commit passed all four jobs](https://github.com/BohaoWorks/codex-baseline/actions/runs/36834795350)
on 2026-10-01; see the exact commit in the verification record. Inspect the
Actions run for each later commit before treating its CI as passed. The workflow has read-only repository
permission, no secrets, no deploy/publish steps and bounded execution time.
It runs synthetic tests, the CLI demo and installed-package checks.
Local verification is documented in [../verification.md](../verification.md).
