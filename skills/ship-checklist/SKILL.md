---
name: ship-checklist
description: Checklist for deploying or releasing - to production, staging, an app store or a package registry. Use when the user says deploy, ship, release, publish, go live, push to prod, or submit a build, and before any irreversible step.
---

# Ship checklist

Deploys are where small mistakes become outages. Go through this in order; stop at the
first item that fails.

## Before

- [ ] **The user asked for this deploy**, to this environment, now. Production deploys,
      store submissions and package publishes are irreversible enough to need an
      explicit yes in this conversation.
- [ ] **Clean tree**: everything committed, on the intended branch, pushed.
- [ ] **Checks green**: tests, build and type check pass locally or in CI.
- [ ] **Config**: every environment variable the new code reads exists in the target
      environment. Never print their values; check presence only.
- [ ] **Database**: migrations reviewed; additive when possible; a backup or snapshot
      exists if a migration touches existing data.
- [ ] **Rollback path known**: the previous version, image or release that can be
      restored, and the command to do it.

## During

- Deploy with the project's own command or pipeline, not an ad-hoc variant.
- Watch the output to the end. A deploy that "probably worked" did not.

## After

- [ ] **Smoke test** the real environment: the page loads, login works, the changed
      feature works with real (or test-mode) data.
- [ ] **Logs and errors** for the first minutes: no new exceptions, no spike in 5xx.
- [ ] **Version visible**: commit hash, release tag or build number recorded.

## Write it down

Record where it runs and how to redeploy, so nobody has to rediscover it:

- where production lives (host, region, service name);
- the deploy command or pipeline;
- where config and secrets are managed (the location, never the values);
- how to roll back.

With Agent HQ, put this in a `log kind=result` entry: "Deployed v1.4.2 (abc123) to
prod on Fly; smoke-tested checkout; rollback: `fly releases rollback 41`".

## If it breaks

Roll back first, investigate second. Tell the user what happened, what was rolled back,
and what is still unknown.
