# Testing

This file says exactly what is tested, with which tool, and what is **not** tested yet. Numbers come from
the local run on 2026-11-10 (Windows 11, Python 3.14 venv, PostgreSQL 16.2 throwaway cluster, Node 24).
CI runs the same suites on Ubuntu with Python 3.12, Node 22 and a `postgres:16` service.

## Commands

```bash
cd backend && pytest --cov=app                  # 88 tests, needs PostgreSQL (see README → Testing)
cd backend && ruff check . && ruff format --check .
cd frontend && npm test -- --coverage           # 46 tests
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Results

| Suite | Location | Tests | Result |
|---|---|---|---|
| Backend API integration (auth, accounts, inventory, provisioning, costs) | `backend/tests/test_{auth,accounts,inventory,provisioning,costs}.py` | 50 | ✅ passed |
| Backend RBAC (generated role × endpoint matrix + targeted cases) | `backend/tests/test_rbac_matrix.py`, `test_rbac_users.py` | 22 | ✅ passed |
| Backend unit (crypto, redaction, config, HCL escaping, adapters, runner, seed) | `backend/tests/test_security_units.py` | 16 | ✅ passed |
| **Backend total** | | **88** | ✅ **88 passed, 91% line coverage** |
| Frontend unit (formatters, API client) | `frontend/src/lib/format.test.ts`, `src/api/client.test.ts` | 12 | ✅ passed |
| Frontend components | `frontend/src/components/ui/ui.test.tsx` | 12 | ✅ passed |
| Frontend pages (component integration) | `frontend/src/pages/pages.test.tsx` | 22 | ✅ passed |
| **Frontend total** | | **46** | ✅ **46 passed, 77% statement coverage** |

## Coverage by testing type

Status key: **Automated** = in the suites above and in CI · **Partial** = some aspects automated · **Manual** = documented procedure · **Not done** = not implemented (yet) · **N/A** = not applicable, with the reason.

| Type | Status | How / where |
|---|---|---|
| Unit | Automated | `test_security_units.py`, `format.test.ts`, `client.test.ts` |
| Component | Automated | `ui.test.tsx` (React Testing Library) |
| Integration (API + DB) | Automated | FastAPI `TestClient` against real PostgreSQL with Alembic-migrated schema |
| Component integration | Automated | `pages.test.tsx`: whole pages with React Query, router and auth; API module mocked |
| System integration (real cloud SDKs) | Not done | Real AWS/Azure/GCP adapters are untested; the missing-SDK path is tested |
| System / E2E (API journeys) | Automated | `test_full_plan_confirm_apply_workflow`, `test_decommission_workflow`, sync → inventory → dashboard tests |
| E2E (browser) | Not done | Real-browser screenshots were captured with Playwright + Edge, but there is no Playwright test-suite |
| Smoke | Partial | `GET /api/v1/health` is tested; there is no post-deploy smoke script |
| Sanity / regression | Automated | The full suites run on every push and PR (CI) |
| API | Automated | All 52 operations are reachable in tests; the RBAC matrix hits every permission-protected route |
| Boundary value / equivalence partitioning | Partial | Parametrised invalid template params, account ids, credentials, budget limits (negative, scope conflict) |
| Negative | Automated | Bad logins, expired/forged tokens, wrong confirmation token/name, replay, expiry, 404/409/422 envelopes |
| Security (authz) | Automated | Every role × every protected endpoint; unauthenticated → 401 everywhere |
| Security (secrets) | Automated | Credentials absent from responses, stored ciphertext and audit details; log redaction; key rotation |
| Contract | Partial | OpenAPI title asserted; frontend types are hand-written mirrors of the Pydantic schemas (no generated client / schema diff) |
| Configuration | Automated | `test_settings_guards` (production secret guards, Postgres-only URL, CSV parsing); runner mode selection |
| Migration | Automated | Every test session runs `alembic downgrade base` + `upgrade head` |
| Static analysis | Automated | Ruff (incl. bandit-derived `S` rules), ESLint, `tsc --strict` |
| SAST | Partial | Ruff `S` (flake8-bandit) rules in CI; no separate CodeQL/Bandit job |
| SCA | Partial | Dependabot configured (pip, npm, actions, docker); no `pip-audit`/`npm audit` gate |
| DAST | Not done | No ZAP scan |
| Vulnerability scanning (images) | Not done | Images not built in CI |
| Pen testing | N/A | Requires an independent tester; out of scope for a portfolio project |
| Load / stress / spike / soak / scalability | Not done | No Locust/k6 scripts yet |
| Volume | Not done | Largest dataset tested is the seeded demo (~30 resources) |
| Frontend performance | Partial | `vite build` output is checked manually: largest chunk is Recharts (≈116 kB gzip); no Lighthouse CI |
| Accessibility | Partial | RTL queries by role/label (labelled inputs, dialog, tables with captions, progressbar ARIA); no axe scan |
| Visual regression | Not done | Screenshots in `docs/screenshots/` are documentation, not baselines |
| Cross-browser / responsive | Manual | Layout built with responsive Tailwind breakpoints; screenshots captured in Edge only |
| Cross-platform | Partial | Developed on Windows; CI runs on Ubuntu |
| Mutation | Not done | |
| Chaos | N/A | Single-node compose stack; no resilience targets defined |
| A/B | N/A | No product experimentation |
| Localization | N/A | English-only UI |
| Compliance | N/A | No regulatory scope; see SECURITY.md for security practices |
| Usability / UAT | Manual | Checklist below |
| OAT | Manual | Checklist below |

## UAT checklist (manual, against the seeded demo)

- [ ] Sign in as admin, operator and viewer (`*@cloudorbit.dev` / `CloudOrbit!2026`, local only) and confirm the navigation and buttons differ by role
- [ ] Connect a new AWS account (mock), validate it, sync it, and see it in the inventory and dashboard
- [ ] Plan an S3 bucket, try to apply with a wrong name (button stays disabled), confirm correctly, and see the resource in the inventory and the action in the audit log
- [ ] Create a budget below current spend and see the cost alerts appear
- [ ] Acknowledge and resolve an operational alert
- [ ] Change your password and sign in again

## OAT checklist (manual)

- [ ] `docker compose up -d --build`: `api` becomes healthy and migrations apply on start
- [ ] `GET /api/v1/health` returns 200; stop postgres and it returns 503
- [ ] Restart `worker` while a sync is queued; the job completes after restart (`task_acks_late=True`)
- [ ] Back up with `pg_dump`, restore into a fresh volume, and the app works
- [ ] `alembic downgrade -1` then `alembic upgrade head` succeeds on a populated database
- [ ] Rotate `CREDENTIALS_ENCRYPTION_KEYS` (prepend a new key) and existing accounts still validate
