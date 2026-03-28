#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="$ROOT_DIR/src/py/DBCode/code_config.yaml"

if [[ -f "$CFG" ]]; then
  perl -i.bak -pe 'if(/^(\s*api_key:\s*)(.*)\s*$/){ my $v=$2; $v=~s/\s+$//; if($v ne "" && $v ne "None" && $v ne "__API_KEY__" && $v ne "your_anthropic_api_key"){ $_="$1__API_KEY__\n"; } }' "$CFG"
  rm -f "$CFG.bak" 2>/dev/null || true
  echo "[sanitize-config] Scrubbed API key in $CFG"
else
  echo "[sanitize-config] Config not found at $CFG (skipped)"
fi
