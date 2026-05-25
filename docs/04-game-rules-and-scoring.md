# 04 — Game Rules and Scoring

The complete, normative description of how a round plays out and how points
are awarded. Worked examples included for every non-trivial case. If a
disagreement comes up later, this doc wins.

## Round overview

A game is a sequence of **rounds**. Each round has one **describer** (a single
player) and a **target word** drawn from a `(theme, difficulty)` cell of the
Jeopardy-style board. All other players are **guessers**, organised into
**teams**. A solo game is just teams of one.

Within a round:

1. Describer picks an unused cell from the board. Server reveals the word
   privately to the describer and announces the cell publicly.
2. Describer types a free-form description; guessers see the text live as it
   is typed.
3. Guessers submit guesses. The server compares (normalised) guess to
   (normalised) target.
4. Round ends when one of the end conditions fires (see "Round end").
5. Server awards points (see "Scoring").
6. Board updates; the next describer is picked from the rotation queue.

## Describer rotation

A queue of `PlayerId`s is built when the game starts. The default rotation is
**round-robin by team, then by player within team**. Example with teams
`A=[a1,a2]`, `B=[b1]`, `C=[c1,c2,c3]`:

```
a1, b1, c1, a2, [B has none new — skip], c2, [A done — skip], c3, a1, b1, ...
```

In other words: cycle teams; within each team, take the next unused player;
when a team is exhausted, skip it that turn. After every player has been
describer once, the queue resets and continues. Implementation detail in
`backend/app/game/rotation.py`.

This ensures fairness across team sizes without ever giving the same team
two describers in a row when avoidable.

## Round end conditions

A round ends as soon as any of the following becomes true. Whichever fires
first wins; subsequent conditions are no-ops.

1. **Describer concedes** (`round/concede`). Hard stop.
2. **Time mode timer expires** (`now >= ends_at`). Time mode only.
3. **All non-describer teams have at least one correct guess.** Both modes.
4. **Host forces round end** (`round/force_end`). Safety hatch.
5. **Attempts mode safety timer.** 5 minutes after round start, both modes
   (but redundant in time mode unless `time_seconds = unlimited`).

Points already credited from correct guesses **stay** when the round ends.

## Guess validation

Server normalisation, applied to both guess and target before comparison:

1. Trim leading/trailing whitespace.
2. Lowercase using Unicode-aware case folding (`str.casefold()`).
3. Strip diacritics by NFD decomposition and dropping combining marks.
4. Strip punctuation: any `unicode.category` starting with `P`.
5. Collapse internal whitespace to single spaces.

This handles "Soccer!" / "soccer", "café" / "cafe", "Привет, мир" / "привет мир".

Multi-word targets must match the full normalised form. Partial matches do
not count. Future enhancement: optional fuzzy match for difficulty-1 words.

## Attempts (the attempts mode)

Each guesser has `free_attempts_per_round` free guesses for this round
(default 5 / 7 / 10 / custom).

- Each submission consumes one free attempt (whether correct or not), until
  the counter reaches zero.
- Once free attempts are zero, every additional submission **costs the
  guesser's team 10 points immediately**, applied before the correctness
  check. The team balance may go negative.
- A correct submission still pays out per the scoring rules below, even if
  it was a paid attempt. The 10-point cost is **not** refunded.
- After a player has guessed correctly in this round, they cannot submit
  again.

## Time mode

There is a round timer (`time_seconds` from settings) but **no per-player
attempt cap**. Players can keep submitting freely until they guess correctly
or the timer expires. Wrong guesses cost nothing.

`time_seconds = null` ("unlimited") means there is no timer — the round runs
until describer concedes or every team has scored. Use sparingly.

## Scoring

Let `S = base_score = base_values[difficulty - 1]` (default `[100, 200, 300,
400, 500]`).

### Per-team decay (default)

When a team's **first** player guesses correctly, that team is added to the
correct-team queue at position `n` (1-indexed). Points awarded to that team:

```
points_n = floor(S * decay^(n-1))    where decay = 0.8
```

Subsequent correct guesses from members of the **same** team do not award
additional points (the team already scored this round). This is intentional:
it prevents large teams from running away with the score.

Worked examples with `S = 200`:

| Position `n` | Formula        | Points |
| ------------ | -------------- | ------ |
| 1            | floor(200·0.8⁰) | 200    |
| 2            | floor(200·0.8¹) | 160    |
| 3            | floor(200·0.8²) | 128    |
| 4            | floor(200·0.8³) | 102    |
| 5            | floor(200·0.8⁴) | 81     |

With `S = 500`:

| Position `n` | Points |
| ------------ | ------ |
| 1            | 500    |
| 2            | 400    |
| 3            | 320    |
| 4            | 256    |
| 5            | 204    |

> Decision flag: per-team decay is the default. A per-player decay variant is
> possible — every individual correct guess advances `n`, regardless of team.
> This is closer to the literal reading of the original spec but rewards
> larger teams. If you prefer it, switch `scoring.decay_unit` from `"team"` to
> `"player"` in the settings. The data model already supports both.

### Describer reward

Computed at round end. Let `k` = number of distinct correct teams (other than
the describer's own team if it scored).

```
if k == 0 or describer conceded:
    reward = 0
else:
    reward = floor(S * 0.5) + floor(S * 0.1) * (k - 1)
    reward = min(reward, S)
```

The reward is credited to the **describer's team**. Solo: the describer's
1-person team gets it.

Worked examples with `S = 200`:

| Correct teams (`k`) | Reward                       |
| ------------------- | ---------------------------- |
| 0                   | 0                            |
| 1                   | floor(200·0.5) = 100         |
| 2                   | 100 + floor(200·0.1) = 120   |
| 3                   | 100 + 2·20 = 140             |
| 5                   | 100 + 4·20 = 180             |
| 10                  | min(100 + 9·20, 200) = 200   |

This rewards clarity (any guess at all is worth half), gives a bonus for
broad clarity (more teams guess), and caps at the round's base score so the
describer never out-earns the top guesser.

Edit `scoring.describer_base_pct` / `scoring.describer_bonus_pct` if you
disagree with these numbers.

### Penalty accounting

Penalties (`-10` per paid attempt) are applied **immediately on submit** to
the guesser's team balance, independent of correctness. They are tracked
per-player in `paid_attempts` for the round results screen.

### Concede

`round/concede` from the describer ends the round immediately. **No team
scores anything**, even teams that had already guessed correctly in the
round. The reasoning: concede means "this isn't working, give me back the
turn"; awarding partial credit there would discourage conceding when it's the
right call.

> If you disagree: an alternative is to keep already-credited correct guesses
> standing on concede. Easy to switch — see `Room.handle_concede`.

### No-correct-guess case

Time expires (or all-teams-no-progress in attempts mode safety end) with
zero correct teams:

- Every team: 0 points.
- Describer: 0 points.
- Word is still revealed and marked as used on the board.

## Reactions

Each non-describer player can give the current describer **one like or one
dislike per round**, mutually exclusive. Toggling like when dislike is
already set replaces it (and vice versa). Toggling the same kind again
removes it.

Counts are visible to everyone in real time. They have **no score impact in
v1**. Reactions reset at round end.

## End of game

When all `(theme, difficulty)` cells have been used, the game transitions to
`ended` state. The server emits `game/ended` with the final scoreboard. The
host can call `game/play_again` to reset the board (settings persist) and
rotate the starting describer to the next player in the queue.

## Worked round example

Setup:
- Teams: `A=[a1,a2]`, `B=[b1]`, `C=[c1]`. Describer = `a1`.
- Cell: `(technology, 3)` → `S = 300`.
- Mode: attempts, free = 5.

Timeline:
1. `a1` types "scrambling information so only intended recipients can read".
2. `b1` guesses "code" — wrong. Free attempts left: 4. No penalty.
3. `c1` guesses "encryption" — correct. Team C is position 1.
   - Team C: +floor(300·0.8⁰) = +300.
4. `a2` (on describer's team) guesses "ciphering" — wrong. Free 4 → 3.
5. `b1` guesses "encryption" — correct. Team B is position 2.
   - Team B: +floor(300·0.8¹) = +240.
6. Every non-describer team has now guessed → round ends early.

Results:
- Team A (describer's team) describer reward: `k = 2` distinct correct
  non-describer teams → `floor(300·0.5) + floor(300·0.1)*(2-1) = 150 + 30 =
  180`. Team A: +180.
- Team B: +240 (positions: 2).
- Team C: +300 (position: 1).
- `a2` consumed 1 free attempt (no penalty). `b1` consumed 2. `c1` consumed
  1. Everyone within free allotment, so no balance deductions.

Round summary screen shows the per-team table, the per-player attempt usage,
and the revealed word + hint.

## Edge cases checklist

For implementers — make sure these all behave as specified.

- Describer is the only player → server rejects `lobby/start_game`.
- Round ends mid-guess: a guess in flight when `round/ended` fires is
  rejected with `round_not_active`.
- Same player double-clicks Submit: server idempotency on `(round_id,
  player_id, normalised_text)` for a 1s window.
- Player disconnects mid-round as describer → host gets a prompt to "force
  end round". Round continues with no live stream until host acts (or any
  player times out as a safety after 30 s of describer disconnection, server
  emits `round/concede` automatically).
- Player disconnects mid-round as guesser → their `attempts_used` snapshot
  preserved; on reconnect they see remaining attempts and current describer
  text.
- Host disconnects → next-longest-connected player becomes host. Host
  transitions broadcast in `lobby/state`.
- Player guesses the secret word during the round but it's their own team
  and team already scored → guess accepted (`already_guessed_correctly` if
  same player, otherwise the team's correctness flag is already set and the
  guess is informationally correct but awards no further points; the UI shows
  a check). Free attempt is still consumed.
- Settings change while in lobby is allowed; settings change while not in
  lobby is rejected.
- Empty / whitespace-only guess → ignored (does not consume attempt).
