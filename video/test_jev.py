from pathlib import Path

from core.jev import Video
from jev import Outcome, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Video(HERE / "sample.mp4"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Outcome.FAILED, probs.json()
