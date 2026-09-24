from pathlib import Path

from core.jev import Audio, Text
from jev import Reply, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Text((HERE / "sample.txt").read_text()), Audio(HERE / "sample.wav"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Reply.CHANGES, probs.json()
