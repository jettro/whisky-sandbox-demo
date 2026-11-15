import pytest

from whisky_sandbox_demo.calculations import bottles_needed


@pytest.mark.parametrize(
    ("participants", "pour_ml", "bottle_ml", "expected"),
    [
        (8, 20, 700, 1),
        (35, 20, 700, 1),  # exactly 700 ml
        (36, 20, 700, 2),  # 720 ml: one more bottle
        (40, 20, 700, 2),
        (40, 20, 500, 2),  # 800 ml
        (60, 25, 500, 3),
        (0, 20, 700, 0),
    ],
)
def test_bottles_round_up(participants, pour_ml, bottle_ml, expected):
    assert bottles_needed(participants, pour_ml, bottle_ml) == expected


def test_rejects_invalid_bottle_size():
    with pytest.raises(ValueError):
        bottles_needed(8, 20, 0)
