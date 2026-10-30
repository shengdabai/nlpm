---
name: product-advising
description: "Rule catalog P01–P32 for advising AI-built products: readiness gates, security, reliability, front-end, repo hygiene, release. Used by the advisor agent behind /nlpm:advise."
version: 0.1.0
user-invocable: false
---

# Product Advising Rules（给 AI 做出来的产品提建议与需求）

> Scope: this catalog is the fork maintainer's layer on top of nlpm. nlpm's R01–R50 score the *natural-language artifacts* (skills, agents, commands, CLAUDE.md). P01–P32 look at the *product repository itself* — code, config, tests, deploy files — and turn what they find into a prioritized list of requirements a maintainer can paste into an issue tracker or a PRD. They do not replace a security audit; every finding must cite a file and line.

## 1. Severity

| Level | Meaning | Examples |
|---|---|---|
| P0 | Money, other people's data, or credentials are exposed, or a safety check fails open | unauthenticated write endpoint; secret in git; webhook returns 200 when its secret is missing |
| P1 | The core path breaks, the work is falsely "done", or a release step is unsafe | `test.skip` on the main flow; rate limit kept in an in-process Map; migrations with no recovery point |
| P2 | Quality and hygiene that a second person would hit within a day | 390 px horizontal overflow; unpinned CDN; session files committed |
| P3 | Advice; take it when the next iteration touches that area | blocking web fonts; pipeline author email not linked to GitHub |

A rule's default level is listed in its row. Raise a level when the product is already public or takes payment; lower it when the project is explicitly single-user and offline. Say which adjustment you applied.

## 2. Verification layers

Every requirement names one layer so the next session knows how to prove it:

| Layer | Use for |
|---|---|
| unit | pure functions, validators, state machines |
| integration | API route + database, webhook handler with a recorded payload |
| e2e | a user path in a real browser (Playwright, 3 viewports: 1440 / 768 / 390) |
| manual | things a human must look at: generated media, copy, pricing pages |
| real-dependency | a real webhook delivery, a real OAuth round trip, a real database |

## 3. The catalog

Columns: **Check** = what to look for. **How** = concrete commands or file patterns. **Requirement** = the sentence to put in the issue. **Acceptance** = what proves it done.

### 3.1 Gates and evidence (from the three-gate ladder: self-use → others → paid)

| ID | Level | Check | How | Requirement | Acceptance |
|---|---|---|---|---|---|
| P01 | P1 | Gate 1 evidence exists before anything else is added | `.omc/usage-log.md` has ≥ 3 dated entries (date / how it was done before / how now / what it saved) | "Use the product yourself three times and record each use before adding features." | file exists with ≥ 3 entries; each entry names a real task |
| P02 | P2 | Login or payment code exists without gate-2 evidence | grep for `auth`, `session`, `stripe`, `paypal`, `checkout`, `license` in src; look for one named non-owner user in README / docs / usage log | "Freeze login and payment work until one person who is not the maintainer completes the core task and gives one concrete piece of feedback." | a dated note naming the user source and the feedback |
| P03 | P3 | A real Won't list | README / PRD / docs has a scope or "not doing" section | "Write three things this product will not do in this version." | section present with ≥ 3 items |
| P04 | P2 | First users are named | README / PRD says where the first 10 users come from and quotes the first outreach message | "State the source of the first 10 users and paste the first recruiting message." | both present |

### 3.2 Security

| ID | Level | Check | How | Requirement | Acceptance |
|---|---|---|---|---|---|
| P05 | P0 | Write endpoints with no authentication, or server-side code using a service-role / admin key on a public route | grep API routes, edge functions, workers for `service_role`, `SUPABASE_SERVICE`, `adminAuth`, and for handlers of POST/PUT/DELETE with no auth check in the first 30 lines | "Every write endpoint verifies the caller before touching data; service-role keys never run on a route a browser can reach." | integration test: request without credentials → 401/403 |
| P06 | P0 | Ownership check on cross-user records (IDOR) | queries by `id` / `itemId` / `orderId` with no `ownerId` / `userId` predicate | "Every query that reads or writes a user-owned record includes the owner in the predicate." | integration test: user A requests user B's record → 403/404 |
| P07 | P0 | Secrets or demo keys in the tree or history | `gitleaks detect` (with history when it is a git repo); regex `AIza[0-9A-Za-z_-]{35}`, `sk-[A-Za-z0-9]{20,}`, `DEMO_KEY`, `xoxb-`, `ghp_` | "Revoke and rotate the key, then remove it from history; keep secrets in the platform secret store." | gitleaks 0 findings; rotation recorded |
| P08 | P0 | `.env*` tracked by git | `git ls-files` filtered for `.env` names | "Untrack `.env*`, add it to `.gitignore`, rotate every value inside." | untracked and ignored |
| P09 | P0 | Secrets in config files instead of the secret store | `wrangler.toml` `[vars]`, `vercel.json` `env`, `app.yaml` containing `KEY`, `SECRET`, `TOKEN` values | "Move each value to `wrangler secret put` / the platform's encrypted variables." | no plaintext value in config |
| P10 | P0 | Fail-open when configuration is missing | webhook handler returns 200 when its signing secret is unset; edge session check lets requests through when `SESSION_SECRET` is undefined; database missing → mock data served in production | "Missing configuration returns 500 and logs once; it never pretends success." | integration test with the variable removed → 500 |
| P11 | P1 | Rate limiting held in process memory | `new Map()` / object keyed by IP in a limiter; no Upstash / D1 / KV / Redis | "Rate limits live in shared storage so they survive restarts and multiple instances." | integration test across two instances or after restart |
| P12 | P1 | Public bind or public admin surface | `0.0.0.0` in docker-compose / dev servers meant for localhost; routes `/admin`, `/debug` without auth; database ports exposed | "Bind to localhost or put the surface behind authentication and an IP allow list." | port scan or config review |
| P13 | P1 | Sensitive fields in logs | `console.log` / `print` / `logger` lines containing `token`, `secret`, `password`, `apiKey`, `authorization`, full request headers | "Log through one redaction helper; tokens never appear in logs or AI tool output." | grep returns 0 |
| P14 | P1 | Debug and error exposure | `DEBUG=True`, `app.debug`, `NODE_ENV` not forced to production, `Access-Control-Allow-Origin: *` together with credentials, stack traces returned to the client | "Production disables debug, restricts CORS to named origins, and returns a generic error body." | response review on the deployed URL |
| P15 | P1 | AI agent inside the product with broad permissions | `permissionMode: bypass`, `--yolo`, `danger-full-access`, `allowedTools: *`; agent can delete, send, or move money with no human approval or audit table | "The agent has its own identity, is read-only by default, needs a human approval for delete / send, has zero transfer permission, and writes an audit row per action." | config review + one recorded interception |

### 3.3 Reliability and data

| ID | Level | Check | How | Requirement | Acceptance |
|---|---|---|---|---|---|
| P16 | P1 | Check-then-write without atomicity | read → branch → insert for grants, credits, order creation; no unique constraint or transaction | "Make the operation idempotent with a unique constraint or a transaction / compare-and-swap." | concurrent test: two identical requests → one effect |
| P17 | P1 | State in `globalThis` or module scope on serverless | `globalThis.` assignments holding counters, caches of user data, snapshots | "Persist state to a table or KV; module scope is a cache at most." | restart test |
| P18 | P1 | Migrations without a recovery point or rollback note | `migrations/` or `drizzle/` exists; no README / runbook line on snapshot or Time Travel and rollback | "Before each production migration record a recovery point and the command to roll back." | runbook line + one rehearsal |
| P19 | P1 | Dependency hygiene | lockfile missing or untracked; versions `*` / `latest`; non-official registry in lockfile `resolved`; remote install scripts piped straight into a shell in Dockerfile / CI; `pull_request_target` using secrets | "Commit the lockfile, pin versions, install only from the official registry, replace remote-script installs with download → checksum → run." | `git ls-files` shows lockfile; audit of `resolved` hosts |
| P20 | P1 | Known-vulnerable dependencies or framework behind its security patch | `npm audit --omit=dev --audit-level=high` / `pnpm audit --prod` / `pip-audit`; framework version vs its latest security release | "Upgrade to the fixed version; where impossible, document the compensating control and an expiry date." | audit high = 0 or documented exception |

### 3.4 Front-end and experience

| ID | Level | Check | How | Requirement | Acceptance |
|---|---|---|---|---|---|
| P21 | P2 | Horizontal overflow on phones; touch targets under 32 px | Playwright at 390 px: `document.documentElement.scrollWidth > innerWidth`; buttons / links with computed height < 32 px | "No horizontal page overflow at 390 px; interactive targets are at least 32 px tall." | e2e screenshot at 1440 / 768 / 390 with cache-buster |
| P22 | P2 | Unpinned third-party CDN | `cdn.tailwindcss.com` without version, `unpkg.com/<pkg>` or `jsdelivr` without `@x.y.z`, `@latest` | "Pin every CDN URL to an exact version at least two weeks old." | grep returns only versioned URLs |
| P23 | P3 | Render-blocking fonts and scripts | Google Fonts stylesheet link without `media="print" onload` or preload; large sync `<script>` in `<head>` | "Load web fonts and non-critical scripts without blocking first paint." | Lighthouse / PageSpeed first contentful paint improves |
| P24 | P2 | No `/health` or version marker on a server project | routes list; deploy smoke script | "Expose `/health` returning 200 with build identifier and no secrets." | curl after deploy |

### 3.5 Repository hygiene and delivery truth

| ID | Level | Check | How | Requirement | Acceptance |
|---|---|---|---|---|---|
| P25 | P1 | False completion markers | grep `TODO`, `FIXME`, `test.skip`, `.only(`, `NotImplemented`, `throw new Error("not implemented")`, placeholder returns | "Implement or remove each marker; a marker in a shipped path blocks release." | grep returns 0 in changed files |
| P26 | P1 | Tests that cannot fail | test files with no assertion; mocks that return the asserted value; test suite absent for the core path | "Each core path has at least one test that fails when the behavior is broken." | mutation spot-check: break the code, test goes red |
| P27 | P2 | Session and sync debris committed | `.omc/state`, `.claude/settings.local.json`, `*.local.md`, iCloud duplicates (`name 2/`, `.git 2`), `.DS_Store`, `node_modules` | "Untrack debris, add ignore rules; on iCloud-synced folders keep repos in `*.nosync` directories with a symlink." | `git ls-files` clean |
| P28 | P2 | Machine-specific or internal literals | absolute paths `/Users/`, `/Volumes/`; internal hostnames, ports, chat or channel ids hard-coded; raise to P0 if the literal is a credential | "Move machine-specific values to configuration; internal identifiers come from environment variables." | grep returns 0 |
| P29 | P3 | Automated commits with an author email GitHub cannot link | launchd / cron / CI commit scripts with no `GIT_AUTHOR_EMAIL`; commits by `codex@local.invalid`, `user@host.local` | "Automated committers set `GIT_AUTHOR_EMAIL` and `GIT_COMMITTER_EMAIL` to an address verified on the GitHub account (the noreply address is fine)." | `git log --format=%ae` shows only linked addresses |
| P30 | P1 | Deploy target not explicit | bare `vercel link` / `vercel --prod` with directory name ≠ project name; `wrangler deploy` without `--env`; D1 `migrations apply` on a project whose migrations table was hand-managed | "Deploy commands name project, scope and environment explicitly; migration strategy is written down per project." | deploy script review |
| P31 | P1 | Release without a pre-launch check or rollback path | no launch-check report for the current HEAD; README / runbook has no "how to roll back in 10 minutes" | "Run the ten-category pre-launch check on this HEAD and write the rollback steps before opening traffic." | report file dated after the last commit |
| P32 | P2 | README does not say how to run, test, and what it does not do | missing run command, test command, limits section | "README answers: how to run it, how to test it, what it will not do." | three sections present |

## 4. How to read a product before applying the catalog

1. **Profile it in five lines** — entry type (new product / fix / new capability / small change), capabilities present (server, login, payment, database, public delivery), risk level by what this change touches, current gate (1 self-use / 2 others / 3 paid), deployment target. Do not infer "commercial" from architecture; look for pricing pages, payment code, or a stated goal.
2. **Inventory** — language and package manager, lockfile, test runner, deploy files (`vercel.json`, `wrangler.toml`, `Dockerfile`, `fly.toml`, `.github/workflows`), migrations, `.omc/usage-log.md`, NL artifacts (hand them to the nlpm scorer separately).
3. **Run only the rows the profile makes relevant.** A static single-page tool skips 3.2 server rows and 3.3 entirely; say so under "Not applicable".
4. **Cite evidence** as `path:line` or a command and its first output line. A finding without evidence is a question for the maintainer, not a requirement.
5. **Write the requirement sentence so it can be pasted unchanged** into an issue: one behavior, one acceptance criterion, one verification layer.

## 5. Output contract

The advisor returns Markdown in this order. Default language is Chinese; switch to English when `.claude/nlpm.local.md` sets `advise.lang: en`.

```
# <project> — 建议与需求（nlpm advise · <YYYY-MM-DD> · HEAD <short-sha or n/a>）

## 一句话判断
<one sentence: what the product is, which gate it is at, the single most important next move>

## 画像
入口 / 能力勾选 / 风险级别 / 当前门 / 部署目标 — five short lines

## 发现清单
| 级别 | 规则 | 证据 | 影响 | 需求 | 验收标准 | 验证层 |
(P0 first; at most 15 rows; group the rest under "其余观察")

## 可直接贴进 issue 的需求
### [P0] <title>
背景 / 需求 / 验收标准 / 验证层 / 相关规则
(one block per P0 and P1)

## 本轮不做
<Won't items with the reason, so the list does not grow>

## 不适用
<rules skipped because the profile excludes them>

## NL 工件分数
<table from the nlpm scorer, or "no NL artifacts found">
```

Keep the whole report under 250 lines. When nothing reaches P0 or P1, say so in the first line instead of inflating P2 items.
