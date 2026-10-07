#!/usr/bin/env bash
# ==============================================================================
# TradeSignal India - Instant Production Rollback Utility
# Usage:
#   ./scripts/rollback.sh <COMMIT_SHA_OR_TAG>
# Example:
#   ./scripts/rollback.sh 7a8b9c0d
# ==============================================================================

set -e

TARGET_TAG="$1"

if [ -z "$TARGET_TAG" ]; then
  if [ -f ".last_deployment.env" ]; then
    echo "⚠️  No commit SHA specified. Reading from .last_deployment.env..."
    source .last_deployment.env
    TARGET_TAG="$LAST_STABLE_COMMIT"
  fi
fi

if [ -z "$TARGET_TAG" ]; then
  echo "❌ Error: Please provide a commit SHA or tag to rollback to."
  echo "   Usage: ./scripts/rollback.sh <COMMIT_SHA>"
  exit 1
fi

echo "=========================================================="
echo "⏪ Rolling back to version: $TARGET_TAG"
echo "=========================================================="

export COMMIT_TAG="$TARGET_TAG"

# Pull specified version
echo "📦 Pulling backend and frontend images for tag: $TARGET_TAG..."
docker compose -f docker-compose.prod.yml pull backend frontend || true

# Recreate containers with target tag
docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend

echo "=========================================================="
echo "✅ Rollback complete! Live version is now: $TARGET_TAG"
echo "=========================================================="
