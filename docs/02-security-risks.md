# 02 · Initial security risk list (Milestone 1)

Likelihood/Impact: H = high, M = medium, L = low. "Control" = where this project addresses it.

| ID | Risk | L | I | Control in this project |
|---|---|---|---|---|
| R-01 | Secrets committed to Git (`.env`, keys, passwords) | M | H | CI hygiene check, Gitleaks full-history scan (CDL), Trivy secret scan, `.gitignore` |
| R-02 | **Real RSA private key already in Git history** (`JwtServiceTest.java`) | — | M | Detected by Gitleaks; approved exception EXC-06 (test only); plan: generate at runtime + purge history |
| R-03 | Default admin credentials `admin/admin` if `ADMIN_PASSWORD` unset | M | H | Deploy compose refuses to start without `ADMIN_PASSWORD`; random per environment |
| R-04 | Vulnerable third-party dependencies (npm, Maven, PyPI) | H | H | SCA (Trivy) in CI, image scan in CDL, Dependabot |
| R-05 | Unpinned Python dependencies (ranges) → non-reproducible, unscannable | H | M | CI resolves exact versions before scanning; recommendation: commit a lockfile |
| R-06 | Agent stores Git tokens inside clone URLs on disk | M | H | Volume not exposed; recommendation: credential helper instead of URL |
| R-07 | Images built on the production host from whatever is in the folder | H | H | Production now pulls signed images **by digest**, never builds |
| R-08 | No tests/scans before deployment | H | H | CI + CDL gates; nothing deploys without green CI |
| R-09 | Anyone with server access can deploy anything, no trace | M | H | Protected environment + approval + deployment records |
| R-10 | ws-gateway and frontend ports published on all interfaces | M | M | Deploy compose binds 127.0.0.1; ALB + WAF in Terraform |
| R-11 | Start-up deadlock backend ⇄ agent (availability) | H | M | Fixed in compose |
| R-12 | Containers run with all default Linux capabilities | M | M | `cap_drop: ALL`, `no-new-privileges` in deploy compose |
| R-13 | Compromised CI tool / GitHub Action (e.g. Trivy action hijack, CVE-2026-33634) | M | H | Actions pinned by full SHA; tool binaries sha256-verified |
| R-14 | Origin check of WebSocket skipped when no `Origin` header | L | M | Documented; JWT still required |
| R-15 | LLM prompt-injection through repository content read by the agent | M | M | Out of scope of CI/CD — listed as limitation |

## Answers — Milestone 1 investigation questions
See `auto-monitor-deployment/docs/QA.md` (all milestones).
