# Branch protection baseline

This repo now includes CI + repository metadata to support strict branch protection.

## What is already in this repo

- **CI workflow** at `.github/workflows/ci.yml`
  - runs Python syntax checks
  - optionally runs unit tests from `tests/` if present
- **CODEOWNERS** at `.github/CODEOWNERS`
  - owner is set to `@Johnnyk80` (update if ownership changes)
- **PR template** at `.github/pull_request_template.md`

## One-time GitHub settings to apply

Branch protection rules themselves are configured in GitHub settings (server-side), not in code.
You can apply them quickly with:

```bash
.github/scripts/apply_branch_protection.sh owner/repo main
```


## Why GitHub still shows: "Your main branch isn't protected"

That alert is expected until branch protection is enabled in repository settings.
Workflows and docs in this repo **cannot** enforce protection by themselves; protection is a server-side GitHub setting.

## Fastest fix (GitHub UI)

1. Go to **Settings → Branches**.
2. Under **Branch protection rules**, click **Add rule**.
3. Set **Branch name pattern** to `main`.
4. Enable:
   - **Require a pull request before merging**
   - **Require approvals** (set to at least 1)
   - **Require review from Code Owners**
   - **Dismiss stale pull request approvals when new commits are pushed**
   - **Require status checks to pass before merging**
     - Select: `Lint and sanity checks`, `CodeQL`, `Secret scan` (after workflow appears)
   - **Require conversation resolution before merging**
   - **Require linear history**
   - **Do not allow bypassing the above settings** (apply to admins)
5. Disable:
   - **Allow force pushes**
   - **Allow deletions**
6. Save changes.

## API / script fix (alternative)

You can also apply baseline protection with:

```bash
GITHUB_TOKEN=<admin-token> .github/scripts/apply_branch_protection.sh owner/repo main
```

After saving the rule, refresh the repo page and the alert should disappear.

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


## Additional security settings for a public repository

In **Settings → Security** and **Settings → Code security and analysis**, enable:

- Dependency graph
- Dependabot alerts
- Dependabot security updates
- Secret scanning (and Push protection, if available)
- Private vulnerability reporting (if you want inbound reports through GitHub)

## Workflow hardening tips

- Require both `Lint and sanity checks` and `CodeQL` as required status checks.
- Add `Secret scan` as a required status check once `.github/workflows/secret-scan.yml` is in default branch.
- Keep GitHub Actions restricted to trusted actions/orgs where possible.
