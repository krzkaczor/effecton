# changesets

Changeset-based changelog and version management for this monorepo — a Python
take on [changesets](https://github.com/changesets/changesets), built on
effecton. Never published; it runs from the workspace.

## CLI

```sh
uv run changeset add --package effecton --bump minor --message "Add E.retry"
uv run changeset status    # pending changesets and the releases they produce
uv run changeset version   # apply changesets: bump versions, update changelogs
uv run changeset notes effecton   # print the latest released changelog section
```

A changeset is a markdown file in `.changeset/` with YAML frontmatter mapping
package names (declared in `.changeset/config.toml`) to bump levels:

```markdown
---
effecton: minor
---

Add `E.retry` combinator.
```

## Release flow

`.github/workflows/release.yml` runs on every push to `main`:

- While changesets are pending, it runs `changeset version` and opens (or
  force-updates) the **Version Packages** PR on `changeset-release/main`.
- Once that PR merges (no changesets left, version untagged), it creates the
  `effecton@<version>` tag plus a GitHub Release with the latest changelog
  section, and publishes effecton to PyPI via trusted publishing.

One-time setup:

- Enable **Settings → Actions → General → Allow GitHub Actions to create and
  approve pull requests**, or the PR step fails with a 403.
- Configure a [PyPI trusted publisher](https://docs.pypi.org/trusted-publishers/)
  for the `effecton` project pointing at this repo's `release.yml`.
- Tag the already-released baseline once so it is never re-released:
  `git tag effecton@0.1.0 && git push origin effecton@0.1.0`.

Known limitation: the Version Packages PR is created with the default
`GITHUB_TOKEN`, so CI does not run on it automatically (GitHub suppresses
workflow triggers from Actions-created events).
