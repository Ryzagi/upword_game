# 06 — UI Screens

ASCII wireframes and component breakdowns for every screen. These are
suggestions for layout, not pixel mockups — the dev or a designer should
iterate them.

Convention:

- `[ Button ]` is a button.
- `< text >` is an input.
- `▒` is a disabled/used state.
- `※` marks something only visible to a subset of users (host, describer, etc.).

## 1 — Main menu (`/`)

```
┌──────────────────────────────────────────────────────────────┐
│  Word Describer                                       [EN ▾] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│           ┌───────────────────────────────────────┐          │
│           │  Nickname:  < Alex                  > │          │
│           │                                       │          │
│           │  [    Create new room    ]            │          │
│           │  ─────────────  or  ─────────────     │          │
│           │  Room code:  < ___-___ >  [ Join ]    │          │
│           └───────────────────────────────────────┘          │
│                                                              │
│                  [ Rules ]     [ Settings ]                  │
└──────────────────────────────────────────────────────────────┘
```

**Components:** `LanguageSwitcher`, `NicknameInput`, `CreateRoomButton`,
`JoinRoomForm`, `RulesModalTrigger`, `SettingsModalTrigger`.

**Behaviour:**
- Nickname persists in `localStorage`; defaults to last used.
- "Create room" → `POST /api/rooms` → redirect to `/r/{code}`.
- "Join" → `POST /api/rooms/{code}/join` → redirect to `/r/{code}`.
- Errors render inline below the form.

## 2 — Lobby (`/r/{code}`)

```
┌──────────────────────────────────────────────────────────────┐
│  Room K7P2RM   [Copy link]                          [EN ▾]   │
│                                                  [Rules] [⚙] │
├──────────────────────────────────────────────────────────────┤
│  Players (4)                  │  Settings                    │
│  ┌─────────────────────────┐  │  ┌─────────────────────────┐ │
│  │ • Alex     [Host]       │  │  │ Mode:                   │ │
│  │ • Mira                  │  │  │   ( ) Time              │ │
│  │ • Pat                   │  │  │   (•) Attempts          │ │
│  │ • Sam                   │  │  │                         │ │
│  └─────────────────────────┘  │  │ Attempts/round:         │ │
│                               │  │   ( )5  (•)7  ( )10     │ │
│  Teams                        │  │   ( )Custom < 8 >       │ │
│  ┌─────────────────────────┐  │  │                         │ │
│  │ Team Red (2)            │  │  │ Time/round: ▒           │ │
│  │   Alex, Mira            │  │  │   30 60 90 120 ∞        │ │
│  │   [Rename] ※host        │  │  │                         │ │
│  │                         │  │  │   ※settings host-only   │ │
│  │ Team Blue (1)           │  │  └─────────────────────────┘ │
│  │   Pat                   │  │                              │
│  │                         │  │  [Join Team Red]             │
│  │ (no team) Sam           │  │  [Join Team Blue]            │
│  │                         │  │  [+ Add team]   ※host        │
│  │ [Randomize teams] ※host │  │                              │
│  └─────────────────────────┘  │                              │
├───────────────────────────────┴──────────────────────────────┤
│              [        Start game       ] ※host               │
└──────────────────────────────────────────────────────────────┘
```

**Components:** `RoomHeader` (code + copy + lang + rules + settings),
`PlayerList`, `TeamList`, `JoinTeamButtons`, `RandomizeButton`, `SettingsPanel`,
`StartGameButton`.

**Behaviour:**
- The host badge floats on the longest-connected player; updates if host
  disconnects.
- Non-host players see Settings as read-only.
- Player drag-and-drop between teams is a host-only affordance in v1.5;
  click-to-join the only mechanism in v1.
- "Start game" disabled unless ≥2 teams each with ≥1 player and ≥3 players
  total.

## 3 — Settings modal

Two tabs.

### 3a Preferences

```
┌─ Settings ───────────────────────────── [×] ─┐
│  [ Preferences ] [ Accessibility ]           │
│ ─────────────────────────────────────────── │
│  Language:    ( EN )  ( RU )                 │
│  Theme:       ( Light )  ( Dark )  ( Auto )  │
│  Sound FX:    [✓]                            │
└──────────────────────────────────────────────┘
```

### 3b Accessibility

```
┌─ Settings ───────────────────────────── [×] ─┐
│  [ Preferences ] [ Accessibility ]           │
│ ─────────────────────────────────────────── │
│  Font size:       ( - ) [ A ] ( + )          │
│  High contrast:   [ ]                        │
│  Reduced motion:  [✓]  (auto-detected)       │
│  Dyslexia font:   [ ]                        │
└──────────────────────────────────────────────┘
```

All choices apply instantly and persist in `localStorage`. They are
per-browser, not per-room or per-player.

## 4 — Rules modal

A single scrollable column with localised markdown. Sections:

1. The basics — describer vs guessers, teams.
2. The board — themes and difficulties.
3. Game modes — time vs attempts, with the penalty explained.
4. Scoring — base, decay, describer reward, concede behaviour.
5. Translation bar and reactions.
6. Tips for describing well.

Maintained as a localised markdown string per language; rendered with
`react-markdown`.

## 5 — Game board (`/r/{code}/play`, state=board)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Round 4   ·   Describer: Pat                              [Concede] │
├────────────┬─────────────────────────────────────────────────────────┤
│ Scoreboard │              Pick a theme & difficulty                  │
│            │  ┌───────┬──────┬──────┬──────┬──────┬──────┐           │
│ Red  720   │  │       │ 100  │ 200  │ 300  │ 400  │ 500  │           │
│  Alex      │  ├───────┼──────┼──────┼──────┼──────┼──────┤           │
│  Mira      │  │ Sport │ ▒▒▒  │ 200  │ 300  │ 400  │ 500  │           │
│            │  ├───────┼──────┼──────┼──────┼──────┼──────┤           │
│ Blue 380   │  │ Nature│ 100  │ 200  │ ▒▒▒  │ 400  │ 500  │           │
│  Pat       │  ├───────┼──────┼──────┼──────┼──────┼──────┤           │
│            │  │ Tech  │ 100  │ 200  │ 300  │ 400  │ ▒▒▒  │           │
│ Green  90  │  ├───────┼──────┼──────┼──────┼──────┼──────┤           │
│  Sam       │  │ Films │ 100  │ 200  │ 300  │ ▒▒▒  │ 500  │           │
│            │  └───────┴──────┴──────┴──────┴──────┴──────┘           │
│            │                                                         │
│            │  ※ Cells are clickable for Pat only                     │
└────────────┴─────────────────────────────────────────────────────────┘
```

**Components:** `Scoreboard` (left rail), `BoardGrid` (centre), `RoundHeader`.

**Behaviour:**
- Describer-only: cells are buttons. On hover, show difficulty as a tooltip.
- Non-describer view: cells render but are not clickable; copy says "Pat is
  picking…".
- After the game ends, the board becomes read-only and a "Play again" button
  surfaces in the header for the host.

## 6 — Active round (`/r/{code}/play`, state=round)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Sport · 300            ⏱ 00:42         Describer: Pat   [Concede]※ │
├────────────┬────────────────────────────────────────────────────────┤
│ Scoreboard │   Describer text  (live)                               │
│            │   ┌──────────────────────────────────────────────────┐ │
│ Red  720   │   │ a sport played on ice with brooms and stones …   │ │
│            │   │                                                  │ │
│ Blue 380   │   │ (※ Pat is typing — guessers see this live)       │ │
│            │   └──────────────────────────────────────────────────┘ │
│ Green  90  │                                                        │
│            │   ※for guessers ────────────────────────────────       │
│            │   Your guess:  < ______________________ > [Guess]      │
│            │   Free attempts: 4   |   Penalty: -0                   │
│            │                                                        │
│            │   [👍 2]  [👎 0]                                       │
│            │                                                        │
│            │   ─────────  Translate  ─────────                      │
│            │   From [EN▾]  To [RU▾]                                 │
│            │   < curling                                  >         │
│            │   [Translate]   →  кёрлинг                             │
│            │   [Copy]  [Paste to guess]                             │
└────────────┴────────────────────────────────────────────────────────┘
```

**Variants:**
- The describer sees their own input as an editable text area, with the
  secret word displayed in a small private banner at the top: `Your word:
  curling — hint: An ice sport using brooms and heavy round stones.` Guessers
  do not see this banner.
- The countdown is hidden in attempts mode (replaced with `Mode: Attempts`).
- A small "✓ correct!" badge appears next to a player's row in the
  scoreboard the moment they guess right.
- If the player has already guessed correctly, the guess input is replaced
  with a "Waiting for others…" line.

**Components:** `LiveTranscript`, `GuessForm`, `AttemptsBadge`, `ReactionBar`,
`TranslateBar`, `RoundHeader`, `Scoreboard`.

## 7 — Round summary modal

```
┌─ Round 4 results ──────────────────────── [×] ─┐
│  Word:  curling                                 │
│  Hint:  An ice sport with brooms and stones     │
│                                                 │
│  Describer Pat  (Blue)        +150              │
│                                                 │
│  Correct order:                                 │
│   1.  Red    Alex      +300                     │
│   2.  Green  Sam       +240                     │
│                                                 │
│  Attempts used:                                 │
│   Alex 1 free   ·   Sam 3 free   ·   Mira 5 free, 2 paid (-20) │
│                                                 │
│             [  Next round  ]                    │
└─────────────────────────────────────────────────┘
```

**Behaviour:**
- Auto-displayed at round end, dismissable.
- "Next round" only enabled for the next describer; otherwise it counts down
  3 seconds and auto-advances.

## 8 — End-of-game screen

Full-screen takeover.

```
┌──────────────────────────────────────────────────┐
│                  Game over                       │
│                                                  │
│   1.  Red     1240                               │
│   2.  Blue    1020                               │
│   3.  Green    580                               │
│                                                  │
│   [ Play again ]※host        [ Back to lobby ]    │
└──────────────────────────────────────────────────┘
```

## Component inventory (frontend)

- `LanguageSwitcher`
- `NicknameInput`
- `CreateRoomButton`, `JoinRoomForm`
- `RoomHeader`, `CopyLinkButton`
- `PlayerList`, `TeamList`, `TeamCard`
- `JoinTeamButton`, `RandomizeButton`
- `SettingsPanel` (lobby), `SettingsModal` (preferences + a11y)
- `RulesModal`
- `StartGameButton`
- `Scoreboard`, `ScoreRow`
- `BoardGrid`, `BoardCell`
- `RoundHeader`, `ConcedeButton`, `Countdown`
- `LiveTranscript`, `DescriberInput`
- `GuessForm`, `AttemptsBadge`, `PenaltyBadge`
- `ReactionBar`
- `TranslateBar`
- `RoundSummaryModal`
- `EndOfGameScreen`
- `Toast` (for error events)

## Visual conventions

- One accent colour from the team palette per team, used consistently across
  scoreboard, badge, and player chips.
- Live-updating values get a brief flash animation; respect
  `prefers-reduced-motion`.
- All modal triggers are reachable via keyboard, with `Esc` closing them.
- Focus rings visible and high-contrast.
