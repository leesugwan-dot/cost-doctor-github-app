# Privacy-safe user evidence reporting

CostDoctor keeps external telemetry off. User evidence is derived only from public, repository-native GitHub metadata for this repository.

## What is counted

- External public-scan Issue requests whose title starts with `[CostDoctor Scan]`
- Successful runs of the trusted `public-scan.yml` workflow initiated by an external actor
- Public feedback Issues whose title starts with `[CostDoctor Feedback]`
- Repository stars and forks as interest signals only, not as confirmed users

Each repository-native scan/run is classified in memory into `OWNER_TEST`, `ANONYMOUS_PUBLIC_REQUEST`, or `CONFIRMED_EXTERNAL_ACTOR`. Outcomes are tracked separately as `PUBLIC_SCAN_SUCCESS` or `PUBLIC_SCAN_FAILURE`. Owner tests never increase external-user counts.

## What is never persisted or reported

- Customer source code, filenames, user Issue bodies or comments, secrets, or private-repository activity
- Marketplace installation identities or counts, because GitHub does not expose that Evidence here
- External analytics, cookies, pixels, or third-party telemetry

Reports contain aggregate counts only. Usernames are processed in memory solely to deduplicate public actors and are never written to the report, artifact, log, or notification Issue.

The minimum funnel is `request_received → validation_pass → dispatch_pass → scan_pass → result_pass`, plus a failure category when a trusted run fails. No IP, source, filename, secret, clickstream, or permanent request profile is stored.

GitHub's Issues API may include body fields in its response. The reporter never inspects, persists, or outputs user Issue bodies or comments; it reads only the machine marker in its own tracking Issue to prevent duplicate notifications.

## When the owner is notified

The workflow runs after the public-scan workflow, once per day, and on manual dispatch. It always writes a GitHub Actions Summary and a short-lived aggregate artifact.

If a new external scan request, successful external scan, or feedback Issue is detected, it creates or updates one repository Issue titled `[CostDoctor User Evidence] External usage detected`. It stays quiet when there is no new user Evidence.

Private Self-Scan usage remains unknown by design because it runs inside the customer's repository with `contents: read` and no telemetry.
