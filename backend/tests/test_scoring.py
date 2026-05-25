from app.game.scoring import describer_reward, points_for_team_position

# ---- points_for_team_position ----


def test_first_team_gets_full_score() -> None:
    assert points_for_team_position(200, position=1, decay=0.8) == 200
    assert points_for_team_position(500, position=1, decay=0.8) == 500


def test_doc_worked_example_s200() -> None:
    # From docs/04: S=200 → 200, 160, 128, 102, 81
    assert points_for_team_position(200, 1, 0.8) == 200
    assert points_for_team_position(200, 2, 0.8) == 160
    assert points_for_team_position(200, 3, 0.8) == 128
    assert points_for_team_position(200, 4, 0.8) == 102
    assert points_for_team_position(200, 5, 0.8) == 81


def test_doc_worked_example_s500() -> None:
    # From docs/04: S=500 → 500, 400, 320, 256, 204
    assert points_for_team_position(500, 1, 0.8) == 500
    assert points_for_team_position(500, 2, 0.8) == 400
    assert points_for_team_position(500, 3, 0.8) == 320
    assert points_for_team_position(500, 4, 0.8) == 256
    assert points_for_team_position(500, 5, 0.8) == 204


def test_zero_or_invalid_position_returns_zero() -> None:
    assert points_for_team_position(200, 0, 0.8) == 0
    assert points_for_team_position(200, -1, 0.8) == 0


# ---- describer_reward ----


def test_describer_reward_zero_with_no_correct_teams() -> None:
    assert describer_reward(200, correct_non_describer_team_count=0) == 0


def test_describer_reward_zero_when_conceded() -> None:
    assert describer_reward(200, correct_non_describer_team_count=3, conceded=True) == 0


def test_describer_reward_doc_example_s200() -> None:
    # From docs/04 worked example with S=200:
    # k=0 → 0,  k=1 → 100,  k=2 → 120,  k=3 → 140,  k=5 → 180,  k=10 → 200 (capped)
    assert describer_reward(200, correct_non_describer_team_count=0) == 0
    assert describer_reward(200, correct_non_describer_team_count=1) == 100
    assert describer_reward(200, correct_non_describer_team_count=2) == 120
    assert describer_reward(200, correct_non_describer_team_count=3) == 140
    assert describer_reward(200, correct_non_describer_team_count=5) == 180
    assert describer_reward(200, correct_non_describer_team_count=10) == 200


def test_describer_reward_capped_at_base_score() -> None:
    # k large enough that the un-capped formula exceeds S
    raw = 100 + 20 * (49)  # k=50 → 1080
    assert raw > 200
    assert describer_reward(200, correct_non_describer_team_count=50) == 200


def test_describer_reward_uses_custom_pcts() -> None:
    # base_pct=1.0, bonus_pct=0.0, k=4 → full S, no bonus
    assert (
        describer_reward(
            300,
            correct_non_describer_team_count=4,
            base_pct=1.0,
            bonus_pct=0.0,
        )
        == 300
    )
