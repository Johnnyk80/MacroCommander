# Branch protection baseline

This repo now includes CI + repository metadata to support strict branch protection.

## What is already in this repo

- **CI workflow** at `.github/workflows/ci.yml`
  - runs Python syntax checks
  - optionally runs unit tests from `tests/` if present
- **CODEOWNERS** at `.github/CODEOWNERS`
  - set the placeholder owner to your real GitHub username/team
- **PR template** at `.github/pull_request_template.md`

## One-time GitHub settings to apply

Branch protection rules themselves are configured in GitHub settings (server-side), not in code.
You can apply them quickly with:

```bash
.github/scripts/apply_branch_protection.sh owner/repo main
```

## Recommended policy

- Require pull request before merge
- Require 1+ approval
- Require code owner review
- Dismiss stale reviews on new commits
- Require status check: `Lint and sanity checks`
- Require linear history
- Disable force pushes
- Disable branch deletion
- Apply rules to admins as well
