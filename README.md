# Word Describer — Multiplayer Party Game

A browser-based multiplayer party game in the spirit of Alias / Jeopardy. One
player ("the describer") types a description of a hidden word in real time;
everyone else races to guess it. Players compete as solo entries or in teams,
choose categories from a Jeopardy-style theme × difficulty board, and play
either by round-timer or by guess-attempts.

Phase 0 of the plan (foundation: backend + frontend scaffolding, corpus
loader, dev runner, CI) is in place. Continue with Phase 1 in the
implementation plan.

## Quick start

```
make dev       # runs FastAPI on :8000 and Vite on :5173
make test      # runs backend + frontend tests
make lint      # runs ruff + ESLint + tsc --noEmit
make format    # auto-format with ruff + prettier
make clean     # remove .venv and node_modules
```

Visit `http://localhost:5173/` for the placeholder main menu. The Vite dev
server proxies `/api`, `/healthz`, and `/ws` to the FastAPI backend, so the
two halves talk to each other natively without CORS gymnastics in dev.

Direct backend probes during development:

```
curl http://localhost:8000/healthz
curl http://localhost:8000/api/corpus/themes?language=en
```

## Stack at a glance

- **Frontend:** React 18 + TypeScript + Vite + Tailwind, Zustand for state,
  `react-i18next` for localisation, native WebSocket for live play.
- **Backend:** Python 3.12 + FastAPI + uvicorn + pydantic v2, WebSocket for
  real-time room state and keystroke streaming.
- **Data:** JSON word corpus per language (`data/words.*.json`). No database
  in v1 — rooms live in process memory.
- **Translation:** MyMemory free API, proxied through the backend with an
  in-memory cache. Pluggable so we can swap to LibreTranslate or a paid
  provider later.
- **Reverse proxy:** nginx in front of FastAPI in production (serves the
  built frontend, proxies `/api` and `/ws` with WebSocket upgrade). Starter
  config in [`deploy/nginx.conf`](deploy/nginx.conf).

## Read these in order

1. [`docs/01-implementation-plan.md`](docs/01-implementation-plan.md) —
   phased build plan with acceptance criteria. The primary deliverable.
2. [`docs/02-architecture.md`](docs/02-architecture.md) — tech choices,
   repository layout, deployment shape.
3. [`docs/03-data-models-and-api.md`](docs/03-data-models-and-api.md) —
   entities, HTTP routes, WebSocket message catalogue.
4. [`docs/04-game-rules-and-scoring.md`](docs/04-game-rules-and-scoring.md) —
   round flow, scoring formulas with worked examples, edge cases.
5. [`docs/05-words-corpus.md`](docs/05-words-corpus.md) — corpus JSON
   schema, content guidelines, language strategy.
6. [`docs/06-ui-screens.md`](docs/06-ui-screens.md) — ASCII wireframes for
   every screen.
7. [`docs/07-i18n.md`](docs/07-i18n.md) — translation strategy for UI and
   word packs.

Sample word corpora in [`data/`](data/) demonstrate the JSON shape and seed
content for English and Russian.

## Open decisions called out in the docs

The plan makes opinionated defaults so you can react to a concrete proposal,
but the following are flagged for explicit confirmation before Phase 0:

- **Persistence model** — default is ephemeral in-memory rooms; if you want
  reconnect across server restarts or game history we add SQLite (see
  Architecture §"Persistence").
- **Translation provider** — default is MyMemory free tier; alternatives in
  Architecture §"Translation".
- **Per-player vs per-team decay** — default is per-team (one decay step per
  team's first correct guess). See Game Rules §"Scoring".
- **Describer reward formula** — default is `0.5 × S + 0.1 × S` per additional
  correct team, capped at `S`. See Game Rules §"Describer reward".
