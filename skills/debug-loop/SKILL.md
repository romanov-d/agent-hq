---
name: debug-loop
description: A disciplined loop for bugs, failing tests, crashes, regressions and "it doesn't work". Use whenever something behaves differently from what is expected, before proposing a fix, and especially after a first fix attempt did not work.
---

# Debug loop

Guessing at fixes is the slowest way to debug. Each step below exists to replace a
guess with an observation.

## 1. Reproduce

Get a command, test or click path that shows the bug every time. Write it down. If you
cannot reproduce it, collect evidence first (logs, the exact input, versions, the
environment) instead of changing code.

## 2. Read the actual error

The full message and stack trace, top to bottom, including the first frame in your own
code. Look up the line it points to. Many bugs are solved here.

## 3. Shrink the problem

Remove everything that is not needed to trigger it: smaller input, one request, one
component, a failing unit test. Find the last version that worked if there is one
(`git log`, `git bisect`) and diff it against the broken one.

## 4. One hypothesis at a time

State it in one sentence: "The order total is wrong because tax is applied twice when
a coupon is present." Then design a check that would prove it wrong: a log line, an
assertion, a breakpoint, a query. Run it. Keep the result, right or wrong.

Never change two things at once. Never keep a change that did not fix anything.

## 5. Fix the cause, not the symptom

A null check that hides a value that should never be null moves the bug elsewhere.
Fix where the bad state is created. If the real fix is large, say so and propose it
rather than patching around it silently.

## 6. Prove it

- Run the reproduction from step 1: it must pass now.
- Add a regression test when the project has tests.
- Run the surrounding test suite: the fix must not break neighbours.

## Stop rule

Two fix attempts that did not work means your model of the system is wrong. Stop
editing. Re-read the code path end to end, add logging, and write down what you now
know and don't know. If still stuck, report to the user: what you tried, what you
observed, your best remaining hypothesis. With Agent HQ, mark the task `blocked` with
what you need.

## Record what you learned

When the cause was not obvious, write it down (`log kind=result`): symptom, cause,
fix, how to spot it next time. Future sessions will meet the same trap.
