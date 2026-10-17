from sleeper_assistant.core.nfl.injury_status import UNLIKELY_TO_PLAY, WILL_NOT_PLAY


def test_doubtful_is_unlikely_but_not_ruled_out() -> None:
    assert "Doubtful" in UNLIKELY_TO_PLAY and "Doubtful" not in WILL_NOT_PLAY
    assert WILL_NOT_PLAY <= UNLIKELY_TO_PLAY


def test_every_spelling_the_app_used_to_check_is_covered() -> None:
    for status in ("Out", "IR", "Injured Reserve", "PUP", "Sus", "Suspended", "NA", "DNR", "COV"):
        assert status in WILL_NOT_PLAY
    for status in ("Questionable", "Probable", ""):
        assert status not in UNLIKELY_TO_PLAY
