# Agent-Teams Test Report

**Date:** 2026-02-11 17:53 PST  
**Tester:** Marcus (subagent: agent-teams-wire)

## Installation
✅ `pip3 install -e .` — successful  
✅ `agent-teams --help` — all 14 subcommands available

## Team Setup
✅ Created `marcus-ops` team with 9 members:
team-lead, builder-agent, research-agent, horror-content, tiktok-horror, control-plane-dev, ambitious-projects, memory-consolidation, session-cleanup

## Test Results

### Basic Messaging
| Test | Result | Notes |
|------|--------|-------|
| Send message (team-lead → builder-agent) | ✅ PASS | Message delivered with UUID, timestamp |
| Poll inbox (builder-agent) | ✅ PASS | Returns `<teammate-message>` XML tags |
| Poll again (cursor-based) | ✅ PASS | Returns empty — cursor advances correctly |
| Broadcast from team-lead | ✅ PASS | 8 messages sent (all except sender) |
| Verify broadcast received | ✅ PASS | builder-agent, research-agent, horror-content all received |

### Task Management
| Test | Result | Notes |
|------|--------|-------|
| Create 3 tasks | ✅ PASS | IDs 1, 2, 3 assigned |
| Claim task 1 (builder-agent) | ✅ PASS | Status → in_progress |
| Claim already-claimed task 1 (research-agent) | ✅ PASS | Error: "Task 1 is in_progress, cannot claim" |
| Complete task 1 | ✅ PASS | Status → completed, result stored |
| Complete unclaimed task 2 | ✅ PASS | Error: "Task 2 is pending, cannot complete" |
| List all tasks | ✅ PASS | Returns 3 tasks |
| List pending tasks | ✅ PASS | Returns tasks 2, 3 |
| List completed tasks | ✅ PASS | Returns task 1 |

### Edge Cases
| Test | Result | Notes |
|------|--------|-------|
| Poll empty inbox | ✅ PASS | Returns empty string |
| Send to non-existent member | ✅ PASS | Creates inbox file (permissive design) |
| Create duplicate team | ✅ PASS | Idempotent after bugfix (see below) |
| Claim already-claimed task | ✅ PASS | Proper error |
| Complete unclaimed task | ✅ PASS | Proper error |
| Long message (10,000 chars) | ✅ PASS | Full text preserved |
| Special characters (`<>&"` emoji backticks) | ✅ PASS | All preserved correctly |

### Integration Format
| Test | Result | Notes |
|------|--------|-------|
| XML `<teammate-message>` tags | ✅ PASS | Correct attributes: from, team, type, timestamp |
| `--json` output | ✅ PASS | Valid JSON on all commands |
| JSON poll format (`--format json`) | ✅ PASS | Returns JSON array |

### Wrapper Script
| Test | Result | Notes |
|------|--------|-------|
| Source agent-wrapper.sh | ✅ PASS | Sets AGENT_IDENTITY, TEAM_MESSAGES |
| agent_send function | ✅ PASS | Message delivered to team-lead |
| agent_done function | ✅ PASS | idle_notification sent |

## Bugs Found & Fixed

### Bug 1: `create_team` overwrites existing config
**Severity:** High  
**Description:** Calling `agent-teams create <team>` on an existing team wiped all members (reset config to empty).  
**Fix:** Added existence check in `core.py:create_team()` — if config exists, merge new members instead of overwriting.  
**Status:** ✅ Fixed and verified

## Cron Integration

Updated **8 enabled cron jobs** in `/Users/ape/.openclaw/cron/jobs.json`:

| Job Name | Member Identity | Status |
|----------|----------------|--------|
| session-cleanup | session-cleanup@marcus-ops | ✅ Updated |
| builder-agent | builder-agent@marcus-ops | ✅ Updated |
| research-agent | research-agent@marcus-ops | ✅ Updated |
| memory-consolidation | memory-consolidation@marcus-ops | ✅ Updated |
| control-plane-dev | control-plane-dev@marcus-ops | ✅ Updated |
| ambitious-projects | ambitious-projects@marcus-ops | ✅ Updated |
| horror-content | horror-content@marcus-ops | ✅ Updated |
| tiktok-horror-post | tiktok-horror@marcus-ops | ✅ Updated |

Each job now:
1. **Starts** by polling `agent-teams poll {member}@marcus-ops`
2. **Ends** by sending summary + idle_notification to team-lead

Backup saved to `jobs.json.bak`.

## Summary

**20/20 tests passed.** One bug found and fixed. All 8 enabled cron jobs wired up with agent-teams inbox polling and status reporting.
