---
name: review-before-done
description: Review your own change as if a stranger wrote it, before saying "done", committing, or opening a pull request. Use at the end of any task that changed code, and when the user asks to review a diff.
---

# Review before done

"Done" means the user can rely on it. Read the diff once more with fresh eyes, as a
reviewer who does not trust the author.

## 1. Look at the whole diff

`git diff` (or the staged diff). Every changed line should be there on purpose. Remove
debug prints, commented-out code, stray files, unrelated formatting churn.

## 2. Check against the acceptance criterion

Go through each line of the task's criterion and verify it by running something, not
by reading code. If a line can't be verified here, say so explicitly.

## 3. Edges

For each input the change handles, ask what happens with:

- empty, null, zero, negative, very large, unicode, whitespace-only values;
- the second call (idempotency), two calls at once (races), a retry after failure;
- the network or a dependency failing, timing out, returning garbage;
- a user without permission, a logged-out user, another tenant's id.

## 4. Safety

- User input reaches HTML only through escaping; SQL only through parameters;
  shells only through argument lists, never string concatenation.
- No secrets in code, logs, error messages or commits.
- New permissions, scopes or CORS rules are as narrow as possible.

## 5. Readability

Names say what things are. Functions do one thing. A comment explains why, not what.
Could the next person (or session) change this safely without you?

## 6. Run the checks

Tests, type checker, linter, build - whatever the project has. Report what you ran and
the result. Don't claim "tests pass" for tests you did not run.

## Report format

Finish with a short report:

- what changed (one or two lines);
- how it was verified (commands, clicks);
- what was not verified and why;
- known limitations or follow-ups.

With Agent HQ, this report is the `log kind=result` entry, and the task moves to
`done` (or `review` when a human must look first).
