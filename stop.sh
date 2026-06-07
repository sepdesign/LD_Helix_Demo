#!/usr/bin/env bash
#
# stop.sh - stop all four Helix demo services (Python 8000, Go 8001,
# Java 8002, Frontend 3000) by finding and killing whatever is listening
# on each port. Safe to run repeatedly; ports already free are skipped.
#
# Usage:  ./stop.sh   (or: bash stop.sh)
#
# Works in git-bash on Windows and in bash on macOS/Linux.
set -uo pipefail

# Echo the PID(s) listening on TCP port $1 (empty if none). OS-aware.
port_pid() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:${port}" -s tcp:LISTEN 2>/dev/null | sort -u
  else
    netstat -ano 2>/dev/null | tr -d '\r' \
      | awk -v p=":${port}" '$0 ~ /LISTENING/ && $2 ~ p"$" {print $NF}' | sort -u
  fi
}

# Kill every PID listening on a port (plus its child tree on Windows, since
# 'go run' spawns a compiled child and 'mvn' spawns a java child).
kill_port() {
  local name="$1" port="$2" pids pid
  pids="$(port_pid "$port")"
  if [ -z "$pids" ]; then
    echo ">> $name (:$port) - not running"
    return 0
  fi
  for pid in $pids; do
    echo ">> stopping $name (:$port), pid $pid"
    if command -v taskkill >/dev/null 2>&1; then
      taskkill //PID "$pid" //T //F >/dev/null 2>&1 || true   # //T tree, //F force
    else
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
}

echo "============================================================"
echo " Helix LaunchDarkly demo - stop.sh"
echo "============================================================"
kill_port frontend 3000
kill_port java     8002
kill_port go       8001
kill_port python   8000
echo ">> done."
