from pathlib import Path

from core.jev import Image, Video
from jev import Return, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Image(HERE / "sample.png"), Video(HERE / "sample.mp4"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Return.DAMAGED, probs.json()
