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
- **A fresh `pip install -r requirements.txt` (e.g. a `--no-cache` Docker build) is the
  only way to catch a real dependency conflict** — an already-populated native venv
  tolerates version mismatches a clean resolve won't. Bit this project twice: the old
  `httpx<0.28.0` constraint (`litellm==1.56.4`'s own pin, since relaxed — no longer an
  issue as of the current `litellm` pin) and, worse, a genuine `ResolutionImpossible`
  between `litellm`'s hard pins on `click`/`importlib-metadata` and `semgrep`'s
  transitive pins on those same packages, only found via a `--no-cache` build of
  `infra/Dockerfile.api`, never via the native venv (see `apps/api/requirements.txt`'s
  own pin comments for the exact versions and reasoning). When bumping any pinned
  dependency in `requirements.txt`, verify via `docker compose --profile codescan build
  --no-cache api worker`, not just `pytest` in the native venv.
- **`setuptools` must stay `<81`** — Semgrep's own tracing dependency
  (`opentelemetry-instrumentation-requests`) still imports the legacy `pkg_resources`
  module, removed from `setuptools` 81+.
- **Suppressing a confirmed Code Scan false positive is tool-specific, and the wrong
  mechanism silently does nothing** (all three below were caught by actually re-running
  the tool after adding a suppression, not by assuming the standard-looking comment
  worked): **gitleaks** auto-loads a `.gitleaks.toml` at the scanned repo's root (no
  `--config` flag needed — see `.gitleaks.toml`'s own comment) for a broad
  pattern-based allowlist, or an inline `# gitleaks:allow` comment on the exact flagged
  line for one-off cases (e.g. a test fixture's fake PEM string). **semgrep**'s inline
  `# nosemgrep` (bare, or `# nosemgrep: <rule-id>` to target one rule) must go on the
  line semgrep's own JSON output reports as the match's *start* line — for a multi-line
  call this is often not where you'd guess (e.g. the opening `op.execute(` line, or a
  `.render()` call two lines below the `Template(...)` constructor it's really about,
  not the constructor itself). **Trivy** auto-loads a `.trivyignore` at the repo root
  (one check ID per line) for a whole-file/structural check like "Dockerfile has no
  HEALTHCHECK" (`DS-0026`) — its inline `# trivy:ignore:<ID>` comment only works for
  checks tied to one specific instruction, not structural ones; confirmed by testing
  both before picking `.trivyignore`.
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
- **Route-driven tabs, not client-side tab state** — `app/(app)/ai-center/layout.tsx` +
  `components/ui/tabs.tsx` (Milestone 15). Each tab is a real Next.js route segment
  (`/ai-center/tools`, `/ai-center/project`, `/ai-center/vendor-register`), not a
  conditionally-rendered panel — keeps every tab deep-linkable and back-button-correct,
  matching how every other feature in this app (`/policy`, `/escalations`, ...) is its
  own route. `components/ui/tabs.tsx` wraps `@base-ui/react`'s `Tabs` primitive in
  **route-driven mode**: `Tabs.Root value={activeTabFromPathname}` with no
  `onValueChange`, each `Tabs.Tab` rendered as `render={<Link .../>} nativeButton=
  {false}` — base-ui's `Tab` only calls `onValueChange` (a safe no-op when omitted) on
  click, never `preventDefault()`, so real `Link` navigation still fires; the base-ui
  active-tab data attribute is `data-active`, not `data-selected` — check a primitive's
  actual compiled source before styling a `data-[x]:` variant, its attribute names
  aren't consistent across every base-ui component. Adding a fourth tab means adding a
  route segment under `ai-center/` and one entry in `layout.tsx`'s `TABS` array, not
  touching the tab-bar component itself.
- **A moved page gets a redirect stub at its old URL, not a deletion** — `app/(app)/
  tools/page.tsx` is now just `redirect("/ai-center/tools")` (a Server Component; the
  App Router's `redirect()` from `next/navigation`) after AI Tools moved under AI
  Center. Cheap insurance against a saved bookmark/link, and the actual convention to
  follow the next time a route moves rather than a fresh page. **Verifying a `redirect()`
  stub needs a real browser, not `curl`** — Next 16 doesn't always send a bare HTTP 3xx;
  for a request that would otherwise stream, it embeds a `NEXT_REDIRECT;replace;
  <path>;307;` marker into the RSC payload instead, which only a JS-executing client
  acts on. `curl` sees a plain `200 OK` with no `Location` header and looks broken even
  when it isn't — read the response body for the `NEXT_REDIRECT` marker to confirm the
  target, or better, drive a real headless browser.
- **`curl` can't verify any authenticated page's rendered content in this app** — every
  page under `(app)/` is wrapped by `app-shell.tsx`'s `AppShell`, a Client Component
  that renders only a "Loading..." fallback until its own `fetchCurrentUser()` effect
  resolves client-side. The server-rendered HTML `curl` sees is always just that
  fallback, never the actual page content, regardless of auth state — this isn't new or
  a bug, it's true for every existing authenticated page. Confirming real content
  (or a client-side redirect, or a tab click, or dark mode) needs a real browser
  (Playwright/`chromium-cli`), not a `curl`+grep check.
- **A "Request" flow is a routed page, not a `Dialog` popup** (Milestone 18) —
  `app/(app)/ai-center/{tools,project,vendor-register}/request/page.tsx`, one per tab.
  Each is a self-contained multi-step wizard using the shared
  `components/ui/wizard-progress-bar.tsx::WizardProgressBar` (a copy of
  `components/policy/progress-bar.tsx::PolicyProgressBar`, kept as a copy under a
  neutral name rather than a shared import so AI Center doesn't reach into
  `components/policy/`) — same "Step N of M" + prev/next-title-pill look as
  `/policy/new`, but **no server-side draft/autosave**: all step state lives in plain
  React state and the actual `POST` fires once, atomically, on the final step's
  submit — `/policy/new`'s per-step `PATCH` autosave only exists because `Policy` rows
  already have a real draft lifecycle (`current_step`, resumable), which
  `tool_request`/`project_request`/`vendor_request` don't and weren't given one for
  this. A refreshed/abandoned wizard loses progress, same as an abandoned dialog did
  before — not a regression. Shared cross-tab pieces: `lib/tiers.ts` (`TIER_KEYS`/
  `TIER_LABELS`, used by both the Tools and Project wizards plus the existing Tools
  catalog page — all three used to keep their own local copy) and
  `components/vendor/checklist-answer-fieldset.tsx` (extracted from
  `vendor-register/page.tsx`, still used there for the post-approval "Edit Checklist"
  popup — a new `scrollable` prop defaults `true` to preserve that dialog's bounded-
  height scrollbox, while the wizard passes `scrollable={false}` since a wizard step is
  already a full scrollable page, not a fixed-height popup).

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
| Request a vendor (commercial or open-source) | ✅ | ✅ | ✅ |
| Approve/reject a vendor request; edit checklist responses | ✅ | ✅ | ❌ |
| Submit an AI Project request (use-case/workflow) | ✅ | ✅ | ✅ |
| Approve/reject a project request; edit a project | ✅ | ✅ | ❌ |

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
Trivy, deduplicated findings, dashboard summary + history; findings sorted and grouped
critical → high → medium → low everywhere — the API's `list_findings()`, the frontend's
severity filter tags on the scan detail view, and the PDF report's structure, which
matches `Qtower_CodeScan_Phase1_Handoff.md`'s spec: an executive summary, a full
30-item Tier 1 taxonomy table (found yes/no + occurrence count per category), then
findings grouped by severity) · `vendors/` (Milestone 14, part of the in-progress
**AI Center** rebuild — see `AI_Center_Technical_Handoff.md` — commercial + open-source
vendor risk register: a fixed, seeded checklist (`vendor_checklist_item`, no org_id/RLS,
same shared-catalog precedent as `training_module`) scored **deterministically and
synchronously** — no Celery, no `ai_gateway` call, unlike every other request/approval
flow in this app, since the checklist is already structured Y/N data with one
mechanically correct evaluation. Any `must_have` item answered "no" forces
`status="restricted"` regardless of every other answer; `good_to_have`/`optional`
answers produce a weighted score. `vendor_request`/`vendor` follows the exact same
circular-FK migration sequencing and self-approval guard as `tool_request`/
`approved_tool`. **The requester answers the checklist directly on the request** (not
deferred to govern/assure after approval) — `create_vendor_request()` computes
`projected_status`/`overall_score` synchronously at submission via the same
`scoring.score_vendor()` an approved vendor uses, and `approve_vendor_request()` copies
the request's answers into the new `vendor`'s own `vendor_checklist_response` rows and
rescores fresh from them rather than trusting the request's cached projection verbatim.
`govern`/`assure` can still correct an approved vendor's checklist afterward via the
existing edit affordance — the request-time checklist doesn't replace that, it just
means a vendor is no longer created blank) · `projects/` (Milestone 16, the third AI
Center tab — AI use-case/workflow submissions, assessed by AI precheck exactly like
`tools/`: a direct structural copy of `tools/prompts.py`/`tools/tasks.py`, same
skip-if-no-active-policy gate, same never-auto-approve fail-safe JSON parsing, same
Celery-task-only rule, same admin-editable-prompt-with-fallback pattern
(`deployment_config.project_assessment_prompt`, not yet exposed via a Settings UI
section). `project_request`/`project` follows the same circular-FK migration
sequencing and self-approval guard as `tool_request`/`approved_tool`. Linking Tools/
Vendors is **not a hard gate** — a project can submit with zero links — via
`project_tool_link`/`project_vendor_link`: each row is exactly one of a real catalog
reference (`tool_id`/`vendor_id`) or a free-text `other_name` for something not in
inventory (both invariants enforced in `service.py`, not a DB constraint), and exactly
one of `project_id`/`request_id` (a still-pending request's proposed links, or a real
project's links after approval — the schema deviates slightly from the original plan
sketch, which only listed `project_id`, to let a request's links be visible/assessed
before approval exists). `approve_project_request()` copies (not moves) a request's
link rows into new `project_id` rows, same copy-on-approve pattern `vendors/` already
established for checklist responses. The "not registered in inventory" tag is
structural, set at submission time — never inferred by the LLM — though the precheck
prompt is given every linked tool/vendor labeled either way so its explanation can
reference them; a real run showed the model correctly flagging an unregistered link
against the policy's own "no AI tools without governance review" clause).
`approved_tool`/`vendor` both gained real logo support (Milestone 17) — two input
paths, an upload to MinIO or pasting a URL directly. An uploaded logo's `logo_url`
column holds this app's own streaming route (e.g. `/tools/approved/{id}/logo-file`),
not a MinIO/S3 URL — the bucket isn't public and a presigned URL would eventually
expire out from under a catalog card that renders it indefinitely; that streaming GET
route is deliberately the one unauthenticated endpoint on an otherwise session-gated
router, since a cross-origin `<img>` tag (frontend on a different port than the API)
won't carry the httponly session cookie without extra plumbing, and a logo is
non-sensitive branding-adjacent imagery, not data worth gating. Shared validation/key
logic lives in `apps/api/core/media.py` (512KB cap, PNG/JPEG/SVG only, one fixed
extensionless storage key per entity so a re-upload overwrites in place) rather than
duplicated per module. Milestone 18 replaced every AI Center "Request" **popup** with a
dedicated **page** at `/ai-center/{tools,project,vendor-register}/request` — a
multi-step wizard (progress bar, one section per step, Back/Next) matching `/policy/new`
visually, but **purely client-side across steps** (plain React state, one atomic submit
on the final step) rather than `/policy/new`'s server-autosaved-draft model, since
`tool_request`/`project_request`/`vendor_request` have no draft/current-step concept to
autosave into — building one was explicitly out of scope. `tool_request` gained
`data_tiers`/`requires_enterprise_account`, `project_request` gained `data_tiers`
(migration `0018`) per `AI_Center_Technical_Handoff.md`'s "Request forms" section; both
feed into their respective `ai_gateway` precheck prompts, not just stored inertly. The
Vendor Register wizard unifies commercial (15 questions) and open-source (a real
**20-question** set — 6 Must Have / 8 Good to Have / 6 Optional, replacing Milestone
14's 5-item placeholder guess, confirmed via a direct DB check that zero real checklist
responses referenced the old items before deleting them) behind one "Request Vendor"
entry point that picks the type on step 1 and swaps both the question set and the
basic-info field labels ("Website"/"Business justification" vs. "Repository, URL"/
"Intended use case") accordingly. Every Must Have question requires an explicit answer
before the wizard's Step 2 will advance — client-side only, the server-side scoring
rule that an *unanswered* must-have doesn't force `restricted` (only an explicit "no"
does) is deliberately unchanged.

## Where to look for more

- `apps/api/tests/` — one file per module, service-layer tests. Zero route-level
  (`TestClient` against the real app) tests exist outside `test_license_gate.py` and
  `test_branding.py`'s one regression test — a known gap, not an oversight.
- Every module's own docstrings explain non-obvious decisions inline — read the
  `service.py` and `models.py` docstrings before assuming a design is arbitrary.
