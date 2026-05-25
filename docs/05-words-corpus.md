# 05 — Words Corpus

The shape and conventions for the JSON files in `data/`. The backend loads
these at startup; changing the schema later breaks the round-selection logic,
so freeze this in Phase 0.

## File layout

One file per language:

```
data/
├── words.sample.en.json
├── words.sample.ru.json
└── words.<lang>.json        # future
```

The backend chooses the file based on the room's language setting (which
defaults to the host's UI language at room creation time). Switching language
**inside a running game is not supported** — the corpus is loaded once per
room and the board references words by ID.

## Top-level schema

```jsonc
{
  "version": 1,
  "language": "en",
  "themes": [
    {
      "id": "sport",
      "name": "Sport",
      "icon": "trophy",       // optional, frontend may map to an SVG
      "words": [ ... Word objects ... ]
    },
    ...
  ]
}
```

Rules:

- `version` is an integer. Bump if the schema changes; the loader can refuse
  unknown versions.
- `language` is an IETF tag (`en`, `ru`, `de`, `pt-BR`, ...).
- Theme `id`s are short, stable, lowercase, ASCII, no spaces. They are the
  canonical join key across languages — the EN file's `sport` and the RU
  file's `sport` are the same theme, displayed with different `name`s.
- Theme `name` is the localised display string.
- `icon` is optional; if present, must match a key the frontend knows.

## Word object schema

```jsonc
{
  "id": "encryption",
  "text": "encryption",
  "difficulty": 3,
  "hint": "Scrambling information so only the right people can read it.",
  "aliases": ["encrypt"]     // optional; alternate accepted answers
}
```

Rules:

- `id`: stable, ASCII, lowercase, unique within the theme. Used to dedupe in
  the round picker so a word isn't picked twice in a game. Not displayed.
- `text`: the canonical target word/phrase as players will see it after the
  round. Localised — the EN file shows English, the RU file shows Russian.
- `difficulty`: integer 1–5. Maps to the board column with `base_value`
  `[100, 200, 300, 400, 500][difficulty - 1]`.
- `hint`: a short description that does **not** contain or trivially imply
  the target word. Used internally as a fallback if the describer disconnects
  and (later) as a paid hint feature.
- `aliases` (optional): list of strings; if any normalises equal to the
  player's normalised guess, it counts as correct. Useful for stems and
  spelling variants.

## Content guidelines

- Avoid words that contain the target in the hint. "A device used to take
  photographs" is fine for `camera`; "A camera used by photographers" is not.
- Avoid culturally narrow references unless the theme makes them obviously
  relevant.
- Keep difficulty 1 words usable by children and ESL speakers.
- Difficulty 5 should be reasonably hard — obscure but real, multi-syllable,
  or technical-but-not-jargon. Avoid "trivia-buff only" words; the game
  rewards description, not encyclopaedic recall.
- Multi-word targets allowed (`solar eclipse`) but keep them short. Hyphens
  treated as separate words by the normaliser.
- Diacritics in the target are fine; the normaliser strips them on
  comparison. Keep them in `text` so the reveal looks correct.

## Cross-language pairing

Theme IDs are shared across languages, so we can show the same board to a
room playing in either language. **Word IDs are not paired across
languages** — `data/words.sample.en.json#sport.encryption` and a hypothetical
`data/words.sample.ru.json#sport.shifrovanie` are different rows. We do not
attempt true translation pairing; localised packs are independent.

A future "mixed language" mode is out of scope for v1.

## Validation

The loader (`backend/app/corpus/loader.py`) validates:

- `version == 1` (current).
- Theme IDs unique within file.
- Word IDs unique within their theme.
- Each `difficulty ∈ {1,2,3,4,5}`.
- Every `(theme_id, difficulty)` cell has at least one word.
- Hints are not empty and do not contain the target word as a substring
  (after normalisation). Loader fails fast on violations.

Backend test fixture: `tests/data/corpus.test.json` covers each validation
branch.

## Sample files

See [`data/words.sample.en.json`](../data/words.sample.en.json) and
[`data/words.sample.ru.json`](../data/words.sample.ru.json) for working
examples. The samples include three themes (Sport, Nature, Technology) with
all five difficulty tiers — enough to build the board and play several rounds.

For production, target ≥10 words per `(theme, difficulty)` cell so that
games don't exhaust a cell after one or two plays.

## Workflow for adding words later

1. Edit the JSON in a branch.
2. Backend tests will fail loudly if you break the schema.
3. CI runs the validator on every PR.
4. No backend code change needed to add words — restart picks them up.

When the corpus grows past ~5 MB total, switch to splitting by theme into
`data/<lang>/<theme>.json` files. The loader interface stays the same.
