from pathlib import Path

from core.jev import Text, Video
from jev import Repro, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Text((HERE / "sample.txt").read_text()), Video(HERE / "sample.mp4"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Repro.REPRODUCED, probs.json()
