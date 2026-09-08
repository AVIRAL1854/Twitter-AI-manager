#!/usr/bin/env bash
# Fix corrupted 0-byte or truncated .git/index on NTFS mounts
set -e

echo "🔧 Fixing .git/index and optimizing Git configuration for NTFS..."
rm -f .git/index .git/index.lock
git reset

# Enforce NTFS resilience settings
git config --local core.fsync all
git config --local core.fsyncMethod fsync
git config --local core.trustctime false
git config --local core.filemode false
git config --local core.checkStat minimal

echo "✅ Git index restored and NTFS settings applied successfully!"
