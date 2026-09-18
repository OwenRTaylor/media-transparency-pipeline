#!/usr/bin/env bash
# Claude Code PreToolUse guard. Wired in .claude/settings.json on the Bash tool.
# Reads the tool-call JSON on stdin; if the command is a `git commit`, runs the
# shared personal-data check. Exit 2 blocks the tool call and feeds stderr back.
input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c 'import sys,json;
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)"

case "$cmd" in
  *"git commit"*)
    root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
    if ! out="$("$root/scripts/check-no-personal.sh" 2>&1)"; then
      printf '%s\n' "$out" >&2
      echo "Blocked by check-no-personal (Claude PreToolUse guard). Redact or unstage, then retry." >&2
      exit 2
    fi
    ;;
esac
exit 0
