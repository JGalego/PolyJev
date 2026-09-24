from pathlib import Path

from core.jev import Image, Text, Video
from jev import Parcel, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Text((HERE / "sample.txt").read_text()), Image(HERE / "sample.png"), Video(HERE / "sample.mp4"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Parcel.STOLEN, probs.json()
