#!/usr/bin/env bash
# Source this in cron job payloads for auto inbox polling and idle notification.
# Usage: source agent-wrapper.sh <agent@team>
#
# At start: polls inbox → sets $TEAM_MESSAGES with any new messages (XML format)
# At end: call agent_done to send idle_notification

AGENT_IDENTITY="${1:?Usage: source agent-wrapper.sh agent@team}"
AGENT_NAME="${AGENT_IDENTITY%%@*}"
TEAM_NAME="${AGENT_IDENTITY##*@}"

# Poll inbox at start
TEAM_MESSAGES=$(agent-teams poll "$AGENT_IDENTITY" 2>/dev/null)
export TEAM_MESSAGES

agent_done() {
    local result="${1:-available}"
    agent-teams send "$AGENT_IDENTITY" "${TEAM_NAME}-lead@${TEAM_NAME}" \
        --text "{\"type\":\"idle_notification\",\"from\":\"${AGENT_NAME}\",\"idleReason\":\"${result}\"}" \
        --type idle_notification >/dev/null 2>&1
}

agent_send() {
    local to="$1" text="$2" type="${3:-message}"
    agent-teams send "$AGENT_IDENTITY" "${to}@${TEAM_NAME}" --text "$text" --type "$type"
}
