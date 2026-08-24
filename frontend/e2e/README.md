# PixQuery E2E tests (Playwright)

`frontend/e2e/` contains a real, end-to-end Playwright suite. It runs against
the **actual running app** — no mocked network layer, no fake Mongo/RabbitMQ/
Weaviate. Every request goes through the real FastAPI backend to the real
infra containers.

## Prerequisites

1. Infra containers running (persistent named containers, don't recreate them):
   ```bash
   docker start pixquery-mongodb pixquery-rabbitmq pixquery-weaviate
   # or, first time: docker compose -f docker-compose.infra.yml up -d
   ```
2. Backend running natively on port 8000:
   ```bash
   cd backend
   uv run uvicorn api_main:app --port 8000
   ```
   (Set `SECRET_KEY` in your environment/`.env` — required for JWT signing.)
3. Frontend dev server running natively on port 3000:
   ```bash
   cd frontend
   npm start
   ```
4. Playwright browsers installed (one-time):
   ```bash
   cd frontend
   npx playwright install chromium
   ```
   On a minimal Linux host without the usual browser shared libs
   (`libnspr4`/`libnss3`, etc.) and without root, `--with-deps` will fail.
   Fetch just the missing `.so` files without `apt install`:
   ```bash
   mkdir -p /tmp/pw-libs && cd /tmp/pw-libs
   apt-get download libnspr4 libnss3
   for f in *.deb; do dpkg-deb -x "$f" .; done
   export LD_LIBRARY_PATH=/tmp/pw-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
   ```
   Export that `LD_LIBRARY_PATH` in whatever shell runs `npm run test:e2e`.

## Running the suite

```bash
cd frontend
npm run test:e2e
```

Override the frontend URL with `PIXQUERY_BASE_URL` if it's not on
`http://localhost:3000`. Config lives in `frontend/playwright.config.js`.

## What's covered

- `e2e/auth.spec.js` — register, duplicate-username rejection, wrong-password
  rejection, logout, session persistence across reload.
- `e2e/workspaces.spec.js` — create/open/delete a workspace, scan-button
  gating when no pipeline is attached, list filtering.
- `e2e/pipelines.spec.js` — create a pipeline, nav from Search to Pipelines.
- `e2e/search.spec.js` — keyword/semantic search hitting the live `/search`
  endpoint, workspace-scoped search.
- `e2e/jobs.spec.js` — Jobs/stats view against the live `/stats` endpoints.

Each test registers its own unique user (`e2e/helpers.js: uniqueUsername`) so
runs are independent and safe to repeat against the same live MongoDB without
manual cleanup between runs. Tests that create workspaces/pipelines leave
those documents in Mongo (deletion is only exercised where the flow itself
tests delete) — this is a persistent dev database, not a disposable
container, so keep that in mind when running repeatedly.

## Notes / known gaps

- No sample images are ingested by this suite, so result-content assertions
  in `search.spec.js` are limited to "the request succeeds and returns a
  list" rather than specific matches. A future pass could seed a workspace
  with a couple of fixture images and wait for the worker pipeline to
  process them before asserting on visible results.
