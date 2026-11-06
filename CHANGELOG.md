# Changelog

## Unreleased

- Add a separately pinned Codex 0.166.0 explicit-file compatibility policy,
  preserving 0.159.3 defaults and byte-identical old bundles. No fields or
  runtime dependencies added; unknown versions and inconsistent manifest
  provenance remain refused. This does not predict effective runtime settings.

- Reject rendered configs larger than 256 KiB before creating output files,
  respecting the read limit used by `inspect` and `compare`. The input limit,
  supported policy and tool version are unchanged.
- Add synthetic Windows/Unicode round-trip and exact-byte-limit regression tests.

## 0.1.0 — 2026-10-01

- Offline inspect, export, render and compare commands for a versioned subset of Codex CLI 0.159.3.
- Portable-field export, machine overlays, deterministic hash manifests and drift origins.
- Explicit-file boundaries, unknown/blocked-field refusal and conservative sensitive-material screening.
- Synthetic examples, standard-library tests, bilingual documentation and a reproducible terminal demo.
- Read-only GitHub Actions workflow for Linux/Windows tests, demo and installed-package checks.

### Unreleased: 0.167.0 explicit-file policy

- Add a separately pinned 0.167.0 policy for the existing 14-field subset.
- Preserve defaults, prior policy tuples, strict enum/path restrictions and old bytes.
- Document managed-network limitations; no runtime compatibility claim.
