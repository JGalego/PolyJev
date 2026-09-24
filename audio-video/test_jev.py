from pathlib import Path

from core.jev import Video
from jev import Price, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Video(HERE / "sample.mp4"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Price.MISMATCH, probs.json()
