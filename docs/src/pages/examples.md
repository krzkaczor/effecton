---
title: Examples
description: Complete programs built on effecton that live in the repository.
---

# Examples

The repository ships complete programs built on effecton. Each one is a workspace package with its own tests, so it doubles as a reference for structuring a real project: one module per service, errors colocated with the code that raises them, and `run_main` at the entry point.

## skills-cli

[`packages/examples/skills-cli`](https://github.com/krzkaczor/effecton/tree/main/packages/examples/skills-cli) is a small CLI that installs an [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) from a GitHub URL. It is the canonical example: all I/O goes through a service, so the whole program runs against test implementations without touching the network or the disk.

## changesets

[`packages/changesets`](https://github.com/krzkaczor/effecton/tree/main/packages/changesets) is the repository's own release tooling: a Python take on [changesets](https://github.com/changesets/changesets) that records pending changes, bumps versions and writes changelogs. It is never published, but it is the largest effecton program in the repo and the exemplar for error design.

## Where to look for smaller snippets

Most pages in the Core and Standard library sections end with a link to the test module that pins the behavior they describe, for example [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py) for the runners and [`test_http_client.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_http_client.py) for the HTTP client. Those tests are the most complete catalogue of idiomatic usage.
