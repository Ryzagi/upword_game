# 01 — Implementation Plan

Phased build plan with explicit acceptance criteria. Each phase is independently
demoable; do not start phase N+1 until phase N's acceptance criteria are met.

Time estimates are person-days for one engineer working full time, assuming the
specs in `03`–`07` are already read.

## Phase 0 — Foundation (1–2 days)

Set up the skeleton so feature work in later phases doesn't get blocked on tooling.

**Backend**
- Scaffold `backend/` with `pyproject.toml`, FastAPI, uvicorn, pydantic v2.
- `app/main.py` exposes `GET /healthz` returning `{"ok": true}`.
- Ruff + Black + isort configured; `pytest` configured with one passing test.
- CORS middleware permits the Vite dev origin only.

**Frontend**
- Scaffold `frontend/` with Vite (`react-ts` template), Tailwind, ESLint, Prettier.
- React Router with `/` (main menu placeholder) and `/r/:code` (lobby placeholder).
- Vitest configured with one passing test.
- Zustand installed but unused so far.

**Corpus**
- `data/words.sample.en.json` and `data/words.sample.ru.json` seeded with at
  least 3 themes × 5 difficulty tiers each (see `05-words-corpus.md`).
- Backend loads the corpus at startup and exposes `GET /api/corpus/themes`
  returning theme metadata (no words yet).

**Dev experience**
- Root `Makefile` (or `package.json` script + `uv` task) with `make dev` that
  runs backend on `:8000` and frontend on `:5173` concurrently.
- A single `README.md` at root explaining how to run locally.

**CI (minimal)**
- GitHub Actions workflow that runs backend lint + tests and frontend lint +
  tests on every push. No deploy yet.

**Acceptance**
- `make dev` boots both servers without errors.
- `GET http://localhost:8000/healthz` returns 200.
- Opening `http://localhost:5173/` renders the placeholder main menu.
- `GET /api/corpus/themes` returns the EN themes loaded from JSON.
- CI passes on the seed commit.

## Phase 1 — Rooms, presence, WebSocket plumbing (3–4 days)

The minimum viable network layer: people can create a room, share a link,
join, and see each other.

**Backend**
- `RoomManager`: in-process dict of `code → Room`, with per-room `asyncio.Lock`.
- Room codes: 6-char base32, collision-checked.
- `POST /api/rooms` → `{code, hostPlayerId}`.
- `POST /api/rooms/{code}/join` body `{nickname}` → `{playerId, token}`. Token
  is a random opaque string used to authenticate the WS connection.
- `WS /ws/rooms/{code}?token=...` → upgrades, registers connection.
- Heartbeat: server pings every 20s, drops connections silent for 60s.
- `lobby/state` event broadcast on every roster change.

**Frontend**
- Main menu: "Create room" button, "Join with code" form.
- Room URL pattern: `/r/{code}`; the page reads code from URL, joins (issues
  nickname), then connects WS.
- `playerId` + `token` persisted in `localStorage` keyed by room code so a
  refresh reconnects rather than creates a new player.
- Lobby placeholder lists connected players (no teams yet).
- Nickname edit inline; `lobby/rename` event over WS.

**Acceptance**
- Two browsers (or browser + private window) on the same machine can join the
  same room and see each other's nicknames live.
- Closing a tab removes the player from the list within ~60 s.
- Refreshing a tab restores the same player identity.

## Phase 2 — Lobby: teams, settings, rules, i18n shell (3–4 days)

The pre-game flow becomes fully usable.

**Teams**
- Team data model on server (`Team{id, name, color, playerIds[]}`).
- "Solo" mode: every player is auto-placed in a 1-person team named after them.
- "Teams" mode: host can drag players between teams, rename teams, add/remove
  teams. Players can self-join via "Join team" button.
- "Randomize teams" action distributes players evenly into N teams (host picks
  N, default 2).

**Game settings (host only)**
- Mode picker: `time` vs `attempts`.
- Time-mode value: 30 / 60 / 90 / 120 / unlimited.
- Attempts-mode value: 5 / 7 / 10 / custom integer.
- Settings broadcast as part of `lobby/state`.

**Rules modal**
- Static markdown content rendered as a modal; localised.

**Settings modal**
- Tabs: Preferences (language switcher, light/dark theme) + Accessibility
  (font size, high-contrast palette, reduced-motion toggle).
- All choices persisted in `localStorage` per browser, not per room.

**i18n**
- `react-i18next` configured with `en` + `ru` namespaces.
- All strings introduced so far moved out of components into `locales/en/common.json`
  and `locales/ru/common.json`.
- Language switcher in Settings → Preferences with `en` and `ru` options.
- Browser language detection on first load, then user override wins.

**Acceptance**
- Host can configure teams + game mode; non-host players see the changes live.
- Self-join team works; randomize-teams produces a roughly even split.
- Switching to Russian translates every visible string in menu / lobby /
  rules / settings.
- Accessibility toggles take effect without reload.

## Phase 3 — Game start, theme board, describer rotation (2–3 days)

Players can enter a game and the board renders, but no live describing yet.

**Backend**
- Room state machine: `LOBBY → BOARD → ROUND → BOARD → … → ENDED`.
- `game/start` (host only) transitions `LOBBY → BOARD`.
- Describer rotation: round-robin through teams' players. Implementation in
  `04-game-rules-and-scoring.md`.
- `round/pick_cell` from the current describer: server picks a random unused
  word matching the chosen `(theme, difficulty)` and stores it on the round.
- Server emits `round/started` with theme + score visible to everyone, plus a
  separate `describer/word` event sent **only** to the describer's connection.

**Frontend**
- Theme × difficulty matrix: rows = themes, columns = difficulty 1..5 with
  score values 100..500 (configurable later).
- Used cells visibly disabled.
- Sidebar: teams + scores + indicator of who is the current describer.
- Non-describers see "Waiting for {describer} to pick a category…".

**Acceptance**
- Host clicks "Start game"; all clients transition to the board.
- Current describer can click an unused cell and only they see the word.
- Other players see the round screen header but not the word.
- Describer rotation advances correctly after each round (which still ends
  instantly with no scoring in this phase).

## Phase 4 — The round: live description, guessing, scoring (5–7 days)

The core loop. Largest phase; allow buffer for tuning.

**Live description**
- Describer's text input streams keystrokes via WebSocket: client throttles at
  100 ms, sends the **full current string** each tick.
- Server fans out `describer/text` to all non-describer clients in the room.
- Guesser view renders the live text in a read-only area; describer sees their
  own input as normal.

**Guess submission**
- Guess input: enter to submit. Server normalises both guess and target
  (lowercase, strip diacritics, strip punctuation, collapse internal
  whitespace) and compares.
- Correct guess: emit `guess/correct` to everyone; award scoring per
  `04-game-rules-and-scoring.md`. The guesser remains in the round but cannot
  submit more guesses for this word.
- Wrong guess: emit `guess/wrong` only to the submitter (and `guess/penalty` if
  the penalty path triggered).

**Mode mechanics**
- **Time mode**: server-authoritative round timer (`asyncio.create_task` + a
  monotonic deadline). Clients render a synced countdown by subtracting server
  `now()` from `endsAt`. No per-player attempt cap.
- **Attempts mode**: per-player free-attempts counter. On exhaustion, further
  guesses cost the guesser's team –10 points each, applied immediately on
  submit, regardless of correctness.
- Balance is allowed to go negative.

**Round termination conditions**
- Describer concedes (button) → round ends, describer scores 0, no team scores.
- Round timer expires (time mode) → round ends, scores already credited stay.
- Every non-describer team has at least one correct guess → round ends early.
- Host "force end round" (safety) → round ends, scores credited stay.
- Attempts-mode safety timer (5 min default) → forced round end.

**End-of-round**
- Reveal the word.
- Show summary: who guessed correctly, in what order, points awarded per team,
  describer reward, balance deltas.
- Advance describer; transition `ROUND → BOARD`.

**End-of-game**
- Optional: when all cells used, transition `BOARD → ENDED`, show final
  scoreboard, offer "Play again" which resets the board and rotates the first
  describer.

**Acceptance**
- A round is fully playable end to end in both modes with at least three
  players.
- Decay math matches the worked examples in `04-game-rules-and-scoring.md`.
- Concede yields zero scores everywhere.
- Refreshing a tab mid-round restores the player's view (live text, remaining
  attempts, current scoreboard).

## Phase 5 — Reactions and translation bar (2–3 days)

**Reactions**
- Per-player like and dislike for the current describer. Toggle behaviour: a
  second click un-reacts. Mutual exclusion: liking removes a prior dislike.
- Aggregated counter visible to everyone in real time.
- Reactions reset between rounds. No score impact in v1.

**Translation bar**
- Component in the round view: input field, source-language picker, target
  picker, "Translate" button.
- `POST /api/translate` proxies MyMemory; response cached in-memory by
  `(src, dst, normalised_text)` with a soft 1-hour TTL.
- "Copy" button copies result to clipboard.
- "Paste to guess" button writes the result into the guess input field
  (without auto-submitting).

**Acceptance**
- Reactions tally is consistent across all clients within ~200 ms.
- Translating "hello" en→ru returns "привет" (or similar) and copy / paste
  flows both work.
- Translation works while the round is active without interrupting the
  describer's stream.

## Phase 6 — Polish, accessibility, tests (3–4 days)

- Keyboard navigation through the lobby and board (tab order, focus rings).
- ARIA labels for live regions (describer text uses `aria-live="polite"`).
- `prefers-reduced-motion` respected (no autoplay animations, no parallax).
- Empty-state and error-state copy for every screen.
- Reconnect during a round: server sends a `room/snapshot` on reconnect with
  game state, current round state, and player's private state (word if
  describer, attempts left if guesser).
- Test coverage targets: 100 % on the scoring module, room state machine, and
  guess normaliser. >60 % overall backend. Smoke tests in frontend for the
  three main screens.
- One Playwright happy-path script that drives two browsers through a full
  game (optional).

**Acceptance**
- Lighthouse accessibility score >90 on each main screen.
- All backend unit tests pass; `pytest -q` runs in <5 s.

## Phase 7 — Deployment (1–2 days)

- `backend/Dockerfile` builds a slim Python image running uvicorn.
- `frontend/Dockerfile` multi-stage: Node build → nginx static serve.
- `docker-compose.yml` for a local prod-like run, including an nginx reverse
  proxy in front that handles WS upgrades and serves static assets.
- Deployment doc with one canonical target (recommended: a single VPS via
  Caddy or Docker Compose; or Fly.io which handles WSS natively).
- HTTPS + WSS terminated at the proxy; HTTP redirects to HTTPS.
- Environment-driven config: `CORS_ORIGINS`, `TRANSLATION_API_BASE`,
  `LOG_LEVEL`.

**Acceptance**
- Deploying to staging and playing a full game with two real browsers across
  the internet works end to end.

## Future (post-v1, not scheduled)

These are deliberately out of scope for v1 but worth tracking so the data
models don't paint us into a corner.

- **Hints**: surface the `hint` field from the corpus on demand, with a points
  cost.
- **Reaction-driven scoring**: dislike streak penalty for the describer, or
  like streak bonus.
- **Paid translation taps**: charge the guesser's balance per translation call.
- **Accounts**: optional sign-in so nicknames and avatars persist.
- **More languages**: pipeline for community-submitted word packs.
- **Spectator mode**: late joiners view but don't play.
- **Game history**: persisted finals stored in SQLite, viewable later.
- **Custom word packs**: hosts upload their own JSON in lobby.
- **Secret-word filter**: auto-mask the secret word if the describer types it
  in their stream.

## Sequencing notes

- The corpus shape (`05`) is a Phase 0 commitment — changing it later is
  painful because it cascades into the round word-selection logic.
- The WebSocket message catalogue (`03`) is a Phase 1 commitment. Adding new
  events later is cheap; renaming existing ones is expensive once the
  frontend has them wired in.
- The scoring formulas (`04`) are a Phase 4 commitment, but worth a sign-off
  before Phase 0 so the data model has the right fields.
