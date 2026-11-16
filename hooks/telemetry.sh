# Sourced library (not a hook): appends one JSON line per event to $SUPERLITE_HOME/events.jsonl, the same
# line shape as skills/subagent-driven-development/scripts/telemetry.py (contract C6). Bash 3.2 builtins only.
#
#   . "${BASH_SOURCE[0]%/*}/telemetry.sh"
#   SL_TEL_SESSION=$sid SL_TEL_CWD=$cwd          # context, optional; else env vars and $PWD
#   sl_tel_gate HOOK DECISION RULE TOOL TARGET   # one `gate` line
#   sl_tel_json VAR VALUE [MAX]                  # VAR = JSON string of VALUE cut to MAX chars (200), or null
#   sl_tel_emit KIND FRAGMENT                    # FRAGMENT: the kind's own fields as JSON members
#   sl_tel_session_file SID EXT                  # prints <home>/telemetry/sessions/SID.EXT; 1 for a bad id
#
# Fail open: every function returns 0 and prints nothing (errors go to /dev/null). A line holds no free text.
# Note: the run id lookup uses [[ =~ ]], so BASH_REMATCH changes; read your own match first.

_SL_TEL_LIB_DIR="${BASH_SOURCE[0]%/*}"
_SL_TEL_VERSION=
_sl_tel_re_ver='"version"[[:space:]]*:[[:space:]]*"([^"]+)"'
{ IFS= read -r -d '' _sl_tel_pkg <"$_SL_TEL_LIB_DIR/../package.json"; } 2>/dev/null
[[ $_sl_tel_pkg =~ $_sl_tel_re_ver ]] && _SL_TEL_VERSION=${BASH_REMATCH[1]}
unset _sl_tel_pkg _sl_tel_re_ver

# sl_tel_json VAR VALUE [MAX]
sl_tel_json() {
  local _v="$2" _max="${3:-200}" _o= _c _i
  _v=${_v:0:$_max}
  _v=${_v//\\/\\\\}
  _v=${_v//\"/\\\"}
  if [[ $_v == *[[:cntrl:]]* ]]; then
    for ((_i = 0; _i < ${#_v}; _i++)); do
      _c=${_v:_i:1}
      [[ $_c == [[:cntrl:]] ]] && _c=' '
      _o=$_o$_c
    done
    _v=$_o
  fi
  if [[ -z $2 ]]; then
    eval "$1=null"
  else
    eval "$1=\"\\\"\"\$_v\"\\\"\""
  fi
  return 0
}

_sl_tel_home() { _SL_TEL_HOME="${SUPERLITE_HOME:-${HOME:-}/.superlite}"; }

# 0 when telemetry is on
_sl_tel_on() {
  [[ ${SUPERLITE_TELEMETRY-} == 0 ]] && return 1
  [[ -n ${PYTEST_CURRENT_TEST-} && -z ${SUPERLITE_HOME-} ]] && return 1
  _sl_tel_home
  [[ -e $_SL_TEL_HOME/telemetry-off ]] && return 1
  return 0
}

# sl_tel_session_file SID EXT
sl_tel_session_file() {
  local re='^[A-Za-z0-9_-]{1,128}$'
  [[ $1 =~ $re ]] || return 1
  _sl_tel_home
  printf '%s\n' "$_SL_TEL_HOME/telemetry/sessions/$1.$2"
  return 0
}

# _sl_tel_now: _SL_TEL_T = UTC time as 2026-11-16T12:34:56.789Z, from the clock and integer arithmetic
_sl_tel_now() {
  local rt="${EPOCHREALTIME-}" s ms=000 f days rem z era doe yoe y doy mp d m
  if [[ -n $rt ]]; then
    s=${rt%%[.,]*}
    f=${rt#*[.,]}000
    [[ $f == "$rt"000 ]] && f=000
    ms=${f:0:3}
  else
    s=$(date +%s)
  fi
  days=$((s / 86400)); rem=$((s % 86400))
  z=$((days + 719468)); era=$((z / 146097)); doe=$((z - era * 146097))
  yoe=$(((doe - doe / 1460 + doe / 36524 - doe / 146096) / 365))
  y=$((yoe + era * 400)); doy=$((doe - (365 * yoe + yoe / 4 - yoe / 100)))
  mp=$(((5 * doy + 2) / 153)); d=$((doy - (153 * mp + 2) / 5 + 1))
  if ((mp < 10)); then m=$((mp + 3)); else m=$((mp - 9)); fi
  ((m <= 2)) && y=$((y + 1))
  printf -v _SL_TEL_T '%04d-%02d-%02dT%02d:%02d:%02d.%sZ' "$y" "$m" "$d" $((rem / 3600)) $((rem % 3600 / 60)) $((rem % 60)) "$ms"
}

# sl_tel_emit KIND FRAGMENT
sl_tel_emit() {
  _sl_tel_on || return 0
  local kind="$1" frag="$2" sess cwd d sd run harn ver w r cfg root line
  local re='"run_id"[[:space:]]*:[[:space:]]*"([^"]+)"' j
  sess="${SL_TEL_SESSION:-${CLAUDE_CODE_SESSION_ID:-${SUPERLITE_SESSION_ID:-}}}"
  cwd="${SL_TEL_CWD:-$PWD}"
  sd="${SL_SD:-${SUPERLITE_STATE_DIR:-}}"
  run=
  if [[ -n $sd ]]; then
    { IFS= read -r -d '' j <"$sd/stable.json"; } 2>/dev/null
    [[ $j =~ $re ]] && run=${BASH_REMATCH[1]}
  fi
  root=
  d=$cwd
  while [[ -n $d ]]; do
    if [[ -e $d/.git ]]; then root=$d; break; fi
    [[ $d == */* ]] || break
    d=${d%/*}
    [[ -z $d && -e /.git ]] && root=/
  done
  if [[ -n ${SUPERLITE_HARNESS-} ]]; then harn=$SUPERLITE_HARNESS
  elif [[ -n ${CLAUDECODE-} ]]; then harn=claude-code
  elif [[ -n ${CODEX_THREAD_ID-}${CODEX_SANDBOX-} ]]; then harn=codex
  elif [[ -n ${GEMINI_CLI-} ]]; then harn=gemini
  else harn=; fi
  ver=$_SL_TEL_VERSION
  _sl_tel_now
  sl_tel_json sess "$sess"; sl_tel_json run "$run"; sl_tel_json root "$root" 1000
  sl_tel_json harn "$harn"; sl_tel_json ver "$ver"
  sl_tel_json w "${SUPERLITE_FLEET_WORKER-}"; sl_tel_json r "${SUPERLITE_FLEET_ROLE-}"
  sl_tel_json cfg "${CLAUDE_CONFIG_DIR-}" 500
  line="{\"v\":1,\"t\":\"$_SL_TEL_T\",\"kind\":\"$kind\",\"session\":$sess,\"run\":$run,\"repo_root\":$root,\"harness\":$harn,\"version\":$ver,\"worker\":$w,\"role\":$r,\"config_dir\":$cfg"
  [[ -n $frag ]] && line="$line,$frag"
  line="$line}"
  ((${#line} > 4095)) && return 0
  _sl_tel_home
  [[ -d $_SL_TEL_HOME ]] || mkdir -p "$_SL_TEL_HOME" 2>/dev/null
  { printf '%s\n' "$line" >>"$_SL_TEL_HOME/events.jsonl"; } 2>/dev/null
  return 0
}

# sl_tel_gate HOOK DECISION RULE TOOL TARGET
sl_tel_gate() {
  _sl_tel_on || return 0
  local h d r t g
  sl_tel_json h "$1"; sl_tel_json d "$2"; sl_tel_json r "$3"; sl_tel_json t "$4"; sl_tel_json g "$5"
  sl_tel_emit gate "\"hook\":$h,\"decision\":$d,\"rule\":$r,\"tool\":$t,\"target\":$g"
  return 0
}
