---
description: Where we left off - state of the current project or of all projects
argument-hint: "[project | all]"
---

If $ARGUMENTS is "all": call `project_list`, then `task_list` with `all_projects: true`, and give the user a short portfolio view: active projects, what is in progress, what is blocked and on whom, overdue tasks.

Otherwise call `briefing` (with `project: $ARGUMENTS` if given) and summarize it in a few lines: where we left off, what is in progress, what is blocked, and the logical next step.
