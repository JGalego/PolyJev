from pathlib import Path

from core.jev import Audio
from jev import Intent, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Audio(HERE / "sample.wav"))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Intent.SUPPORT, probs.json()
