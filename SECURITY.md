# Security Policy

## Supported Versions

xVAULT is developed as a rolling Kodi add-on. Security fixes are only provided for
the current public release that is listed in `addon.xml` and on the GitHub Page.
Older ZIP packages remain available for compatibility checks, but they do not
receive separate security backports.

| Version | Supported |
| ------- | --------- |
| Current public release | Yes |
| Older releases | No |

## Reporting a Vulnerability

Please do not report security vulnerabilities in public GitHub Issues,
Discussions, forum posts or screenshots.

Use one of these private reporting paths instead:

1. Open the repository on GitHub and use the Security tab if private
   vulnerability reporting is available.
2. If private reporting is not available, open a minimal public issue asking for
   a private security contact. Do not include exploit details, secrets, account
   data, logs with tokens, private URLs or personal data in that issue.

When reporting a vulnerability, include only the technical information needed to
reproduce and assess the issue:

- affected xVAULT version
- Kodi version and platform
- affected component or workflow
- concise reproduction steps
- expected and observed behavior
- relevant redacted log excerpts
- whether the issue is already public or actively exploited

Do not send passwords, API keys, Supabase keys, FTP data, MySQL credentials,
Kodi profile files, full private logs, private stream URLs or user account data.

## Scope

Security reports are in scope when they affect the xVAULT add-on, repository
metadata, generated repository page files, update flow, local settings handling,
support package creation, synchronization code or documented deployment
artifacts.

Reports are usually out of scope when they only affect third-party websites,
hosters, Kodi itself, ResolveURL, IPTV Simple, TMDb, Trakt, Supabase, GitHub or a
user's local operating system configuration. If xVAULT handles such a dependency
in an unsafe way, the xVAULT handling may still be in scope.

## Response Expectations

Security reports are triaged as soon as practical. A reasonable target is an
initial acknowledgement within seven days and a status update after assessment.
Fix timing depends on severity, reproducibility, affected platforms and whether
third-party services are involved.

If a fix is needed, it may be released as a normal xVAULT update. Public release
notes may describe the change in broad terms until users have had time to update.

## Coordinated Disclosure

Please give the project a reasonable opportunity to investigate and fix a
confirmed vulnerability before publishing technical details. Do not perform
testing that disrupts services, accesses other users' data, bypasses accounts,
exfiltrates secrets or degrades infrastructure.

Good-faith reports that follow this policy are appreciated.
