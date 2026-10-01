# Contributing

Keep changes small and focused on shared baselines, local overlays and readable
drift. Please use synthetic configuration in issues and tests.

For a new field or Codex version, link the official documentation and a pinned
release schema/commit, explain the portable/local/blocked classification and
add meaningful refusal and round-trip tests. Do not widen the allowlist merely
because an example happened to work. Do not add auth, provider/MCP execution,
automatic home scanning or automatic imports to this release's boundary.

Before a pull request, run `python -m unittest discover -s tests -v`,
`python tools/demo.py`, and build/install a wheel in an isolated environment.
Update both READMEs when the user contract changes. Keep demo output truthful
and keep host paths, credentials, generated packages and build folders out of Git.

Suggested maintenance: review incoming issues and upstream configuration changes
weekly when a maintainer is available. Version support is explicit; continue
rejecting unreviewed versions. Activate the documented CI template only with
authorized workflow-write access, then verify the run's commit equals HEAD.
There is no background service or unattended maintenance process installed.
