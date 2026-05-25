from app.game.rotation import compute_rotation


def test_solo_rotation_is_just_the_players() -> None:
    rotation = compute_rotation([["a"], ["b"], ["c"]])
    assert rotation == ["a", "b", "c"]


def test_equal_teams_interleave() -> None:
    rotation = compute_rotation([["a1", "a2"], ["b1", "b2"]])
    assert rotation == ["a1", "b1", "a2", "b2"]


def test_uneven_teams_skip_exhausted_teams() -> None:
    # Doc example: A=[a1,a2], B=[b1], C=[c1,c2,c3]
    rotation = compute_rotation([["a1", "a2"], ["b1"], ["c1", "c2", "c3"]])
    assert rotation == ["a1", "b1", "c1", "a2", "c2", "c3"]


def test_single_team_is_player_order() -> None:
    assert compute_rotation([["p1", "p2", "p3"]]) == ["p1", "p2", "p3"]


def test_empty_input() -> None:
    assert compute_rotation([]) == []


def test_empty_teams_are_skipped() -> None:
    rotation = compute_rotation([[], ["x"], [], ["y", "z"]])
    assert rotation == ["x", "y", "z"]


def test_no_duplicates_across_full_rotation() -> None:
    teams = [["a1", "a2", "a3"], ["b1", "b2"], ["c1"]]
    rotation = compute_rotation(teams)
    flat = sum(teams, [])
    assert sorted(rotation) == sorted(flat)
    assert len(rotation) == len(set(rotation))
