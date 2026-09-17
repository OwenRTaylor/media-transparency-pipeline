#!/usr/bin/env bash
# Set up tmux dev layout: 5 Claude Code windows + 4 terminals.
# Project-agnostic: session name + working dir derive from the git repo root,
# so the same script works in any project. Run from inside a tmux session.
set -uo pipefail

DIR="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Not in a git repo."; exit 1; }
SESSION="$(basename "$DIR" | tr '[:upper:] ' '[:lower:]-')"

if [ -z "${TMUX:-}" ]; then
  echo "Not inside tmux. Attach first: tmux new -A -s $SESSION -c \"$DIR\""
  exit 1
fi

# Rename current window as first Claude instance.
# NOTE: normally launched by the /tmux-dev skill, already running inside a Claude
# session in this window. claude-1 already has Claude — do NOT send `claude` here.
tmux rename-window "claude-1"

# Remaining claude + terminal windows.
for i in 2 3 4 5; do tmux new-window -n "claude-$i" -c "$DIR"; done
for i in 1 2 3 4; do tmux new-window -n "term-$i" -c "$DIR"; done

# Wait until a window's shell has drawn its prompt before typing into it.
# A fixed sleep is unreliable: bash + tmux plugins on WSL take variable time to
# init, and send-keys that races startup gets dropped (symptom: `claude` sitting
# un-executed at the prompt).
wait_for_prompt() {
  local win="$1" i
  for i in $(seq 1 50); do  # up to ~10s
    if tmux capture-pane -t "$win" -p 2>/dev/null | grep -qE '[$#] *$'; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

# Start Claude in windows 2-5, each only once its shell is ready.
for i in 2 3 4 5; do
  win="claude-$i"
  wait_for_prompt "$win" || echo "warn: claude-$i shell not ready, sending anyway"
  tmux send-keys -t "$win" "claude" Enter
done

tmux select-window -t "claude-1"
echo "Ready: 5 claude + 4 terminal windows ($SESSION)"
