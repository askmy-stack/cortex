from outcomes.ledger import update_usefulness


def test_usefulness_rises_on_success() -> None:
    assert update_usefulness(prior_usefulness=0.5, success=True) > 0.5


def test_usefulness_falls_on_failure() -> None:
    assert update_usefulness(prior_usefulness=0.5, success=False) < 0.5
