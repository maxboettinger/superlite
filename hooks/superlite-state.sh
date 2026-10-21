# Sourced by the hooks (not a hook itself): which .superlite folder this session uses. The same order as
# skills/subagent-driven-development/scripts/state.py, so hooks and sl always agree:
#   1. $SUPERLITE_STATE_DIR;
#   2. the session's binding: ${SUPERLITE_HOME:-$HOME/.superlite}/sessions/<session_id from the hook input>, whose
#      first line is the bound .superlite path (written by `sl orchestrator set|approve|bind` and `lint --stable`);
#      used while that folder exists and its `session` file names no other session;
#   3. legacy: <CLAUDE_PROJECT_DIR, else the input's cwd, else $PWD>/.superlite, unless its `session` file names
#      another live session (one whose binding points at that folder): another session's run never gates this one.
# superlite_state: reads $input (the raw hook JSON); sets SL_SD (the .superlite folder) and SL_PROJ (the project its
# paths are judged against: the folder's parent, or the launch directory for a session's private folder under
# sessions/); returns 1 when the launch folder belongs to another session. Bash builtins only (no process is spawned).

# _sl_line FILE: first line of FILE, CR dropped, into SL_LINE (empty when unreadable).
_sl_line() {
  SL_LINE=""
  [ -f "$1" ] || return 0
  IFS= read -r SL_LINE < "$1" || true
  SL_LINE="${SL_LINE%$'\r'}"
}

# _sl_trim VAR: forward slashes, no trailing slash.
_sl_trim() {
  local v="${!1}"
  v="${v//\\//}"
  while [[ $v == */ && $v != / ]]; do v="${v%/}"; done
  printf -v "$1" '%s' "$v"
}

# _sl_launch: the launch directory into SL_LAUNCH.
_sl_launch() {
  local re
  SL_LAUNCH="${CLAUDE_PROJECT_DIR:-}"
  if [ -z "$SL_LAUNCH" ]; then
    re='"cwd"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
    [[ $input =~ $re ]] && SL_LAUNCH="${BASH_REMATCH[1]//\\\\//}"
  fi
  [ -n "$SL_LAUNCH" ] || SL_LAUNCH="$PWD"
  _sl_trim SL_LAUNCH
}

superlite_state() {
  local re sid="" o a b sessions="${SUPERLITE_HOME:-$HOME/.superlite}/sessions"
  SL_SD=""; SL_PROJ=""
  _sl_trim sessions
  if [ -n "${SUPERLITE_STATE_DIR:-}" ]; then
    SL_SD="$SUPERLITE_STATE_DIR"
    _sl_trim SL_SD
    case "$SL_SD" in /*|[A-Za-z]:/*) ;; *) SL_SD="$PWD/$SL_SD" ;; esac
  else
    re='"session_id"[[:space:]]*:[[:space:]]*"([A-Za-z0-9_-]{1,128})"'
    [[ $input =~ $re ]] && sid="${BASH_REMATCH[1]}"
    if [ -n "$sid" ]; then
      _sl_line "$sessions/$sid"
      if [ -n "$SL_LINE" ] && [ -d "$SL_LINE" ]; then
        SL_SD="$SL_LINE"
        _sl_line "$SL_SD/session"
        [ -z "$SL_LINE" ] || [ "$SL_LINE" = "$sid" ] || SL_SD=""   # taken over by another session
      fi
    fi
    if [ -z "$SL_SD" ]; then
      _sl_launch
      SL_PROJ="$SL_LAUNCH"
      SL_SD="$SL_PROJ/.superlite"
      _sl_line "$SL_SD/session"; o="$SL_LINE"
      if [ -n "$sid" ] && [ -n "$o" ] && [ "$o" != "$sid" ] && [[ $o =~ ^[A-Za-z0-9_-]{1,128}$ ]]; then
        _sl_line "$sessions/$o"; a="$SL_LINE"; _sl_trim a; b="$SL_SD"
        if [ "${a,,}" = "${b,,}" ]; then SL_SD=""; SL_PROJ=""; return 1; fi   # another live session's folder
      fi
      return 0
    fi
  fi
  _sl_trim SL_SD
  case "$SL_SD" in
    "$sessions"/*) _sl_launch; SL_PROJ="$SL_LAUNCH" ;;   # a private folder: judge paths against the launch directory
    *) SL_PROJ="${SL_SD%/*}"; [ -n "$SL_PROJ" ] || SL_PROJ=/ ;;
  esac
  return 0
}
