# Q Tower — Developer / Agent Reference

Q Tower (internal repo name "Project Misty") is a self-hosted AI governance platform:
FastAPI backend (`apps/api`), Next.js 16 frontend (`apps/web`), Postgres/Redis/MinIO/
Jackson infra (`infra/`). This file is a stable architecture and setup reference, safe
to read cold. It does not contain secrets, credentials, or narrative history — those
live in a separate, gitignored `aboutproject.md` in this repo (present on dev machines
that have been used to build this project, not guaranteed to exist on a fresh clone).

## Architecture

- **Modular monolith.** Each feature lives in `apps/api/modules/<name>/` with
  `models.py` / `schemas.py` / `service.py` / `router.py`. Cross-module calls only go
  through another module's `service.py` — never import another module's router or
  reach into its models directly.
- **One central authorization check.** `apps/api/modules/authz/service.py::can(user,
  action, resource)` — every route handler must call this, never an inline role check.
  The permission matrix there is the single source of truth for who can do what.
- **Multi-tenant via Postgres RLS**, not application-level filtering.
  `core/db.py::org_scoped_session(org_id)` sets `app.current_org_id` for the session;
  every org-scoped table has a matching `CREATE POLICY ... USING (org_id =
  current_setting('app.current_org_id', true)::uuid)`. The app connects as the
  non-superuser `misty_app` role — RLS is silently bypassed if a superuser connection
  is ever used instead.
- **`ai_gateway/`** is the only allowed path to an LLM. Every real (non-mock) call must
  run inside a **Celery task**, never synchronously from a route handler — this is a
  hard rule, not a style preference, since a blocking LLM call in the request path
  would exhaust FastAPI's sync thread pool under load.
- **Branding is data** (`deployment_config` table), never hardcoded — the frontend's
  `theme-provider.tsx` applies it as CSS custom properties.
- **Licensing** is local-only (RS256 signature check, no phone-home). The signing
  private key is never shipped to a deployment; only the public verify key is.

## Non-negotiable constraints

1. Every new tenant-data table gets `org_id` + RLS from its first migration — no
   exceptions, no "add RLS later."
2. All LLM calls go through `ai_gateway/` — no direct SDK calls in feature code.
3. All auth/identity access goes through `identity/service.py` — never read the
   session cookie directly in a router.
4. Branding is data, never hardcoded in a component.
5. Modular monolith — cross-module calls only via each module's `service.py`.
6. All authorization goes through `authz.can(user, action, resource)`.
7. **AWS-portability**: 12-factor config (env vars, no hardcoded localhost), MinIO used
   only via S3-compatible SDK calls (swap-in-place for real S3 later), Dockerfiles built
   to run under ECS/Fargate without rework.
8. Never commit: `handoff.md`, `aboutproject.md`, `policy_builder.md`,
   `FullSmokeTest.md`, any `*_Handoff.md`/planning doc, `Design/`, `.env` (only
   `.env.example` with blank placeholders), `secrets/`. See `.gitignore`.

## Dev environment — three background processes, native (no Docker for the app itself)

This project runs the API, Celery worker, and frontend **natively on the dev machine**;
Docker Compose (`infra/docker-compose.yml`) is only for Postgres/Redis/MinIO/Jackson/
mock-saml. `infra/Dockerfile.api`/`Dockerfile.web` exist for the eventual real
deployment image, not for local dev.

```
cd infra && docker compose up -d          # postgres, redis, minio, jackson, mock-saml
apps/api/.venv/Scripts/python.exe -m uvicorn apps.api.main:app --port 8000   # no --reload
apps/api/.venv/Scripts/python.exe -m celery -A apps.api.core.celery_app worker \
    --loglevel=info --pool=solo -Q celery,codescan                            # Windows needs --pool=solo
cd apps/web && pnpm dev
```

**One-command bring-up**: `powershell -ExecutionPolicy Bypass -File infra\scripts\dev-up.ps1`
does all four of the above in one call — starts the infra containers, then the API/Celery/
frontend, each only if not already running (checks ports 8000/3000 and a
`infra/.celery-worker.pid` file), so it's safe to re-run any time. Logs land in
`infra/logs/{api,celery,web}.log` (gitignored) since the three processes are launched
detached with no visible console — see the gotcha below for why that's load-bearing, not
a style choice.

First-time setup on an empty database: `alembic upgrade head`, then run the seed
scripts in order — `seed_org.py`, `seed_policy_template.py`, `seed_training_modules.py`,
`generate_license.py`. A super-admin break-glass login (independent of SSO) is set up
via `apps/api/scripts/set_super_admin_password.py`, run interactively in a real
terminal (its `getpass()` prompt hangs if piped). `infra/scripts/gen-*.sh` covers the
license keypair, mock-SAML cert, and the Fernet `ENCRYPTION_KEY` (Milestone 13) —
run once per fresh deployment, values go into `infra/.env` (gitignored).

**Running real code scans** (Milestone 13) needs Linux tooling the native venv can't
provide (see gotchas below) — the api and worker also run containerized, via a compose
profile that stays off by default:

```
cd infra
docker compose --profile codescan build api worker
docker compose --profile codescan up -d api worker   # stop the native uvicorn/celery first
```

This builds/runs the exact image (`infra/Dockerfile.api`) a real deployment uses — one
always-on api container and one always-on worker container, not a container per scan
(see `aboutproject.md` Milestone 13 for the reasoning). The frontend keeps running
natively either way. Switch back to native uvicorn/celery for everything else by
stopping these two containers — `docker compose --profile codescan down`.

## Known gotchas (each one has cost real debugging time — don't rediscover these)

- **Escalations (`Raise Alert`) are deliberately, fully anonymous** — `escalation` has
  no `reporter_id` column at all (dropped in migration `0013`, not just hidden from the
  API/UI). Nobody, including an admin, can trace an alert back to who raised it — don't
  reintroduce a reporter/creator field on this table, and don't let a notification email
  or template leak the caller's identity (`notifications/templates.py`'s
  `escalation_raised` default deliberately has no `{{reporter_email}}`-style
  placeholder). A consequence: there's no per-user "my alerts" list anywhere (not on
  `/escalations`, not on `/dashboard`) — Current/Resolved Escalations are the same
  shared, org-wide lists for every viewer. Code-scan critical findings also no longer
  auto-create an escalation (dropped from `codescan/tasks.py`) — a code-scan-triggered
  alert would always have an identifiable "reporter" (whoever ran the scan), which broke
  this exact guarantee.
- **`uvicorn` has no `--reload`** in this setup — after editing backend code, kill the
  process on port 8000 and restart it, or routes silently 404 on stale code.
- **Celery on Windows needs `--pool=solo`** — the default prefork pool doesn't work
  there. Start it with `-Q celery,codescan` to pick up both the default queue and the
  Milestone 13 code-scan queue in one worker process.
- **`docker compose down -v` does not wipe this project's data.** Postgres/Redis/MinIO
  use bind mounts (`infra/data/`), not named volumes — `-v` only removes named/
  anonymous volumes. To truly wipe: `docker compose down` (no `-v`) then
  `rm -rf infra/data/{postgres,redis,minio}` (MinIO's `.minio.sys` is hidden, a plain
  `*` glob misses it).
- **docxtpl subdocs need the `{{p tag}}` prefix**, not `{{ tag }}` — the `p` strips the
  enclosing `<w:p>` so substituted XML splices in as real content. Row loops need
  `{%tr %}`/`{%tr endfor %}` each as the sole content of its own row. Always pass
  `render(..., autoescape=True)` or any `&` in the *entire* document gets corrupted.
- **Jackson** (`boxyhq/jackson:1.52.2`, pinned — later versions gate a core endpoint
  behind an Enterprise license): its admin API env var is `JACKSON_API_KEYS`, not
  `API_KEYS` despite upstream docs; the real endpoint is `/api/v1/sso`, not
  `/api/v1/connections`; its SCIM webhook signature header is `BoxyHQ-Signature`,
  format `t=<ms>,s=<hmac_sha256_hex(secret, f"{t}.{raw_body}")>`.
- **License JWT custom claims aren't auto-validated by PyJWT** — only the reserved
  `exp` claim is checked automatically. Custom claims like `expires_at` need an
  explicit check (see `licensing/service.py::validate_license`).
- **A real HTTPS callback URL is needed for any OAuth-style external integration**
  (SSO with a real IdP, in principle a shared GitHub App) if you're testing from
  `localhost` — mock providers (`mock-saml`) sidestep this for local dev; a real one
  needs a tunnel (`cloudflared`) or a real domain. Milestone 13's GitHub connection
  deliberately avoids this entirely by having each org create its own GitHub App
  inside its own org — no callback URL needed at all when the App and its install
  target are the same org.
- **Semgrep's official PyPI package does not install on Windows at all** ("Semgrep
  does not support Windows yet" — WSL or Linux/Docker required). **weasyprint**
  installs on Windows but needs native GTK/Pango runtime libraries not present by
  default — its import in `codescan/report.py` is deliberately lazy (inside the
  function, not at module top level) specifically so a machine without those libraries
  can still boot the rest of the API. Real scanner-pipeline testing needs
  `infra/Dockerfile.api` built and run, not the native dev venv.
- **`httpx` must stay `<0.28.0`** — `litellm==1.56.4` requires it, and a fresh
  `pip install -r requirements.txt` (e.g. a Docker build) enforces this strictly even
  though an already-populated native venv can silently tolerate the conflict.
- **`setuptools` must stay `<81`** — Semgrep's own tracing dependency
  (`opentelemetry-instrumentation-requests`) still imports the legacy `pkg_resources`
  module, removed from `setuptools` 81+.
- **Docker Compose's `env_file:` loading interpolates `$word` as a `${word}` variable
  reference** — any secret containing a literal `$` (a bcrypt hash's `$2b$12$...` format
  is the concrete case that bit this project) gets silently corrupted when passed into a
  container this way. Fix: store it base64-encoded instead (see
  `settings.super_admin_password_hash_b64`, decoded via a `@property` — same pattern
  `license_public_key_pem` already used). Don't put a raw `$`-bearing secret in
  `infra/.env` and assume `env_file:` passes it through untouched.
- **Presigned MinIO URLs need a browser-reachable host, not the internal Docker network
  hostname.** When api/worker run containerized, `MINIO_ENDPOINT=http://minio:9000` is
  correct for their own upload/download calls but produces unusable download links (the
  browser can't resolve `minio`). `core/storage.py` signs presigned URLs with a
  *separate* client against `settings.minio_public_endpoint` (falls back to
  `minio_endpoint` when unset, the normal native-dev case) — set
  `MINIO_PUBLIC_ENDPOINT=http://localhost:9000` for the containerized services.
- **Every `User` (or other org-scoped table) lookup must go through `org_scoped_session`
  or an existing `identity_service` helper that already does — never a bare
  `SessionLocal()`.** A bare session bypasses RLS silently rather than erroring cleanly,
  which can manifest as confusing symptoms far from the actual bug (a Celery task's own
  `_load_user` helper using plain `SessionLocal()` surfaced as a Postgres
  `invalid input syntax for type uuid: ""` error deep in an unrelated-looking query, not
  as an obvious permissions failure). `Org` itself is the one legitimate exception — it
  has no RLS since it's the tenant root, not tenant data.
- **A plain `Start-Process`'d background window on Windows dies when the process/job that
  launched it exits** — this bit `dev-up.ps1` twice (API and frontend windows "started
  successfully" then silently vanished a few seconds after the launching call returned).
  True whenever `dev-up.ps1` itself is invoked by something sandboxed under a Windows Job
  Object (an agent/automation tool, not a human typing in their own terminal) — the job's
  cleanup kills every spawned window in the tree, `-NoExit` or not. Fix: launch each
  process via a one-shot Scheduled Task (`schtasks /create` + `/run` + `/delete` — deleting
  the task definition doesn't stop the process it already launched) instead of
  `Start-Process` — a genuinely independent process tree, immune to the launcher's own job.
  See `infra/scripts/dev-up.ps1`'s `Start-Detached` function.
- **Tailwind v4 custom breakpoints (`@theme { --breakpoint-3xl: ... }`) don't reliably sort
  by width against the built-in ones** — a `3xl:`/`4xl:` rule can lose the CSS cascade to
  the built-in `2xl:` rule even on a viewport far past both, because the custom breakpoint's
  `@media` block can end up earlier in the generated stylesheet than `2xl:`'s regardless of
  actual pixel width (confirmed by inspecting the compiled CSS — redefining the full
  sm→2xl chain alongside the custom ones didn't fix the ordering either). Workaround used
  on the sign-in page and the AI Policy pages: skip Tailwind breakpoint variants entirely
  for anything that needs to keep growing past a laptop screen (e.g. up to a 32" external
  monitor) — use `w-[clamp(min,mid+Nvw,max)]`-style arbitrary values instead. One utility
  class, no `@media` ordering to get wrong, and it scales continuously rather than in
  visible steps. `lg:`/`xl:` (fully below the built-in `2xl`) are still fine to use normally.

## Frontend UI patterns worth knowing before adding another one

- **AWS-console-style contextual info panel** (`components/policy/info-panel.tsx`,
  `lib/policy-info-panel.ts`) — a collapsible right rail on `/policy/new` that swaps its
  "What is this section / Why it matters / Adaptation" copy to match whichever wizard
  step is on screen. Content is plain TS data keyed by step id, not fetched from the
  backend or hardcoded per-component — same "catalog as code" precedent as
  `questions.py`/`authz`'s permission matrix. If more pages want this pattern, generalize
  `PolicyInfoPanel` rather than copy-pasting it — it's already just `{stepId, collapsed,
  onToggleCollapsed}` and a content lookup, not policy-specific in shape.
- **Fluid `clamp()`-based page layout, not Tailwind breakpoints**, on the sign-in page and
  both AI Policy pages — see the Tailwind gotcha above for why. When a page needs a
  side-by-side panel (like the one above), give the main column `min-w-0 flex-1` inside a
  `flex` row so it can shrink below its own `clamp()` preference when the panel is open,
  instead of overflowing.

## Roles: who can do what

Two independent axes, OR'd per action (see `authz/service.py::_PERMISSIONS` for the
authoritative source) — a system `admin`/`super_admin` can always do everything below
regardless of business role, since every rule has an `{admin, super_admin}` fallback
clause. Business role only matters for a `system_role="user"` account.

| Action | `govern` | `assure` | `operator` |
|---|---|---|---|
| View policy, tools catalog, training, dashboard | ✅ | ✅ | ✅ |
| Create/edit an AI policy draft | ✅ | ✅ | ❌ |
| **Approve** a policy draft (make it active) | ✅ | ❌ | ❌ |
| Request a tool/feature/extension | ✅ | ✅ | ✅ |
| Approve/reject a tool request; manage the catalog | ✅ | ✅ | ❌ |
| Raise an escalation (anonymous — see below) | ✅ | ✅ | ✅ |
| View current/resolved escalations (`escalations.view`) | ✅ | ✅ | ✅ |
| Manage escalations (respond/resolve) | ✅ | ✅ | ❌ |
| Manage training content | ✅ | ✅ | ❌ |
| **Connect a GitHub App** (`codescan.connect`) | ❌ | ✅ | ❌ |
| Trigger/view a code scan (`codescan.run`/`.view`) | ✅ | ✅ | ✅ |

**Admin-only regardless of business role** (`system_role` must be `admin`/`super_admin` —
no business role passes these on its own): manage SSO connection, manage users, manage
branding.

`codescan.connect` is the one deliberate exception to this app's usual "manage" shape
(`{govern, assure}`) — it's `assure`-only, not `govern`, a Milestone 13 product decision,
not an oversight. `codescan.run`/`.view` are open to every role for now ("segregation
later," also Milestone 13). The break-glass super-admin (`system_role=super_admin`) can
do everything, including the admin-only rows, regardless of its own `business_role`.

## Module map

`identity/` (SSO via Jackson + mock-saml, SCIM webhook, session cookies, break-glass
super-admin login) · `authz/` (the one permission matrix) · `branding/` (org config +
license status) · `licensing/` (RS256 license validation) · `ai_gateway/`
(vendor-agnostic LLM chokepoint via LiteLLM) · `policy/` (AI policy builder, docxtpl
generation, draft/active/archived lifecycle) · `tools/` (approved AI tools catalog +
request/approval workflow with AI precheck) · `escalations/` (free-text incident
reports, **anonymous** — no reporter is ever stored — routes to govern/assure) ·
`notifications/` (mock/live email, audit trail) ·
`training/` (shared training catalog + per-org completion tracking) · `dashboard/`
(single aggregation endpoint composing every other module's service layer) ·
`codescan/` (Milestone 13 — GitHub-connected repo scanning: Semgrep/Bandit/Gitleaks/
Trivy, deduplicated findings, PDF report, dashboard summary + history).

## Where to look for more

- `apps/api/tests/` — one file per module, service-layer tests. Zero route-level
  (`TestClient` against the real app) tests exist outside `test_license_gate.py` and
  `test_branding.py`'s one regression test — a known gap, not an oversight.
- Every module's own docstrings explain non-obvious decisions inline — read the
  `service.py` and `models.py` docstrings before assuming a design is arbitrary.
