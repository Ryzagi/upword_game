# 03 — Data Models, HTTP API, WebSocket Events

The canonical contract between frontend and backend. Treat the event names and
field names as a freeze point once Phase 1 starts shipping.

## Domain entities

All snake_case in transit. Times are ISO-8601 UTC strings. IDs are opaque
short strings (8–12 chars, base32).

```ts
type RoomCode = string;       // 6 chars, base32, e.g. "K7P2RM"
type PlayerId = string;       // 10 chars
type TeamId = string;         // 8 chars
type RoundId = string;        // 10 chars
type WordId = string;         // from corpus
```

### Player

```ts
{
  id: PlayerId
  nickname: string
  team_id: TeamId | null
  is_host: boolean
  is_connected: boolean
}
```

### Team

```ts
{
  id: TeamId
  name: string
  color: string             // hex, server-chosen from palette
  player_ids: PlayerId[]
  score: number             // total across all rounds, can be negative
}
```

### GameSettings

```ts
{
  mode: "time" | "attempts"
  time_seconds: number | null      // 30 | 60 | 90 | 120 | null (unlimited)
  attempts_per_round: number | null // positive int; null in time mode
  scoring: {
    base_values: [100, 200, 300, 400, 500]
    decay: 0.8                     // multiplier per additional correct team
    penalty_per_attempt: 10
    describer_base_pct: 0.5
    describer_bonus_pct: 0.1
  }
}
```

### Board

```ts
{
  themes: ThemeId[]
  difficulties: [1, 2, 3, 4, 5]
  used: Array<{ theme_id: ThemeId, difficulty: number }>
}
```

### Round

```ts
{
  id: RoundId
  describer_id: PlayerId
  theme_id: ThemeId
  difficulty: number
  base_score: number              // base_values[difficulty - 1]
  word: WordId                    // sent only to describer
  started_at: string
  ends_at: string | null          // set only in time mode
  state: "active" | "ended"
  attempts_used: Record<PlayerId, number>  // free attempts consumed
  paid_attempts: Record<PlayerId, number>
  correct_order: Array<{
    team_id: TeamId
    player_id: PlayerId
    at: string
  }>
  reactions: {
    likes: PlayerId[]
    dislikes: PlayerId[]
  }
}
```

### Room

```ts
{
  code: RoomCode
  state: "lobby" | "board" | "round" | "ended"
  host_id: PlayerId
  players: Player[]
  teams: Team[]
  settings: GameSettings
  board: Board | null              // present from state="board" onwards
  current_round: Round | null      // present only when state="round"
  describer_queue: PlayerId[]      // next describer pops from front
}
```

## HTTP API

All routes are under `/api`. JSON in, JSON out. Errors are
`{"error": {"code": "...", "message": "..."}}` with HTTP 4xx / 5xx.

### Rooms

- `POST /api/rooms`
  - Request: `{ nickname: string, language: "en" | "ru" }`
  - Response: `{ code, host_player_id, token }`
  - Side effect: creates an empty room, places creator as host.

- `POST /api/rooms/{code}/join`
  - Request: `{ nickname: string }`
  - Response: `{ player_id, token }`
  - Errors: `room_not_found`, `room_full`, `nickname_taken`.

- `GET /api/rooms/{code}`
  - Response: lobby-public room snapshot (no in-flight round word).
  - Used for warm-loading the lobby before WS connects.

### Corpus

- `GET /api/corpus/themes?language=en`
  - Response: `{ themes: [{ id, name, icon? }] }`
  - Reads from the loaded corpus for the given language.

### Translation

- `POST /api/translate`
  - Request: `{ text: string, src: string, dst: string }`
  - Response: `{ translated: string, provider: "mymemory" }`
  - Errors: `unsupported_pair`, `upstream_failure`, `rate_limited`.
  - Cached for 1 hour by `(src, dst, normalised(text))`.

### Health

- `GET /healthz` → `{ "ok": true, "version": "..." }`

## WebSocket

One connection per `(player, room)` at:

```
ws://<host>/ws/rooms/{code}?token=<token>
```

The server closes the connection with code 4401 if the token is missing or
invalid, 4404 if the room is gone.

All frames are JSON objects with a `type` discriminator. Inbound events are
`type` strings rooted at the action (`lobby/rename`); outbound events are
state pushes (`lobby/state`, `round/...`).

### Inbound (client → server)

| `type`                      | Payload                                        | Notes                                                  |
| --------------------------- | ---------------------------------------------- | ------------------------------------------------------ |
| `lobby/rename`              | `{ nickname }`                                 | rejected if taken                                      |
| `lobby/team_set`            | `{ player_id, team_id \| null }`               | host-only if changing other players; self always ok    |
| `lobby/team_create`         | `{ name }`                                     | host-only                                              |
| `lobby/team_delete`         | `{ team_id }`                                  | host-only; members move to none                        |
| `lobby/team_rename`         | `{ team_id, name }`                            | host-only                                              |
| `lobby/randomize_teams`     | `{ team_count }`                               | host-only                                              |
| `lobby/settings_set`        | `Partial<GameSettings>`                        | host-only                                              |
| `lobby/start_game`          | `{}`                                           | host-only; requires ≥2 teams with ≥1 player each       |
| `round/pick_cell`           | `{ theme_id, difficulty }`                     | describer-only                                         |
| `describer/text`            | `{ text }`                                     | describer-only; full current string                    |
| `guess/submit`              | `{ text }`                                     | non-describer-only                                     |
| `round/concede`             | `{}`                                           | describer-only                                         |
| `round/force_end`           | `{}`                                           | host-only safety hatch                                 |
| `reaction/toggle`           | `{ kind: "like" \| "dislike" }`                | non-describer-only                                     |
| `game/play_again`           | `{}`                                           | host-only, state=ended                                 |
| `client/pong`               | `{}`                                           | response to server ping                                |

### Outbound (server → client)

Broadcast events go to all players in the room unless noted as "private to X".

| `type`                | Recipients         | Payload                                                                                            |
| --------------------- | ------------------ | -------------------------------------------------------------------------------------------------- |
| `room/snapshot`       | individual         | Full `Room` state on connect / reconnect; if state=round and recipient is describer, includes word |
| `lobby/state`         | all                | `{ players, teams, settings, host_id }`                                                            |
| `lobby/player_joined` | all                | `{ player }`                                                                                       |
| `lobby/player_left`   | all                | `{ player_id }`                                                                                    |
| `game/started`        | all                | `{ board, describer_queue }`                                                                       |
| `board/state`         | all                | `{ board, scoreboard }` after each round                                                           |
| `round/started`       | all                | `{ round_id, describer_id, theme_id, difficulty, base_score, ends_at }`                            |
| `describer/word`      | describer only     | `{ word_text, hint }`                                                                              |
| `describer/text`      | non-describers     | `{ text }`                                                                                         |
| `guess/wrong`         | submitter only     | `{ free_attempts_left, paid_attempts_total, balance_delta }`                                       |
| `guess/correct`       | all                | `{ player_id, team_id, position, points_awarded }`                                                 |
| `guess/penalty`       | submitter only     | `{ amount, new_balance }`                                                                          |
| `reaction/state`      | all                | `{ likes: PlayerId[], dislikes: PlayerId[] }`                                                      |
| `round/ended`         | all                | `{ word_text, hint, results: RoundResults }` (see below)                                           |
| `game/ended`          | all                | `{ final_scores }`                                                                                 |
| `server/ping`         | all                | `{}` (client replies with `client/pong`)                                                           |
| `error`               | individual         | `{ code, message, ref?: string }`                                                                  |

#### `RoundResults` shape

```ts
{
  word_text: string
  hint: string
  describer_id: PlayerId
  describer_points: number
  per_team: Array<{
    team_id: TeamId
    first_player_id: PlayerId | null
    correct_at: string | null
    position: number | null        // 1-indexed among correct teams
    points: number                 // round score for this team
  }>
  per_player_attempts: Array<{
    player_id: PlayerId
    free_used: number
    paid_used: number
    penalty_total: number
  }>
}
```

### Error codes

A flat string set so the client can localise messages:

- `room_not_found`, `room_full`, `nickname_taken`, `nickname_invalid`
- `not_host`, `not_describer`, `not_your_turn`
- `bad_settings`, `bad_team_config`, `cell_already_used`
- `round_not_active`, `already_guessed_correctly`
- `unsupported_pair`, `upstream_failure`, `rate_limited`
- `invalid_payload`

### Connection lifecycle

1. Client `POST /api/rooms/{code}/join` → gets `token`, `player_id`.
2. Client opens WS with that token.
3. Server sends `room/snapshot` to the new connection.
4. Server broadcasts `lobby/player_joined` to everyone else.
5. Ongoing: deltas via the events above.
6. On disconnect: server marks player `is_connected = false` after a 5-second
   grace window (debounces page refreshes), then broadcasts `lobby/state`.
7. Reconnect: same playerId / token; server flips `is_connected = true` and
   replays a `room/snapshot`.

### Rate limits (server-side)

- `describer/text`: at most 30 frames/sec per connection; excess dropped.
- `guess/submit`: at most 5/sec per connection; excess → `error{rate_limited}`.
- `reaction/toggle`: at most 5/sec per connection.
- `lobby/*`: at most 10/sec per connection.

These exist primarily as a defensive measure against buggy clients, not as a
gameplay mechanic.
