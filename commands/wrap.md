---
description: Close the session properly - update tasks and write the result entry
---

Wrap up this session in Agent HQ:

1. `task_list` for the current project. For every task touched in this session set the right status (done only if its acceptance criterion is met; blocked with blocked_by if waiting on the user).
2. Write one `log` entry with `kind: result` following the result-entry rules of the agent-hq skill: what works now and how to check it, decisions, traps, what is missing, where exactly we stopped and the next step.
3. Show the user the entry and the task changes in a few lines.
