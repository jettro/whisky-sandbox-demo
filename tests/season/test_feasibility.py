"""The season must be solvable, the budget must bind, and more than one answer must exist."""

from whisky_sandbox_demo.season.catalogue import DEFAULT_SEASON
from whisky_sandbox_demo.season.models import THEMES
from whisky_sandbox_demo.season.validation import validate_season

from .reference import candidates, cheapest_season, plan_from_picks


def test_every_theme_has_enough_candidates():
    for theme in THEMES:
        best = max(len(candidates(s, theme)) for s in ("S1", "S2", "S3"))
        assert best >= 6, theme


def test_reference_season_is_valid_and_within_budget():
    total, picks = cheapest_season()
    report = validate_season(plan_from_picks(picks))
    assert report.valid, report.failed
    assert total <= DEFAULT_SEASON.budget_cents


def test_budget_is_calibrated_close_to_the_cheapest_season():
    total, _ = cheapest_season()
    assert total * 1.05 <= DEFAULT_SEASON.budget_cents <= total * 1.15


def test_budget_binds():
    # Picking the middle of the price range at the real shop is far over budget.
    mid = 0
    for theme in THEMES:
        c = candidates("S1", theme)
        mid += sum(cost for cost, _ in c[len(c) // 2 :][:4])
    assert mid > DEFAULT_SEASON.budget_cents


def test_more_than_one_valid_season():
    _, picks = cheapest_season()
    theme = "speyside"
    supplier, ids = picks[theme]
    used = {pid for _, chosen in picks.values() for pid in chosen}
    spare = next(pid for _, pid in candidates(supplier, theme) if pid not in used)
    alt = {**picks, theme: (supplier, [*ids[:-1], spare])}
    assert validate_season(plan_from_picks(alt)).valid
