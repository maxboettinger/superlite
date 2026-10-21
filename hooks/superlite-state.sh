# Sourced by the hooks (not a hook itself): which .superlite folder this session uses. The same order as
# skills/subagent-driven-development/scripts/state.py, so hooks and sl always agree:
#   1. $SUPERLITE_STATE_DIR;
#   2. the session's binding: ${SUPERLITE_HOME:-$HOME/.superlite}/sessions/<session_id from the hook input>, whose
#      first line is the bound .superlite path (written by `sl orchestrator set|approve|bind` and `lint --stable`);
#      used while that folder exists;
#   3. legacy: <CLAUDE_PROJECT_DIR, else the input's cwd, else $PWD>/.superlite, unless its `session` file names
#      another session: another session's run never gates this one.
# superlite_state: reads $input (the raw hook JSON); sets SL_SD (the .superlite folder) and SL_PROJ (its parent).
# Bash builtins only (no process is spawned).

superlite_state() {
  local re sid="" line f
  SL_SD=""; SL_PROJ=""
  if [ -n "${SUPERLITE_STATE_DIR:-}" ]; then
    SL_SD="${SUPERLITE_STATE_DIR//\\//}"
  else
    re='"session_id"[[:space:]]*:[[:space:]]*"([A-Za-z0-9_-]{1,128})"'
    [[ $input =~ $re ]] && sid="${BASH_REMATCH[1]}"
    if [ -n "$sid" ]; then
      f="${SUPERLITE_HOME:-$HOME/.superlite}/sessions/$sid"
      if [ -f "$f" ]; then
        line=""; IFS= read -r line < "$f"; line="${line%$'\r'}"
        [ -n "$line" ] && [ -d "$line" ] && SL_SD="$line"
      fi
    fi
    if [ -z "$SL_SD" ]; then
      SL_PROJ="${CLAUDE_PROJECT_DIR:-}"
      if [ -z "$SL_PROJ" ]; then
        re='"cwd"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
        [[ $input =~ $re ]] && SL_PROJ="${BASH_REMATCH[1]//\\\\//}"
      fi
      [ -n "$SL_PROJ" ] || SL_PROJ="$PWD"
      SL_SD="$SL_PROJ/.superlite"
      if [ -n "$sid" ] && [ -f "$SL_SD/session" ]; then
        line=""; IFS= read -r line < "$SL_SD/session"; line="${line%$'\r'}"
        if [ -n "$line" ] && [ "$line" != "$sid" ]; then SL_SD=""; SL_PROJ=""; return 1; fi
      fi
      return 0
    fi
  fi
  while [[ $SL_SD == */ && $SL_SD != / ]]; do SL_SD="${SL_SD%/}"; done
  SL_PROJ="${SL_SD%/*}"
  [ -n "$SL_PROJ" ] || SL_PROJ=/
  return 0
}
