# CI scope

The workflow is [../../.github/workflows/ci.yml](../../.github/workflows/ci.yml).
`ci.yml` here retains the reviewed reference copy. Both use pinned official
action commits and test Python 3.11/3.14 on Linux and Windows.

Hosted verification is pending. Inspect the Actions run for the exact published
commit before treating CI as passed. The workflow has read-only repository
permission, no secrets, no deploy/publish steps and bounded execution time.
It runs synthetic tests, the CLI demo and installed-package checks.
Local verification is documented in [../verification.md](../verification.md).
