# 02 — Architecture

High-level system shape, technology choices, repository layout, and the
load-bearing decisions you should push back on if you disagree.

## System diagram

```
            ┌──────────────────────────────────────────────────┐
            │                     Browser                      │
            │  ┌────────────────┐    ┌────────────────────────┐│
            │  │ React UI (Vite)│    │ Zustand store          ││
            │  │ - routes       │◀──▶│ - room state           ││
            │  │ - i18n         │    │ - private player state ││
            │  │ - a11y         │    │ - settings (local)     ││
            │  └────────────────┘    └────────────────────────┘│
            │           │ HTTP                │ WebSocket       │
            └───────────┼─────────────────────┼─────────────────┘
                        │                     │
                        ▼                     ▼
            ┌───────────────────────────────────────────────────┐
            │                FastAPI (uvicorn)                  │
            │  ┌──────────┐  ┌────────────┐  ┌───────────────┐  │
            │  │ HTTP API │  │ WS handler │  │ Translation   │  │
            │  │ /api/... │  │ /ws/rooms  │  │ proxy + cache │  │
            │  └────┬─────┘  └─────┬──────┘  └──────┬────────┘  │
            │       └────────┬─────┘                │           │
            │                ▼                      ▼           │
            │       ┌────────────────┐      ┌────────────────┐  │
            │       │ Room manager   │      │ MyMemory API   │  │
            │       │  - rooms[code] │      │ (external)     │  │
            │       │  - per-room    │      └────────────────┘  │
            │       │    lock        │                          │
            │       │  - game FSM    │                          │
            │       └────────┬───────┘                          │
            │                ▼                                  │
            │       ┌────────────────┐                          │
            │       │ Corpus loader  │   data/words.*.json      │
            │       └────────────────┘                          │
            └───────────────────────────────────────────────────┘
```

## Frontend

- **React 18 + TypeScript**. Strict mode on. Function components only.
- **Vite** for dev server and production builds. Native ESM, fast HMR.
- **React Router v6** for `/`, `/r/:code`, `/r/:code/play`.
- **Zustand** for client state — small, hookable, no Provider boilerplate. One
  store per concern (`useRoomStore`, `useSettingsStore`, `useGameStore`).
- **`react-i18next`** for localisation. Loads `locales/{lang}/common.json` at
  app init; lazy-loads extra namespaces if needed later.
- **Tailwind CSS** for styling. Headless UI for accessible primitives (modal,
  tabs, menus).
- **WebSocket**: native `WebSocket`, wrapped in a thin client (`src/ws/client.ts`)
  that handles reconnect with exponential backoff, queueing outbound messages
  while disconnected, and routing inbound events to the right Zustand store.
- **No global form lib** — the inputs are simple enough for controlled
  components.
- **Build/lint**: ESLint with `typescript-eslint` + `react-hooks`, Prettier,
  `tsc --noEmit` on CI.
- **Tests**: Vitest + React Testing Library. Optional Playwright in Phase 6.

## Backend

- **Python 3.12 + FastAPI**. Type-checked with `mypy` (strict on `app/game/`
  and `app/models/`, lenient elsewhere).
- **Uvicorn** as ASGI server. `--workers 1` in dev; in prod we run one worker
  per VM since room state is in-process (see "Persistence and scale").
- **pydantic v2** for all request/response models and WebSocket payloads.
  Outbound events are dumped via `.model_dump(mode="json")`.
- **WebSocket** via FastAPI's built-in `WebSocket` (Starlette). One connection
  per (player, room).
- **Concurrency**: a single asyncio event loop per process. Each room has an
  `asyncio.Lock` to serialise state mutations; broadcasts happen outside the
  lock to avoid head-of-line blocking on a slow client.
- **Translation client**: `httpx.AsyncClient` with a connection pool and a
  small in-memory LRU cache.
- **Logging**: structlog with JSON output in prod, key-value in dev.
- **Lint/format/tests**: ruff + black + isort + pytest + pytest-asyncio.

## Persistence and scale

Default for v1 is **ephemeral, in-memory state**, one process per VM. This is
the right call for a party game where:

- Rooms are short-lived (minutes to hours).
- A shared link is the only authentication.
- Server restarts are infrequent enough that "all current games end" is
  acceptable downtime cost.

Implications:

- We do not horizontally scale by spinning up more backend instances. One
  process owns all rooms.
- Vertical scaling is fine to several hundred concurrent rooms on a single
  small VM. The expensive thing is fan-out of keystroke events, but at 10 Hz
  per active round and ~8 players per room, even 100 active rounds is
  manageable.
- If we outgrow this we add a Redis pub/sub layer and shard rooms by code.
  The room-manager interface is designed to be swappable for this.

**Alternative if you want it:** add SQLite + SQLModel for room persistence
across restarts and post-game history. This is a Phase 1.5 insert, not v1.
Flag in the README if you want it.

## Translation

Default provider is **MyMemory** — free tier, no API key required for low
traffic, returns reasonable quality for common phrases. The implementation
must be behind an interface so we can swap providers without touching the
frontend.

```python
class Translator(Protocol):
    async def translate(self, text: str, src: str, dst: str) -> str: ...
```

Implementations:
- `MyMemoryTranslator` (default)
- `LibreTranslateTranslator` (self-hosted, drops in later if rate limits hurt)
- `NoopTranslator` (test fixture)

The frontend never talks to the translation API directly — it goes through
`POST /api/translate`. This keeps any future API key out of the client, lets
us add per-room rate limits, and lets us cache.

## Repository layout

```
/
├── README.md
├── Makefile
├── docker-compose.yml          (added in Phase 7)
├── .github/workflows/ci.yml
├── docs/                       (this directory)
├── data/
│   ├── words.sample.en.json
│   └── words.sample.ru.json
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile              (added in Phase 7)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             FastAPI app factory
│   │   ├── config.py           pydantic-settings
│   │   ├── api/
│   │   │   ├── rooms.py        HTTP routes
│   │   │   ├── translate.py
│   │   │   └── corpus.py
│   │   ├── ws/
│   │   │   ├── router.py       /ws/rooms/{code}
│   │   │   └── events.py       inbound/outbound schemas
│   │   ├── rooms/
│   │   │   ├── manager.py      RoomManager
│   │   │   └── room.py         Room (FSM)
│   │   ├── game/
│   │   │   ├── state.py        round state + transitions
│   │   │   ├── scoring.py      decay, describer reward, penalties
│   │   │   └── rotation.py     describer rotation
│   │   ├── corpus/
│   │   │   ├── loader.py
│   │   │   └── schema.py       pydantic models for corpus JSON
│   │   ├── translation/
│   │   │   ├── base.py         Translator protocol
│   │   │   ├── mymemory.py
│   │   │   └── cache.py
│   │   └── models/             shared pydantic schemas (Player, Team, ...)
│   └── tests/
│       ├── test_scoring.py
│       ├── test_rotation.py
│       ├── test_room_fsm.py
│       └── test_ws_smoke.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── Dockerfile              (added in Phase 7)
    ├── public/
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── routes/
        │   ├── Index.tsx       main menu
        │   ├── Lobby.tsx
        │   └── Play.tsx        board + round screens
        ├── components/
        │   ├── lobby/
        │   ├── game/
        │   ├── settings/
        │   └── common/
        ├── stores/
        │   ├── useRoomStore.ts
        │   ├── useSettingsStore.ts
        │   └── useGameStore.ts
        ├── api/
        │   ├── http.ts         fetch wrapper
        │   └── rooms.ts
        ├── ws/
        │   ├── client.ts
        │   └── events.ts       typed event union
        ├── i18n/
        │   └── index.ts
        ├── locales/
        │   ├── en/common.json
        │   └── ru/common.json
        ├── lib/
        │   └── normalise.ts    guess + word normalisation
        └── styles/
            └── tailwind.css
```

## Deployment shape

- One container for `backend` (uvicorn + Python). Listens on `:8000`.
- One container for `frontend` (nginx serving the Vite build). Listens on
  `:80` internally.
- One container for `proxy` (Caddy or nginx) terminating TLS, serving the
  static site, and reverse-proxying `/api/` and `/ws/` to the backend with
  WebSocket upgrade enabled.
- Single VM is sufficient. A Fly.io app with a single machine also works.

Why not serverless: WebSockets on serverless platforms either don't work
(Vercel, basic Lambda) or require a managed protocol gateway (AWS API Gateway
WS) which complicates state ownership. Not worth it for v1.

## Key non-obvious decisions

- **Server is authoritative for time.** The client never decides round-end —
  it renders a countdown derived from `endsAt - serverNow`, where `serverNow`
  is sampled from the server on connect and adjusted with a coarse offset.
  Round-end is emitted by the server.
- **Keystrokes go through the server, not peer-to-peer.** Simpler topology,
  needed anyway for late joiners' snapshots, and the bandwidth is trivial.
- **No optimistic guess display.** When a player guesses, the UI shows a
  spinner until the server confirms. This is cheap latency-wise on a LAN-ish
  connection and avoids double-credit edge cases.
- **Reactions are not persisted across rounds in v1.** Counters reset; no
  per-game like total. Easy to add later if we want it.
