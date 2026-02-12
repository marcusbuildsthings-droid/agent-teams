"""Core library for agent-teams: team management, mailbox IPC, task coordination."""

import json
import os
import fcntl
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

TEAMS_ROOT = Path.home() / ".openclaw" / "teams"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_identity(identity: str) -> tuple[str, str]:
    """Parse 'name@team' into (name, team)."""
    if "@" not in identity:
        raise ValueError(f"Invalid identity '{identity}', expected name@team")
    name, team = identity.split("@", 1)
    return name, team

def _team_dir(team: str) -> Path:
    return TEAMS_ROOT / team

def _inbox_path(team: str, agent: str) -> Path:
    return _team_dir(team) / "inboxes" / f"{agent}.json"

def _tasks_dir(team: str) -> Path:
    return _team_dir(team) / "tasks"

def _config_path(team: str) -> Path:
    return _team_dir(team) / "config.json"

def _cursor_path(team: str, agent: str) -> Path:
    return _team_dir(team) / "inboxes" / f".{agent}.cursor"

# ── Team Management ──

def create_team(team: str, members: Optional[list[str]] = None) -> dict:
    d = _team_dir(team)
    d.mkdir(parents=True, exist_ok=True)
    (d / "inboxes").mkdir(exist_ok=True)
    (d / "tasks").mkdir(exist_ok=True)
    config = {"name": team, "members": members or [], "created": _now()}
    _config_path(team).write_text(json.dumps(config, indent=2))
    # Create inboxes for initial members
    for m in (members or []):
        _inbox_path(team, m).write_text("[]")
    return config

def delete_team(team: str) -> bool:
    import shutil
    d = _team_dir(team)
    if d.exists():
        shutil.rmtree(d)
        return True
    return False

def add_member(team: str, name: str) -> dict:
    cp = _config_path(team)
    config = json.loads(cp.read_text())
    if name not in config["members"]:
        config["members"].append(name)
        cp.write_text(json.dumps(config, indent=2))
    _inbox_path(team, name).write_text("[]")
    return config

def remove_member(team: str, name: str) -> dict:
    cp = _config_path(team)
    config = json.loads(cp.read_text())
    config["members"] = [m for m in config["members"] if m != name]
    cp.write_text(json.dumps(config, indent=2))
    inbox = _inbox_path(team, name)
    if inbox.exists():
        inbox.unlink()
    cursor = _cursor_path(team, name)
    if cursor.exists():
        cursor.unlink()
    return config

def list_teams() -> list[dict]:
    if not TEAMS_ROOT.exists():
        return []
    teams = []
    for d in sorted(TEAMS_ROOT.iterdir()):
        cp = d / "config.json"
        if cp.exists():
            teams.append(json.loads(cp.read_text()))
    return teams

def team_info(team: str) -> dict:
    return json.loads(_config_path(team).read_text())

# ── Mailbox ──

def send_message(from_id: str, to_id: str, text: str, msg_type: str = "message") -> dict:
    from_name, from_team = _parse_identity(from_id)
    to_name, to_team = _parse_identity(to_id)
    if from_team != to_team:
        raise ValueError("Cross-team messaging not supported")
    msg = {
        "id": str(uuid.uuid4())[:8],
        "from": from_name,
        "to": to_name,
        "type": msg_type,
        "text": text,
        "timestamp": _now(),
    }
    _append_to_inbox(to_team, to_name, msg)
    return msg

def broadcast(from_id: str, text: str, msg_type: str = "broadcast") -> list[dict]:
    from_name, team = _parse_identity(from_id)
    config = team_info(team)
    msgs = []
    for member in config["members"]:
        if member != from_name:
            msg = {
                "id": str(uuid.uuid4())[:8],
                "from": from_name,
                "to": member,
                "type": msg_type,
                "text": text,
                "timestamp": _now(),
            }
            _append_to_inbox(team, member, msg)
            msgs.append(msg)
    return msgs

def _append_to_inbox(team: str, agent: str, msg: dict):
    path = _inbox_path(team, agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    # File-locked append
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            inbox = json.loads(content) if content else []
            inbox.append(msg)
            f.seek(0)
            f.truncate()
            f.write(json.dumps(inbox, indent=2))
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def poll_inbox(identity: str, format: str = "xml") -> str:
    """Poll inbox for new messages since last read. Returns XML or JSON."""
    name, team = _parse_identity(identity)
    inbox_path = _inbox_path(team, name)
    cursor_path = _cursor_path(team, name)
    
    if not inbox_path.exists():
        return "" if format == "xml" else "[]"
    
    with open(inbox_path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            content = f.read().strip()
            messages = json.loads(content) if content else []
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    
    # Read cursor (index of last read message)
    cursor = 0
    if cursor_path.exists():
        cursor = int(cursor_path.read_text().strip())
    
    new_msgs = messages[cursor:]
    # Update cursor
    cursor_path.write_text(str(len(messages)))
    
    if not new_msgs:
        return "" if format == "xml" else "[]"
    
    if format == "json":
        return json.dumps(new_msgs, indent=2)
    
    # XML format for context injection
    parts = []
    for msg in new_msgs:
        parts.append(
            f'<teammate-message from="{msg.get("from", "unknown")}" '
            f'team="{team}" type="{msg.get("type", "message")}" '
            f'timestamp="{msg.get("timestamp", "")}">\n'
            f'{msg.get("text", "")}\n'
            f'</teammate-message>'
        )
    return "\n".join(parts)

def read_inbox(identity: str) -> list[dict]:
    """Read all messages in inbox without advancing cursor."""
    name, team = _parse_identity(identity)
    path = _inbox_path(team, name)
    if not path.exists():
        return []
    return json.loads(path.read_text() or "[]")

# ── Tasks ──

def create_task(team: str, subject: str, description: str = "", assigned_to: str = "", assigned_by: str = "") -> dict:
    tasks_dir = _tasks_dir(team)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = tasks_dir / ".lock"
    
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            existing = [f for f in tasks_dir.glob("*.json")]
            task_id = str(len(existing) + 1)
            task = {
                "id": task_id,
                "subject": subject,
                "description": description,
                "status": "pending",
                "assigned_to": assigned_to or None,
                "assigned_by": assigned_by or None,
                "created": _now(),
                "claimed_at": None,
                "completed_at": None,
                "result": None,
            }
            (tasks_dir / f"{task_id}.json").write_text(json.dumps(task, indent=2))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    
    # If assigned, send task_assignment message
    if assigned_to and assigned_by:
        send_message(
            f"{assigned_by}@{team}",
            f"{assigned_to}@{team}",
            json.dumps({"type": "task_assignment", "taskId": task_id, "subject": subject, "description": description}),
            msg_type="task_assignment"
        )
    
    return task

def claim_task(team: str, task_id: str, agent: str) -> dict:
    tasks_dir = _tasks_dir(team)
    lock_path = tasks_dir / ".lock"
    task_path = tasks_dir / f"{task_id}.json"
    
    if not task_path.exists():
        raise ValueError(f"Task {task_id} not found")
    
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            task = json.loads(task_path.read_text())
            if task["status"] != "pending":
                raise ValueError(f"Task {task_id} is {task['status']}, cannot claim")
            task["status"] = "in_progress"
            task["assigned_to"] = agent
            task["claimed_at"] = _now()
            task_path.write_text(json.dumps(task, indent=2))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return task

def complete_task(team: str, task_id: str, agent: str, result: str = "") -> dict:
    tasks_dir = _tasks_dir(team)
    lock_path = tasks_dir / ".lock"
    task_path = tasks_dir / f"{task_id}.json"
    
    if not task_path.exists():
        raise ValueError(f"Task {task_id} not found")
    
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            task = json.loads(task_path.read_text())
            if task["status"] != "in_progress":
                raise ValueError(f"Task {task_id} is {task['status']}, cannot complete")
            task["status"] = "completed"
            task["completed_at"] = _now()
            task["result"] = result
            task_path.write_text(json.dumps(task, indent=2))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return task

def list_tasks(team: str, status: Optional[str] = None) -> list[dict]:
    tasks_dir = _tasks_dir(team)
    if not tasks_dir.exists():
        return []
    tasks = []
    for f in sorted(tasks_dir.glob("*.json")):
        task = json.loads(f.read_text())
        if status is None or task["status"] == status:
            tasks.append(task)
    return tasks
