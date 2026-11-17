---
name: spec-first
description: Write a short spec with an acceptance criterion before writing code. Use when the user asks for a feature, a new project, a non-trivial change, or anything described loosely ("make it better", "add payments", "build a dashboard"), and when a task is about to start without a clear definition of done.
---

# Spec first

Code written against a vague request gets rewritten. Five minutes of spec saves the
rewrite, and the acceptance criterion is what tells you when to stop.

## When to skip

One-line fixes, typos, renames, and anything the user already specified to the level
of "change X to Y in file Z". Don't turn small work into paperwork.

## Steps

1. **Look before you write.** Read the code, data and config the change touches. List
   what you found that the request did not mention: existing helpers, constraints,
   conflicting behaviour, missing pieces. These findings often change the plan.
2. **Write the spec** (10-25 lines, in the task body or as a reply):
   - *Goal*: one sentence, in the user's terms.
   - *Scope*: what changes, and explicitly what does not.
   - *Approach*: the 2-5 steps you will take, naming files or modules.
   - *Acceptance*: observable checks. "Clicking Pay with a test card shows the receipt
     page and creates a row in `payments`" - not "payments work".
   - *Open questions*: only the ones you cannot answer from the code. Propose a default
     for each so the user can just say yes.
3. **Ask only what blocks you.** If every open question has a sensible default, state
   the defaults and start. If one decision really belongs to the user (money, data
   deletion, public behaviour), ask that one question and wait.
4. **Record it.** With Agent HQ: `task_add` with the spec in `body`; split the approach
   into subtasks with `parent_id`. Without it, keep the spec at the top of your reply.
5. **Build against the criterion**, then check every acceptance line yourself before
   saying done. Report each line as passed or not.

## Changing the plan

If the work reveals something the spec missed, update the spec before continuing and
say what changed and why (`log kind=decision`). A changed plan is normal; a silently
changed plan is not.

## Example acceptance criteria

| Weak | Strong |
|---|---|
| Search works | Typing "inv" in the header search lists invoices whose number or client contains "inv", within 300 ms on the demo data |
| Faster page | `/dashboard` LCP under 1.5 s on a throttled 4G profile, measured three times |
| Handle errors | When the API returns 500, the form keeps the user's input and shows "Couldn't save, try again" |
