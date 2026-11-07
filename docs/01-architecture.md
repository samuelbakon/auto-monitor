# 01 · auto-monitor — Architecture & execution (Milestone 1)

> In the assignment the application is called **Co-note**. For this project the
> application delivered is **auto-monitor** (`github.com/samuelbakon/auto-monitor`, forked).

## 1. What the application does
auto-monitor is a web app driven by an AI agent: a user chats with it, and the
agent analyses Git repositories and product objectives, then plans, tracks and
assigns tasks. **The chat is the only user interface.**

## 2. Components

| Component | Folder | Technology | Role | Port |
|---|---|---|---|---|
| Frontend | `frontend/` | Nuxt 3 + Vue 3 + Tailwind (Node 22) | Chat UI, proxies `/api/v1/**` to the backend | 3000 (public) |
| WebSocket gateway | `ws-gateway/` | Node 22 + TypeScript (`ws`, `jose`) | Browser ⇄ backend real-time channel, checks JWT via JWKS | 4000 (public) |
| Backend | `backend/` | Spring Boot 3.4 / Java 21 (Maven) | Login (JWT RS256), business API, internal API for the agent | 8080 (internal) |
| Agent | `agent/` | Python 3.12, FastAPI, APScheduler | Autonomous loop, LLM calls (Mistral → OpenAI, or `mock`), Git operations | 8000 (internal) |
| Business DB | — | MySQL 8.4 | users, projects, objectives, tasks, bugs, messages (Flyway migrations) | 3306 (internal) |
| Agent memory | `postgres/` | PostgreSQL 16 + pgvector | agent state, actions, memories, jobs (`init.sql`) | 5432 (internal) |

**Request flow (chat):** Browser → Nuxt (3000) → WebSocket → ws-gateway (4000) → backend (8080) → agent (8000) → ws-gateway → Browser.
The backend is never exposed directly; `/internal/**` routes require the `X-Internal-Token` header.

**External dependencies:** LLM APIs (Mistral, OpenAI, Gemini — optional, `LLM_PROVIDER=mock` works without keys),
remote Git hosts (GitHub/GitLab) the agent clones with a per-repo token, public package registries
(npm, Maven Central, PyPI) and container base images (Docker Hub) at build time.

## 3. Dependency manifests & lockfiles

| Component | Manifest | Lockfile | Comment |
|---|---|---|---|
| frontend | `package.json` | `package-lock.json` ✅ | exact versions |
| ws-gateway | `package.json` | `package-lock.json` ✅ | exact versions |
| backend | `pom.xml` | ❌ (Maven has none) | versions fixed by Spring Boot parent 3.4.4 |
| agent | `requirements.txt` | ❌ | **version ranges** (`fastapi>=0.115,<1.0`) → builds are not reproducible and scanners cannot read it (see risk R-08) |

## 4. How it is built and run (current process)

```bash
cp .env.example .env              # then fill passwords, tokens, keys
sh scripts/gen-jwt-key.sh         # RSA key -> JWT_PRIVATE_KEY
mkdir -p data/postgres data/mysql data/repos
sudo chown -R 999:999 data/postgres data/mysql && sudo chown -R 1000:1000 data/repos
docker compose up -d --build      # builds the 4 images ON the host, starts 6 containers
sh scripts/check.sh               # health checks
```

| Component | Build command | Test command | Run command (in image) |
|---|---|---|---|
| backend | `mvn package` | `mvn verify` (JUnit) | `java -jar app.jar` |
| agent | `pip install -r requirements.txt` | `pytest` (15 tests) + `ruff` | `uvicorn app.main:app` |
| ws-gateway | `npm ci && npm run build` (tsc) | `vitest run` (4 tests) | `node dist/server.js` |
| frontend | `npm ci && npm run build` (nuxt) | `nuxi typecheck` (no unit tests) | `node .output/server/index.mjs` |

**Before this project:** deployment = someone runs `git pull && docker compose up -d --build` on the server.
No pipeline, no tests or scans before deployment, images built on the production host, no approval, no record of who deployed what.

## 5. Configuration values (dev vs production)

| Variable | Sensitive? | Dev | Production |
|---|---|---|---|
| `PG_PASSWORD`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | 🔴 secret | `change_me` | long random, per environment |
| `INTERNAL_API_TOKEN` | 🔴 secret | placeholder | long random |
| `JWT_PRIVATE_KEY` | 🔴 secret (signs every login token) | generated locally | generated, stored as environment secret |
| `ENCRYPTION_KEY` | 🔴 secret (AES-256 of Git tokens in DB) | generated locally | generated, stored as environment secret |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 🔴 secret | `admin`/`admin` default! | random |
| `MISTRAL_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` | 🔴 secret | empty / `LLM_PROVIDER=mock` | real keys |
| `PUBLIC_URL`, `PUBLIC_WS_URL` | 🟢 not secret | `http://localhost:3000`, `ws://localhost:4000` | public HTTPS / WSS URL |
| `LLM_PROVIDER_ORDER`, `HEARTBEAT_MINUTES`, `LLM_DAILY_TOKEN_BUDGET` | 🟢 | defaults | tuned |

## 6. Files that contain or could contain sensitive information

| File | Why sensitive | Protection |
|---|---|---|
| `.env` | all secrets above | in `.gitignore` ✅; CI hygiene check fails if tracked |
| `data/` (bind mounts) | full database contents | in `.gitignore` ✅ |
| `backup/*.sql` | database dumps | in `.gitignore` ✅ |
| `data/repos/*/.git/config` | the agent embeds the Git token in the clone URL | stays on the host volume — risk R-06 |
| `backend/src/test/.../JwtServiceTest.java` | **contains a real RSA private key** (test fixture, found by Gitleaks) | approved exception EXC-06, to be removed |
| `scripts/gen-jwt-key.sh` output | prints the private key to the terminal | never paste it anywhere except the secret store |

## 7. Bug found while running it locally
The backend readiness probe includes the agent (`readiness: …,agent`) while the agent
`depends_on: backend: service_healthy` → **start-up deadlock** (backend waits for agent, agent waits for backend).
Fix applied in `docker-compose.yml`: agent depends on `backend: service_started` (risk R-11).
