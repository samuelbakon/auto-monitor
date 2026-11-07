# 03 · Git workflow (Milestone 1)

## Branches

| Branch | Purpose | Who can write | Deploys? |
|---|---|---|---|
| `main` | Always releasable. Only source of releases | Nobody directly — PR + review + green CI | Yes (only branch allowed to deploy) |
| `feature/<name>`, `fix/<name>` | Daily work | Any developer | No |
| `test/<sec-xx-name>` | Security test scenarios (SEC-01…10) | Security engineer | Never |

Short-lived branches + pull requests into `main` ("GitHub flow"). A separate `develop`
branch is not needed for one team; CI still runs on `develop` if it is created.

## Rules on `main` (enforced by branch protection, `scripts/protect-branches.sh`)
1. Pull request required, **1 approval**, approvals dismissed when new commits arrive.
2. **Code-owner review** for `.github/**`, Dockerfiles, compose, security code (`.github/CODEOWNERS`).
3. Required status check **"CI evidence"** (= every CI stage green), branch must be up to date.
4. No force-push, no deletion, linear history, conversations resolved.

## Commit conventions
`feat:`, `fix:`, `ci:`, `sec:`, `docs:` prefixes. One logical change per commit.

## Release flow
```
feature/x ──PR──► main ──(CI green)──► CDL (deployment repo) ──► image signed + manifest
                                                           └──► CDP ─► staging ─► [approval] ─► production
```
