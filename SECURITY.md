# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private vulnerability reporting ("Security" tab → "Report a vulnerability") on this
repository. Include:

- what is affected (endpoint, component, version or commit),
- steps to reproduce or a proof of concept,
- the impact you expect.

We aim to acknowledge reports within 3 working days and to ship a fix or mitigation for
high-severity issues within 14 days. We will credit you in the release notes unless you ask us not to.

Please test only against your own local deployment (`docker compose up`). Do not test against other
people's instances, do not access other users' data, and do not run denial-of-service tests.

## Supported versions

Only the latest commit on `main` receives security fixes while the project is pre-1.0.

## What we already do

See [docs/threat-model.md](docs/threat-model.md) for assets, attackers and controls. In short:
argon2id passwords, short-lived JWT in httpOnly/Secure/SameSite cookies, rotating refresh tokens with
reuse detection, double-submit CSRF + Origin check, owner checks on every resource (IDOR tests),
content-based image validation and re-encoding, SSRF-guarded outbound fetches, per-IP and per-user
rate limits, atomic credit ledger, encrypted BYOK keys that never return to the browser, strict CORS
allowlist and security headers, secret scanning (gitleaks), pinned dependencies, pip-audit and
npm audit in CI.
