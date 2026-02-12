"""Tests for agent-teams core functionality."""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

# Patch TEAMS_ROOT before importing core
_tmpdir = tempfile.mkdtemp()
import agent_teams.core as core
core.TEAMS_ROOT = Path(_tmpdir) / "teams"


def setup_function():
    """Clean up between tests."""
    import shutil
    if core.TEAMS_ROOT.exists():
        shutil.rmtree(core.TEAMS_ROOT)


def test_create_and_info():
    config = core.create_team("test-team", ["alice", "bob"])
    assert config["name"] == "test-team"
    assert set(config["members"]) == {"alice", "bob"}
    info = core.team_info("test-team")
    assert info["name"] == "test-team"


def test_list_teams():
    core.create_team("a-team")
    core.create_team("b-team")
    teams = core.list_teams()
    assert len(teams) == 2


def test_add_remove_member():
    core.create_team("test-team", ["alice"])
    core.add_member("test-team", "bob")
    info = core.team_info("test-team")
    assert "bob" in info["members"]
    core.remove_member("test-team", "bob")
    info = core.team_info("test-team")
    assert "bob" not in info["members"]


def test_delete_team():
    core.create_team("doomed")
    assert core.delete_team("doomed")
    assert not core.delete_team("nonexistent")


def test_send_and_poll():
    core.create_team("msg-team", ["alice", "bob"])
    core.send_message("alice@msg-team", "bob@msg-team", "hello bob")
    core.send_message("alice@msg-team", "bob@msg-team", "second msg")

    xml = core.poll_inbox("bob@msg-team", "xml")
    assert '<teammate-message from="alice"' in xml
    assert "hello bob" in xml
    assert "second msg" in xml

    # Second poll should return empty (cursor advanced)
    xml2 = core.poll_inbox("bob@msg-team", "xml")
    assert xml2 == ""


def test_poll_json():
    core.create_team("j-team", ["a", "b"])
    core.send_message("a@j-team", "b@j-team", "test")
    result = core.poll_inbox("b@j-team", "json")
    msgs = json.loads(result)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "test"


def test_broadcast():
    core.create_team("bc-team", ["lead", "w1", "w2"])
    msgs = core.broadcast("lead@bc-team", "all hands")
    assert len(msgs) == 2
    # Both workers got the message
    assert core.poll_inbox("w1@bc-team") != ""
    assert core.poll_inbox("w2@bc-team") != ""
    # Lead didn't get it
    assert core.poll_inbox("lead@bc-team") == ""


def test_task_lifecycle():
    core.create_team("task-team", ["lead", "worker"])
    task = core.create_task("task-team", "Do the thing", "details here")
    assert task["status"] == "pending"
    assert task["id"] == "1"

    claimed = core.claim_task("task-team", "1", "worker")
    assert claimed["status"] == "in_progress"

    completed = core.complete_task("task-team", "1", "worker", "done!")
    assert completed["status"] == "completed"
    assert completed["result"] == "done!"


def test_task_double_claim():
    core.create_team("race-team", ["a", "b"])
    core.create_task("race-team", "contested task")
    core.claim_task("race-team", "1", "a")
    with pytest.raises(ValueError, match="in_progress"):
        core.claim_task("race-team", "1", "b")


def test_task_list_filter():
    core.create_team("filter-team", ["w"])
    core.create_task("filter-team", "task 1")
    core.create_task("filter-team", "task 2")
    core.claim_task("filter-team", "1", "w")

    all_tasks = core.list_tasks("filter-team")
    assert len(all_tasks) == 2
    pending = core.list_tasks("filter-team", "pending")
    assert len(pending) == 1
    in_prog = core.list_tasks("filter-team", "in_progress")
    assert len(in_prog) == 1


def test_task_assignment_sends_message():
    core.create_team("assign-team", ["lead", "worker"])
    core.create_task("assign-team", "assigned task", "do it", assigned_to="worker", assigned_by="lead")
    xml = core.poll_inbox("worker@assign-team")
    assert "task_assignment" in xml
    assert "assigned task" in xml


def test_message_types():
    core.create_team("type-team", ["a", "b"])
    core.send_message("a@type-team", "b@type-team", "shutting down", "shutdown_request")
    xml = core.poll_inbox("b@type-team")
    assert 'type="shutdown_request"' in xml


def test_read_inbox():
    core.create_team("read-team", ["a", "b"])
    core.send_message("a@read-team", "b@read-team", "hey")
    msgs = core.read_inbox("b@read-team")
    assert len(msgs) == 1
    # read_inbox doesn't advance cursor
    xml = core.poll_inbox("b@read-team")
    assert "hey" in xml
