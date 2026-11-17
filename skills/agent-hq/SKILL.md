---
name: agent-hq
description: Working protocol for Agent HQ - use whenever starting work in a project, when the user asks for any work (record it as a task first), when finishing a chunk of work (write a result entry), or when blocked on the user. Also use when the user asks what is going on across their projects, what is overdue, or where something was left off.
---

# Agent HQ protocol

Agent HQ is the shared memory of every project on this machine: tasks, a journal of
results and decisions, and "where we left off". The next session, human or agent,
starts from it instead of re-reading the codebase. Tools: the `agent-hq` MCP server
(briefing, task_add, task_update, task_list, log, project_list, project_update,
import_projects, deal_add, deal_update, agent_cost). The `agent-hq` CLI does the same
from a shell.

## The loop

1. **Start**: the SessionStart hook already printed the briefing. If it did not,
   call `briefing`. Read it before opening files.
2. **User asks for work**: call `task_add` right away, before doing the work.
   Don't ask permission. More than one step? Add subtasks with `parent_id`.
   Put context and the acceptance criterion in `body` - write the criterion
   before the code, it is how you know when to stop.
3. **Start a task**: `task_update status=doing`.
4. **Blocked on the human** (needs a key, access, a decision): `task_update
   status=blocked blocked_by="what we wait for"` and tell the user.
5. **Done**: check the result against the criterion, then `task_update
   status=done` and one `log kind=result`.
6. **Decisions** that change the plan: `log kind=decision` with the reason.

## Writing a result entry

One entry per meaningful chunk of work, plain prose, enough for someone to
continue in a month without reading code:

- what works now and how to check it (URL, command, screen);
- where it runs: server, database, deploy command;
- decisions and why this option;
- traps found: what broke, why, how it was fixed;
- what is missing (access, keys, client answers) - that is a blocker;
- exactly where you stopped and the logical next step.

Never write secret values (keys, passwords, tokens) into Agent HQ - only that a key is
needed and where it lives.

## Stop rules

- Acceptance criterion met: stop and close the task. Good enough is a valid result.
- Two attempts in a row failed: stop, mark blocked, explain what is in the way.
- The task turns out not to move the goal: propose dropping it (`status=drop`) and say why.
