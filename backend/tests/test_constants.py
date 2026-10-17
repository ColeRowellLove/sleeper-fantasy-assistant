from sleeper_assistant import constants


def test_the_position_lists_agree() -> None:
    assert constants.FANTASY_POSITIONS == ("QB", "RB", "WR", "TE", "K", "DEF")
    assert constants.FANTASY_POSITIONS[:-1] == constants.PLAYER_POSITIONS
    assert set(constants.FANTASY_POSITIONS) >= constants.FLEX_POSITIONS


def test_game_statuses_and_slots_are_sleepers_words() -> None:
    assert (constants.GAME_PRE, constants.GAME_LIVE, constants.GAME_COMPLETE) == (
        "pre_game",
        "in_game",
        "complete",
    )
    assert constants.EMPTY_SLOT == "0" and "BN" in constants.NON_STARTER_SLOTS
    assert constants.ESPN_TEAM_CODES["WSH"] == "WAS"
