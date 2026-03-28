#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

mkdir -p "$DIST_DIR"

# Scrub secrets before packaging
"$ROOT_DIR/scripts/sanitize-config.sh"

# Build TypeScript
if command -v npm >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && npm run compile)
fi

# Create zip as a generic package (vsce optional)
PKG_NAME="dbcooker-$(date +%Y%m%d_%H%M%S).zip"
(cd "$ROOT_DIR" && zip -r "$DIST_DIR/$PKG_NAME" . -x "node_modules/*" "venv/*" "workspace/*" "dist/*" ".git/*" "*.vsix")

echo "[package] Created $DIST_DIR/$PKG_NAME"

