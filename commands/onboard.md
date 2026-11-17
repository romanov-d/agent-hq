---
description: Import your projects into Agent HQ - scan code folders, register repos, show the result
argument-hint: "[folders to scan]"
---

Onboard the user into Agent HQ.

1. Call the `import_projects` tool without `add` to preview. Use $ARGUMENTS as `roots` if given, otherwise the defaults.
2. Show the user the list grouped by section (site, app, mobile, bot, game, lib, infra, content, other) with a count. Point out anything that looks like junk (copies, demos, downloaded templates).
3. Ask which to skip, then call `import_projects` with `add: true`. For folders the user wants skipped that got registered, set `project_update status=archive`.
4. Call `project_list` and summarize: how many projects, by section, which have recent commits.
5. Call the `dashboard` tool and give the user the URL.
