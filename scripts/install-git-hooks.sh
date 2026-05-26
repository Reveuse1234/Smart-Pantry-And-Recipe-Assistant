#!/usr/bin/env bash
# Install local git hooks that strip unwanted automated co-author trailers before each commit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$ROOT/.git/hooks/prepare-commit-msg"
cat > "$HOOK" << 'EOF'
#!/bin/bash
# Remove automated co-author trailers from commit messages.
MSG_FILE="$1"
if [[ -f "$MSG_FILE" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    sed -i '' '/cursoragent@cursor\.com/d' "$MSG_FILE"
    sed -i '' '/^Co-authored-by: Cursor /d' "$MSG_FILE"
    sed -i '' '/^Made-with: Cursor/d' "$MSG_FILE"
  else
    sed -i '/cursoragent@cursor\.com/d' "$MSG_FILE"
    sed -i '/^Co-authored-by: Cursor /d' "$MSG_FILE"
    sed -i '/^Made-with: Cursor/d' "$MSG_FILE"
  fi
fi
EOF
chmod +x "$HOOK"
echo "Installed: $HOOK"
