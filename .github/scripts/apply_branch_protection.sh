#!/usr/bin/env bash
set -euo pipefail

# Applies branch protection to the main branch using GitHub's REST API via gh.
# Prerequisites:
#   - gh CLI authenticated with a token that has repo admin rights
#   - run from inside the target repository clone

REPO="${1:-}"
BRANCH="${2:-main}"

if [[ -z "$REPO" ]]; then
  if REPO_GUESS=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null); then
    REPO="$REPO_GUESS"
  else
    echo "Usage: $0 <owner/repo> [branch]"
    exit 1
  fi
fi

echo "Applying branch protection to ${REPO}:${BRANCH}"

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${REPO}/branches/${BRANCH}/protection" \
  -f required_status_checks.strict=true \
  -f required_status_checks.contexts[]='Lint and sanity checks' \
  -f enforce_admins=true \
  -f required_pull_request_reviews.dismiss_stale_reviews=true \
  -f required_pull_request_reviews.require_code_owner_reviews=true \
  -f required_pull_request_reviews.required_approving_review_count=1 \
  -f restrictions= \
  -f required_linear_history=true \
  -f allow_force_pushes=false \
  -f allow_deletions=false

echo "Done."
