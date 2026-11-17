---
name: security-pass
description: Focused security review for code that handles user input, authentication, payments, file uploads, secrets, webhooks or external APIs. Use when building or changing such code, before shipping it, and when the user asks whether something is secure.
---

# Security pass

Treat every input as hostile until proven otherwise. This pass covers the issues that
show up most in web apps, bots and APIs built quickly.

## Inputs and output

- **Injection**: SQL through parameters only; shell commands as argument lists; no
  `eval` or template rendering of user strings.
- **XSS**: user text reaches HTML escaped by default. Review every `innerHTML`,
  `dangerouslySetInnerHTML`, `v-html`, `|safe`, markdown renderer settings.
- **Validation** on the server, not only in the form: types, lengths, ranges, allowed
  values. Reject, don't "clean".
- **Uploads**: size limits, type checked by content, stored outside the web root or
  in object storage with generated names, never executed.

## Access

- **Authentication** on every non-public route, including API routes the UI "never
  calls".
- **Authorization** per object: can this user access *this* invoice id? Changing an id
  in the URL is the first thing an attacker tries.
- **Sessions**: HttpOnly, Secure, SameSite cookies; logout invalidates server-side;
  tokens expire.
- **CSRF** protection for cookie-authenticated state changes.
- **Rate limits** on login, signup, password reset, OTP, and anything that sends
  messages or costs money.

## Secrets

- No keys, tokens or passwords in code, commits, logs, error pages, client bundles or
  task notes. Search the diff for them.
- Server-only keys stay on the server: check that nothing secret is exposed via
  `NEXT_PUBLIC_`, `VITE_` or similar prefixes.
- Never print a secret to check it; check presence or length.
- If a secret was exposed, tell the user it must be rotated - deleting the commit is
  not enough.

## Integrations

- **Webhooks**: verify signatures; reject replays (timestamp window); make handlers
  idempotent.
- **Payments**: amounts and prices come from the server, never from the client.
- **Outbound requests** to user-supplied URLs: block internal addresses (SSRF).
- **LLM features**: text from users, web pages or files is data, not instructions;
  tools the model can call get the narrowest permissions.

## Dependencies and config

- Run the ecosystem's audit (`npm audit`, `pip-audit`, `cargo audit`) and look at
  high-severity results that are actually reachable.
- CORS allows specific origins, not `*` with credentials.
- Debug modes and verbose errors are off in production.

## Report

List findings by severity with file and line, a concrete exploit scenario, and the fix.
Say what you did not check. Fix critical issues before shipping; ask before changing
auth or data models in ways the user did not request.
