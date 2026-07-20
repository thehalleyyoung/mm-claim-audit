#!/usr/bin/env bash
# install.sh — public one-shot dual-install for mm-claim-audit.
#
# Installs into BOTH:
#   ~/.claude/skills/mm-claim-audit/
#   ~/.cursor/skills/mm-claim-audit/
#
# Usage (from repo root):
#   bash install.sh
#   bash install.sh mm-claim-audit

set -euo pipefail

NAME="mm-claim-audit"
SKILL_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    -h|--help)
      echo "usage: bash install.sh [--name NAME] [skill-dir]"
      exit 0
      ;;
    *)
      SKILL_DIR="$1"; shift
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -z "$SKILL_DIR" ]; then
  SKILL_DIR="$ROOT/mm-claim-audit"
fi
SKILL_DIR="$(cd "$SKILL_DIR" && pwd)"
[ -f "$SKILL_DIR/SKILL.md" ] || { echo "error: $SKILL_DIR/SKILL.md missing" >&2; exit 1; }

NAME="$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9-]+/-/g; s/^-+//; s/-+$//')"
CLAUDE_DEST="${HOME}/.claude/skills/${NAME}"
CURSOR_DEST="${HOME}/.cursor/skills/${NAME}"

copy_one() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  mkdir -p "$dest"
  tar -C "$SKILL_DIR" -cf - . | tar -C "$dest" -xf -
  echo "installed: $dest"
}

copy_one "$CLAUDE_DEST"
copy_one "$CURSOR_DEST"
[ -f "$CLAUDE_DEST/SKILL.md" ] && [ -f "$CURSOR_DEST/SKILL.md" ]
echo "ok: dual-installed '$NAME' to Claude + Cursor"
