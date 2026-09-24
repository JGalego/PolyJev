from pathlib import Path

from core.jev import Audio, Image, Text
from jev import Queue, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Text((HERE / "sample.txt").read_text()), Image(HERE / "sample.png"), Audio(HERE / "sample.wav"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Queue.ACCESS, probs.json()
