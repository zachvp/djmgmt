#!/usr/bin/env bash
# Restarts the djmgmt Streamlit UI launch agent so the running server picks up the working tree.
#
# The agent runs an editable install, so a restart is what publishes source changes. New modules in
# particular need a fresh process, since the running server imports them once at startup.
#
# Usage:
#   ./deploy.sh                 run the test suite, then restart and verify the server
#   ./deploy.sh --skip-tests    restart and verify, leaving the test suite for the caller
#   ./deploy.sh --status        report the current agent state and exit

set -euo pipefail

LABEL='zachvp.djmgmt.wake'
TARGET="gui/$(id -u)/${LABEL}"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
PORT="${DJMGMT_UI_PORT:-8501}"
LOG_OUT='/tmp/streamlit.log'
LOG_ERR='/tmp/streamlit.err'
STARTUP_TIMEOUT=30

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test against the interpreter the agent runs, so the gate reflects the deployed environment.
AGENT_PYTHON='/Users/zachvp/.pyenv/versions/dev@3.13/bin/python'
PYTHON="${DJMGMT_PYTHON:-${AGENT_PYTHON}}"
[ -x "${PYTHON}" ] || PYTHON='python3'

run_tests=1
status_only=0
for arg in "$@"; do
    case "${arg}" in
        --skip-tests) run_tests=0 ;;
        --status)     status_only=1 ;;
        *)
            echo "usage: $(basename "$0") [--skip-tests] [--status]" >&2
            exit 2
            ;;
    esac
done

say() { printf '\033[1m==>\033[0m %s\n' "$1"; }

# Reports the agent PID, or an empty string when the agent is loaded without a running process.
agent_pid() {
    launchctl list "${LABEL}" 2>/dev/null | awk '/"PID"/ {gsub(/[^0-9]/, "", $3); print $3}'
}

report_status() {
    local pid
    pid="$(agent_pid)"
    if [ -n "${pid}" ]; then
        say "agent '${LABEL}' running as PID ${pid}"
        ps -o pid,lstart,etime,command -p "${pid}" | tail -n +1
    else
        say "agent '${LABEL}' is loaded without a running process"
    fi
}

# Waits for the UI to accept connections, so a failed startup surfaces here rather than in the browser.
wait_for_port() {
    local waited=0
    while [ "${waited}" -lt "${STARTUP_TIMEOUT}" ]; do
        if nc -z localhost "${PORT}" 2>/dev/null; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

if [ "${status_only}" -eq 1 ]; then
    report_status
    exit 0
fi

if [ "${run_tests}" -eq 1 ]; then
    say "running test suite via ${PYTHON}"
    set +e
    "${PYTHON}" -m pytest "${ROOT}/tests" -q 2>&1 | tail -5
    tests_status="${PIPESTATUS[0]}"
    set -e
    if [ "${tests_status}" -ne 0 ]; then
        echo 'tests failed; deploy with --skip-tests to restart anyway' >&2
        exit 1
    fi
fi

# Load the agent when launchd has no record of it, so a fresh machine reaches the same end state.
if ! launchctl list "${LABEL}" >/dev/null 2>&1; then
    say "bootstrapping agent from ${PLIST}"
    launchctl bootstrap "gui/$(id -u)" "${PLIST}"
fi

say "restarting ${LABEL}"
launchctl kickstart -kp "${TARGET}"

say "waiting for the UI on port ${PORT}"
if wait_for_port; then
    say "UI ready at http://localhost:${PORT}"
    report_status
else
    echo "UI did not accept connections within ${STARTUP_TIMEOUT}s; recent errors:" >&2
    tail -20 "${LOG_ERR}" >&2
    exit 1
fi

say "logs: ${LOG_OUT} (stdout), ${LOG_ERR} (stderr)"
