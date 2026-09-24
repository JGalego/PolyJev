from pathlib import Path

from core.jev import Image
from jev import Chart, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Image(HERE / "sample.png"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Chart.PIE, probs.json()
