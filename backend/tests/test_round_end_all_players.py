"""The round only ends naturally once every non-describer *player* has
guessed correctly — not just one per team. Regression coverage."""

from __future__ import annotations

from app.corpus.schema import Corpus
from app.rooms.room import Room


async def _start_team_room_with_3_players(corpus: Corpus) -> Room:
    room = Room("AAA111", corpus=corpus)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.add_player("Pat")
    # Put Mira and Pat on the same non-describer team so the old rule
    # (one-per-team) would have ended the round on Mira's correct guess.
    await room.update_settings({"team_mode": "teams"})
    [team_a] = await room.randomize_teams(team_count=1) or []  # not used
    return room


async def test_round_continues_when_one_team_mate_guesses_in_teams_mode(
    sample_corpus_en: Corpus,
) -> None:
    """In team mode with 3 players (1 describer + 2 on the same team),
    a single correct guess from one team-mate should NOT end the round —
    the other team-mate still has to get it.
    """
    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    p_mira, _ = await room.add_player("Mira")
    p_pat, _ = await room.add_player("Pat")
    await room.update_settings({"team_mode": "teams"})
    # Build two teams: [Alex], [Mira, Pat]. Alex describes, the others guess.
    teams = await room.randomize_teams(team_count=2)
    # Move players manually so we control who's where.
    await room.set_player_team(p_alex.id, teams[0].id)
    await room.set_player_team(p_mira.id, teams[1].id)
    await room.set_player_team(p_pat.id, teams[1].id)
    await room.start_game()

    # Force Alex to be the describer (rotation may have picked someone else).
    # The easiest way: keep cycling until Alex is up.
    safety = 0
    while room.current_describer_id != p_alex.id and safety < 6:
        safety += 1
        describer = room.current_describer_id
        assert describer is not None
        await room.pick_cell(describer, room.board.theme_ids[0], 1)
        await room.force_end_round()
    assert room.current_describer_id == p_alex.id

    await room.pick_cell(p_alex.id, room.board.theme_ids[0], 1)
    word = room.current_round.word_text

    await room.submit_guess(p_mira.id, word)
    # Mira scored for her team — but Pat still hasn't guessed.
    # The round must stay active under the new "all non-describer players"
    # rule.
    assert room.state == "round", "round ended too early — Pat still hasn't guessed"

    await room.submit_guess(p_pat.id, word)
    # Now everyone has it → round ends, board returns.
    assert room.state == "board"
