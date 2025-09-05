#!/bin/bash

# Script to install git hooks for the project

echo "Installing git hooks..."

# Configure git to use the .githooks directory
git config core.hooksPath .githooks

if [ $? -eq 0 ]; then
    echo "✓ Git hooks installed successfully!"
    echo "  Pre-commit hook will now check for AI-related references"
    echo ""
    echo "To disable hooks temporarily, use: git commit --no-verify"
    echo "To uninstall hooks, run: git config --unset core.hooksPath"
else
    echo "✗ Failed to install git hooks"
    exit 1
fi