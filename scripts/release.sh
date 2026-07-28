#!/bin/bash
# release.sh – Full release helper for RoomFlow
# Usage: ./scripts/release.sh [patch|minor|major|1.2.3]

set -e

BUMP=${1:-patch}

echo "================================================"
echo "  RoomFlow – Release Helper"
echo "================================================"
echo ""

# Make sure we're on main
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ] && [ "$BRANCH" != "master" ]; then
    echo "⚠️  You are on branch '$BRANCH', not main/master."
    read -p "   Continue anyway? [y/N] " confirm
    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 1
    fi
fi

# Make sure working tree is clean
if ! git diff-index --quiet HEAD --; then
    echo "❌  You have uncommitted changes."
    echo "    Commit or stash them before releasing."
    exit 1
fi

# Run version bump script
python3 scripts/bump_version.py "$BUMP"
