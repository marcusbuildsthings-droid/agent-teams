"""CLI for agent-teams."""

import argparse
import json
import sys
from . import core


def main():
    parser = argparse.ArgumentParser(prog="agent-teams", description="Agent team coordination")
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command")

    # team create
    p = sub.add_parser("create", help="Create a team")
    p.add_argument("team", help="Team name")
    p.add_argument("--members", nargs="*", default=[], help="Initial members")

    # team delete
    p = sub.add_parser("delete", help="Delete a team")
    p.add_argument("team")

    # team list
    sub.add_parser("list", help="List teams")

    # team info
    p = sub.add_parser("info", help="Team info")
    p.add_argument("team")

    # add-member
    p = sub.add_parser("add-member", help="Add member to team")
    p.add_argument("team")
    p.add_argument("name")

    # remove-member
    p = sub.add_parser("remove-member", help="Remove member from team")
    p.add_argument("team")
    p.add_argument("name")

    # send
    p = sub.add_parser("send", help="Send a message")
    p.add_argument("sender", help="sender@team")
    p.add_argument("recipient", help="recipient@team")
    p.add_argument("--text", "-t", required=True)
    p.add_argument("--type", default="message", dest="msg_type")

    # broadcast
    p = sub.add_parser("broadcast", help="Broadcast to team")
    p.add_argument("sender", help="sender@team")
    p.add_argument("--text", "-t", required=True)

    # poll
    p = sub.add_parser("poll", help="Poll inbox for new messages")
    p.add_argument("identity", help="agent@team")
    p.add_argument("--format", choices=["xml", "json"], default="xml")

    # inbox
    p = sub.add_parser("inbox", help="Read full inbox")
    p.add_argument("identity", help="agent@team")

    # task create
    p = sub.add_parser("task-create", help="Create a task")
    p.add_argument("team")
    p.add_argument("--subject", "-s", required=True)
    p.add_argument("--description", "-d", default="")
    p.add_argument("--assign-to", default="")
    p.add_argument("--assign-by", default="")

    # task claim
    p = sub.add_parser("task-claim", help="Claim a task")
    p.add_argument("team")
    p.add_argument("task_id")
    p.add_argument("agent")

    # task complete
    p = sub.add_parser("task-complete", help="Complete a task")
    p.add_argument("team")
    p.add_argument("task_id")
    p.add_argument("agent")
    p.add_argument("--result", "-r", default="")

    # task list
    p = sub.add_parser("task-list", help="List tasks")
    p.add_argument("team")
    p.add_argument("--status", choices=["pending", "in_progress", "completed"])

    args = parser.parse_args()
    use_json = args.json

    def output(data):
        if use_json:
            print(json.dumps(data, indent=2))
        else:
            print(json.dumps(data, indent=2))

    try:
        if args.command == "create":
            output(core.create_team(args.team, args.members))
        elif args.command == "delete":
            ok = core.delete_team(args.team)
            output({"deleted": ok})
        elif args.command == "list":
            output(core.list_teams())
        elif args.command == "info":
            output(core.team_info(args.team))
        elif args.command == "add-member":
            output(core.add_member(args.team, args.name))
        elif args.command == "remove-member":
            output(core.remove_member(args.team, args.name))
        elif args.command == "send":
            output(core.send_message(args.sender, args.recipient, args.text, args.msg_type))
        elif args.command == "broadcast":
            output(core.broadcast(args.sender, args.text))
        elif args.command == "poll":
            result = core.poll_inbox(args.identity, args.format)
            if result:
                print(result)
        elif args.command == "inbox":
            output(core.read_inbox(args.identity))
        elif args.command == "task-create":
            output(core.create_task(args.team, args.subject, args.description, args.assign_to, args.assign_by))
        elif args.command == "task-claim":
            output(core.claim_task(args.team, args.task_id, args.agent))
        elif args.command == "task-complete":
            output(core.complete_task(args.team, args.task_id, args.agent, args.result))
        elif args.command == "task-list":
            output(core.list_tasks(args.team, args.status))
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
