"""Phase 4 — Room-level tests for submit_guess, set_describer_text, and
the round-result computations.
"""

from __future__ import annotations

import pytest

from app.corpus.schema import Corpus
from app.models.errors import (
    AlreadyGuessedCorrectlyError,
    DescriberCannotGuessError,
    NotDescriberError,
    RoundNotActiveError,
)
from app.rooms.room import Room


def _other_player_id(room: Room, exclude: str) -> str:
    return next(pid for pid in room.players if pid != exclude)


# --------------------------------------------------------- set_describer_text


async def test_set_describer_text_stores_text(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    await room.set_describer_text(describer, "it's round and used in games")
    assert room.current_round is not None
    assert room.current_round.live_text == "it's round and used in games"


async def test_set_describer_text_truncates_too_long(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    long_text = "x" * 5000
    stored = await room.set_describer_text(describer, long_text)
    assert len(stored) == 2000


async def test_set_describer_text_rejected_for_non_describer(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    other = _other_player_id(room, describer)
    with pytest.raises(NotDescriberError):
        await room.set_describer_text(other, "something")


async def test_set_describer_text_rejected_when_no_round(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    with pytest.raises(RoundNotActiveError):
        await room.set_describer_text(room.current_describer_id or "", "x")


# --------------------------------------------------------- submit_guess basics


async def test_correct_guess_awards_points_and_auto_ends_with_solo_2p(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    assert room.current_round is not None
    word = room.current_round.word_text
    base_score = room.current_round.base_score

    guesser = _other_player_id(room, describer)
    guesser_team_id = room.players[guesser].team_id
    assert guesser_team_id is not None
    initial_guesser_team_score = room.teams[guesser_team_id].score

    result = await room.submit_guess(guesser, word)
    assert result.correct is True
    assert result.team_position == 1
    assert result.team_points == base_score  # first team, full score
    # Round auto-ended because the only non-describer team has scored.
    assert result.round_ended is not None
    assert room.state == "board"
    # Guesser's team gained the full score.
    assert room.teams[guesser_team_id].score == initial_guesser_team_score + base_score


async def test_wrong_guess_doesnt_credit(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    guesser = _other_player_id(room, describer)
    result = await room.submit_guess(guesser, "definitelynotaword")
    assert result.correct is False
    assert result.round_ended is None
    assert room.state == "round"


async def test_describer_cannot_submit_a_guess(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    word = room.current_round.word_text if room.current_round else ""
    with pytest.raises(DescriberCannotGuessError):
        await room.submit_guess(describer, word)


async def test_already_guessed_correctly_blocks_re_submit(
    sample_corpus_en: Corpus,
) -> None:
    # Use 3 players so the round doesn't auto-end after the first correct guess.
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.add_player("Pat")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    assert room.current_round is not None
    word = room.current_round.word_text
    guesser = _other_player_id(room, describer)
    await room.submit_guess(guesser, word)
    # Round still active (one other team hasn't scored yet)
    assert room.state == "round"
    with pytest.raises(AlreadyGuessedCorrectlyError):
        await room.submit_guess(guesser, word)


async def test_empty_guess_is_ignored(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    guesser = _other_player_id(room, describer)
    result = await room.submit_guess(guesser, "   ")
    assert result.empty is True
    # No attempts charged, no broadcast triggered.
    assert room.current_round is not None
    assert guesser not in room.current_round.attempts_used


async def test_normalisation_lets_punctuation_and_case_match(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    assert room.current_round is not None
    word = room.current_round.word_text
    guesser = _other_player_id(room, describer)
    # Submit with weird casing + punctuation + leading/trailing spaces.
    result = await room.submit_guess(guesser, f"  {word.upper()}!?  ")
    assert result.correct is True


# --------------------------------------------------------- attempts mode


async def test_attempts_mode_penalty_kicks_in_after_free_exhausted(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    await room.update_settings({"mode": "attempts", "attempts_per_round": 1})
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    guesser = _other_player_id(room, describer)
    guesser_team_id = room.players[guesser].team_id
    assert guesser_team_id is not None

    # First wrong guess uses the free attempt.
    r1 = await room.submit_guess(guesser, "definitelynotaword")
    assert r1.correct is False
    assert r1.free_attempts_left == 0
    assert r1.penalty_applied == 0
    assert r1.paid_attempts_total == 0

    score_before_paid = room.teams[guesser_team_id].score
    # Second wrong guess: paid attempt, -10.
    r2 = await room.submit_guess(guesser, "stillwrong")
    assert r2.correct is False
    assert r2.penalty_applied == 10
    assert r2.paid_attempts_total == 1
    assert room.teams[guesser_team_id].score == score_before_paid - 10
    assert r2.new_team_score == score_before_paid - 10


async def test_attempts_mode_correct_guess_after_paid_attempt(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.update_settings({"mode": "attempts", "attempts_per_round": 1})
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 3)
    assert room.current_round is not None
    word = room.current_round.word_text
    base_score = room.current_round.base_score
    guesser = _other_player_id(room, describer)
    guesser_team_id = room.players[guesser].team_id
    assert guesser_team_id is not None

    # Burn the free attempt first.
    await room.submit_guess(guesser, "nope")
    score_before = room.teams[guesser_team_id].score
    # Now the correct guess: pay the penalty AND earn the round points.
    result = await room.submit_guess(guesser, word)
    assert result.correct is True
    assert result.penalty_applied == 10
    # Net: lost 10 to penalty, gained base_score for the team's first correct.
    expected = score_before - 10 + base_score
    # Plus describer reward goes to describer's team — but that's separate.
    assert room.teams[guesser_team_id].score == expected


# --------------------------------------------------------- describer reward


async def test_describer_reward_credited_to_describer_team(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    describer_team = room.players[describer].team_id
    assert describer_team is not None
    initial_describer_team_score = room.teams[describer_team].score
    await room.pick_cell(describer, "sport", 3)
    assert room.current_round is not None
    word = room.current_round.word_text
    base_score = room.current_round.base_score  # 300
    guesser = _other_player_id(room, describer)
    await room.submit_guess(guesser, word)
    # k = 1 (one non-describer team scored). reward = floor(300 * 0.5) = 150.
    assert room.teams[describer_team].score == initial_describer_team_score + 150, (
        f"expected +150, base_score={base_score}"
    )


async def test_no_reward_on_concede(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    describer_team = room.players[describer].team_id
    assert describer_team is not None
    score_before = room.teams[describer_team].score
    await room.pick_cell(describer, "sport", 3)
    await room.concede(describer)
    # No reward, score unchanged.
    assert room.teams[describer_team].score == score_before


# --------------------------------------------------------- round results dict


async def test_round_results_dict_populated_with_per_team(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    assert room.current_round is not None
    word = room.current_round.word_text
    guesser = _other_player_id(room, describer)
    result = await room.submit_guess(guesser, word)
    assert result.round_ended is not None
    res = result.round_ended.results
    assert res is not None
    assert "per_team" in res
    assert "per_player_attempts" in res
    assert res["describer_id"] == describer
    assert res["describer_points"] == 50  # base=100, k=1 → floor(100*0.5)=50
    # one row per team
    per_team = res["per_team"]
    assert isinstance(per_team, list) and len(per_team) == 2
    winners = [row for row in per_team if row["position"] == 1]
    assert len(winners) == 1
    assert winners[0]["points"] == 100
    assert winners[0]["first_player_id"] == guesser
