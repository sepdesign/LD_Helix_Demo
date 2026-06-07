#!/usr/bin/env bash
#
# run.sh - start the Helix Health Group LaunchDarkly demo (all four services).
#
# What it does, in order:
#   1. Runs the prerequisite check (scripts/check_prerequisites.py) and stops
#      if anything required is missing (toolchain, .env keys, ...).
#   2. For each service, checks whether its port is already listening.
#   3. Starts only the services that are NOT already up, in the background,
#      with each service's output written to logs/<name>.log.
#   4. Waits for the ports to come up and prints a status table.
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

# 1. Prerequisites (aborts on any required failure; warnings are allowed).
echo ">> checking prerequisites ..."
if ! "$PY" "$ROOT/scripts/check_prerequisites.py"; then
  echo
  echo ">> prerequisite check FAILED - fix the [FAIL] items above, then re-run." >&2
  exit 1
fi

# 2 + 3. Start whatever is not already up.
echo
start_svc python   8000 python-service "$PY" main.py
start_svc go       8001 go-service     go run main.go
start_svc java     8002 java-service   mvn spring-boot:run
start_svc frontend 3000 frontend       "$PY" -m http.server 3000

# 4. Wait for ports and report. Java/Maven is slowest, so give it the most time.
echo
echo ">> waiting for services to come up (Java/Maven can take a while) ..."
wait_up 8000 40;  py_ok=$?
wait_up 8001 40;  go_ok=$?
wait_up 8002 120; jv_ok=$?
wait_up 3000 15;  fe_ok=$?

status() { if [ "$1" -eq 0 ]; then echo "UP"; else echo "DOWN  (see logs/$2.log)"; fi; }
echo
echo "------------------------------------------------------------"
echo "  Python   (8000)  $(status "$py_ok" python)"
echo "  Go       (8001)  $(status "$go_ok" go)"
echo "  Java     (8002)  $(status "$jv_ok" java)"
echo "  Frontend (3000)  $(status "$fe_ok" frontend)"
echo "------------------------------------------------------------"
echo "  Demo:   http://localhost:3000"
echo "  Stop:   ./stop.sh"
echo

# Exit non-zero if anything failed to start (handy for scripting / CI).
[ "$py_ok" -eq 0 ] && [ "$go_ok" -eq 0 ] && [ "$jv_ok" -eq 0 ] && [ "$fe_ok" -eq 0 ]
