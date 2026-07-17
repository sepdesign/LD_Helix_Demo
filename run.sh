#!/usr/bin/env bash
#
# run.sh - start the Helix Health Group LaunchDarkly demo (all five services).
#
# Safe to run any time. It checks each service's port and starts ONLY the ones that
# aren't already running, so if some services are already up it just fills in the
# gaps - it never stops or restarts a running service (use ./stop.sh for that).
#
# What it does, in order:
#   1. Runs the prerequisite check (scripts/check_prerequisites.py) for visibility.
#      It WARNS but never aborts, so a missing build tool - or a service that is
#      already running - never stops the other services from starting.
#   2. Starts each service only if its port is free, in the background, with output
#      written to logs/<name>.log.
#   3. Waits for the ports to come up and prints a status table.
#
# Usage:  ./run.sh   (or: bash run.sh)   - run from anywhere; it cd's to the repo.
# Stop:   ./stop.sh
#
# Works in git-bash on Windows and in bash on macOS/Linux.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

# Prefer 'python', fall back to 'python3'.
PY="$(command -v python || command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "ERROR: python / python3 not found on PATH." >&2
  exit 1
fi

# Echo the PID(s) listening on TCP port $1 (empty if nothing is). OS-aware:
# lsof on macOS/Linux, netstat on Windows/git-bash.
port_pid() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:${port}" -s tcp:LISTEN 2>/dev/null | sort -u
  else
    netstat -ano 2>/dev/null | tr -d '\r' \
      | awk -v p=":${port}" '$0 ~ /LISTENING/ && $2 ~ p"$" {print $NF}' | sort -u
  fi
}
is_up() { [ -n "$(port_pid "$1")" ]; }

# Block until port $1 is listening, up to $2 seconds. Non-zero on timeout.
wait_up() {
  local port="$1" timeout="$2" i=0
  while [ "$i" -lt "$timeout" ]; do
    is_up "$port" && return 0
    sleep 1; i=$((i + 1))
  done
  return 1
}

# start_svc <name> <port> <subdir> <command...>
# Starts the command in <subdir> in the background, but only if <port> is free.
start_svc() {
  local name="$1" port="$2" dir="$3"; shift 3
  if is_up "$port"; then
    echo ">> $name already running on :$port - leaving it alone"
    return 0
  fi
  echo ">> starting $name on :$port  (log: logs/$name.log)"
  # Subshell + '&' detaches the process so it keeps running after this script exits.
  ( cd "$ROOT/$dir" && "$@" >"$LOGDIR/$name.log" 2>&1 & )
}

echo "============================================================"
echo " Helix LaunchDarkly demo - run.sh"
echo "============================================================"

# 1. Prerequisites - informational only. We WARN but never abort, so a build tool
#    that isn't on this shell's PATH (or a service that is already running) never
#    stops the other services from starting. Anything truly broken shows DOWN below.
echo ">> checking prerequisites ..."
if ! "$PY" "$ROOT/scripts/check_prerequisites.py"; then
  echo
  echo ">> heads-up: some prerequisite checks reported [FAIL] above. Continuing anyway -"
  echo ">> already-running services are skipped, and any service that still can't start"
  echo ">> will show DOWN below, with the reason in its logs/<name>.log."
fi

# 2 + 3. Start whatever is not already up.
echo
start_svc python   8000 python-service "$PY" main.py
start_svc go       8001 go-service     go run main.go
start_svc java     8002 java-service   mvn spring-boot:run
start_svc frontend 3000 frontend       "$PY" -m http.server 3000
start_svc presentation 3001 presentation "$PY" -m http.server 3001

# 4. Wait for ports and report. Go and Java COMPILE on start (go run / mvn spring-boot:run),
#    so they get generous timeouts - a slow first compile is not a failure.
echo
echo ">> waiting for services to come up (Go and Java compile on start, so allow time) ..."
wait_up 8000 40;  py_ok=$?
wait_up 8001 75;  go_ok=$?
wait_up 8002 120; jv_ok=$?
wait_up 3000 15;  fe_ok=$?
wait_up 3001 15;  pr_ok=$?

status() { if [ "$1" -eq 0 ]; then echo "UP"; else echo "DOWN  (see logs/$2.log)"; fi; }
echo
echo "------------------------------------------------------------"
echo "  Python   (8000)  $(status "$py_ok" python)"
echo "  Go       (8001)  $(status "$go_ok" go)"
echo "  Java     (8002)  $(status "$jv_ok" java)"
echo "  Frontend (3000)  $(status "$fe_ok" frontend)"
echo "  Slides   (3001)  $(status "$pr_ok" presentation)"
echo "------------------------------------------------------------"
echo "  Demo:   http://localhost:3000"
echo "  Slides: http://localhost:3001"
echo "  Stop:   ./stop.sh"
echo

# Exit non-zero if anything failed to start (handy for scripting / CI).
[ "$py_ok" -eq 0 ] && [ "$go_ok" -eq 0 ] && [ "$jv_ok" -eq 0 ] && [ "$fe_ok" -eq 0 ] && [ "$pr_ok" -eq 0 ]
