#!/usr/bin/env bash
# check-no-personal.sh — guard against committing personal / local-only data.
#
# Enforces the tracked-vs-local split:
#   - Project Context/_model/   -> tracked, MUST be personal-free
#   - Project Context/_human/    -> local only, never committed
#   - Project Context/external/  -> local only, never committed
#
# Blocks when staged changes (a) touch a local-only path, or
# (b) contain a personal-identifying pattern in a tracked text file.
#
# Usage:
#   check-no-personal.sh            # scan the git staged set (default; used by hooks)
#   check-no-personal.sh --all      # scan every tracked file under Project Context/_model
#
# Exit 0 = clean, 1 = blocked. Extend the patterns below as new leaks appear.
#
# check-no-personal:allow-file  (this script lists the patterns literally; exempt from self-scan)
set -uo pipefail

REPO="$(git rev-parse --show-toplevel)" || exit 1
cd "$REPO" || exit 1

# Paths that must never be committed (regex over repo-relative path).
LOCAL_ONLY_RE='^Project Context/(_human/|external/)'

# Personal-identifying content. Name matched as a phrase so legit media-data
# people named "Taylor"/"Owen" don't trip it; unambiguous tokens matched alone.
PERSONAL_RE='owen[ ._-]?taylor|owensdesktop|desktop-jug2fjo|\bmazort\b|@gmail|gmail\.com|au[- ]?adhd|\badhd\b|autis|neurodiverg|\bdbwork\b|\btailscale\b|\b100\.11[0-9]\.[0-9]{1,3}\.[0-9]{1,3}\b'

mode="${1:-staged}"
fail=0

if [ "$mode" = "--all" ]; then
  files="$(git ls-files 'Project Context/_model')"
  get_content() { cat "$1" 2>/dev/null; }
else
  files="$(git diff --cached --name-only --diff-filter=ACM)"
  get_content() { git show ":$1" 2>/dev/null; }
fi

# Rule A — local-only path staged (would need `git add -f` past .gitignore).
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if printf '%s\n' "$f" | grep -Eq "$LOCAL_ONLY_RE"; then
    echo "BLOCKED (local-only path staged): $f"
    fail=1
  fi
done <<EOF
$files
EOF

# Rule B — personal pattern in a tracked text file.
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    *.md|*.txt|*.py|*.json|*.sh|*.toml|*.yaml|*.yml|*.cfg|*.ini|*.mk|Makefile) ;;
    *) continue ;;
  esac
  body="$(get_content "$f")"
  # Files carrying this marker are exempt (e.g. this script, which lists the
  # patterns literally). Keep the marker rare and intentional.
  case "$body" in *check-no-personal:allow-file*) continue ;; esac
  hits="$(printf '%s\n' "$body" | grep -inE "$PERSONAL_RE")"
  if [ -n "$hits" ]; then
    echo "BLOCKED (personal pattern in $f):"
    printf '%s\n' "$hits" | sed 's/^/    /'
    fail=1
  fi
done <<EOF
$files
EOF

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "Commit blocked by check-no-personal.sh — redact or unstage the above."
  echo "  _human/ and external/ are local-only; _model/ must stay personal-free."
  exit 1
fi

echo "check-no-personal: clean."
exit 0
