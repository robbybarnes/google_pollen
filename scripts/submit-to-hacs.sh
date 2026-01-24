#!/bin/bash
# Submit Google Pollen to HACS Default Repository
# Run this script AFTER the brands PR has been merged and HACS validation passes
#
# Prerequisites:
# 1. Brands PR merged: https://github.com/home-assistant/brands/pull/9261
# 2. HACS validation passing (re-run workflow after brands merge)
# 3. New release created after validation passes

set -e

echo "=== HACS Default Submission Script ==="
echo ""

# Check if brands PR is merged
echo "Step 1: Checking brands PR status..."
BRANDS_STATE=$(gh pr view 9261 --repo home-assistant/brands --json state -q .state 2>/dev/null || echo "UNKNOWN")
if [ "$BRANDS_STATE" != "MERGED" ]; then
    echo "ERROR: Brands PR is not yet merged (state: $BRANDS_STATE)"
    echo "Please wait for https://github.com/home-assistant/brands/pull/9261 to be merged"
    exit 1
fi
echo "Brands PR is merged!"

# Check HACS validation status
echo ""
echo "Step 2: Checking HACS validation status..."
HACS_STATUS=$(gh run list --repo robbybarnes/google_pollen --workflow "HACS Validation" --limit 1 --json conclusion -q '.[0].conclusion')
if [ "$HACS_STATUS" != "success" ]; then
    echo "ERROR: HACS validation is not passing (status: $HACS_STATUS)"
    echo "Please re-run the HACS validation workflow:"
    echo "  gh workflow run hacs.yaml --repo robbybarnes/google_pollen"
    exit 1
fi
HACS_URL=$(gh run list --repo robbybarnes/google_pollen --workflow "HACS Validation" --limit 1 --json url -q '.[0].url')
echo "HACS validation passing!"

# Get hassfest URL
HASSFEST_URL=$(gh run list --repo robbybarnes/google_pollen --workflow "Hassfest Validation" --limit 1 --json url -q '.[0].url')

# Get latest release
RELEASE_URL=$(gh release view --repo robbybarnes/google_pollen --json url -q .url)

echo ""
echo "Step 3: Creating HACS default PR..."

# Create the PR
PR_BODY=$(cat <<EOF
## Checklist

- [x] I've read the [publishing documentation](https://hacs.xyz/docs/publish/start).
- [x] I've added the [HACS action](https://hacs.xyz/docs/publish/action) to my repository.
- [x] I've added the [hassfest action](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) to my repository.
- [x] The actions are passing without any disabled checks in my repository.
- [x] I've added a link to the action run on my repository below in the links section.
- [x] I've created a new release of the repository after the validation actions were run successfully.

## Links

Link to current release: <${RELEASE_URL}>
Link to successful HACS action (without the \`ignore\` key): <${HACS_URL}>
Link to successful hassfest action (if integration): <${HASSFEST_URL}>

## About

Google Pollen is a Home Assistant custom integration that provides pollen forecasts using the Google Pollen API. It creates sensors for grass, tree, and weed pollen indices and levels.

Repository: https://github.com/robbybarnes/google_pollen
EOF
)

gh pr create --repo hacs/default \
    --head robbybarnes:add-google-pollen \
    --title "Add robbybarnes/google_pollen" \
    --body "$PR_BODY"

echo ""
echo "=== Done! ==="
echo "Your PR has been created. Check the HACS backlog for status:"
echo "https://github.com/hacs/default/pulls?q=is%3Apr+is%3Aopen+draft%3Afalse+sort%3Acreated-asc"
