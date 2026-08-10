from tether import konsole_followup


def test_retired_followup_is_a_noop():
    assert konsole_followup.main(["--legacy", "ignored"]) == 0
