from pathlib import Path

from core.jev import Text
from jev import Email, load

HERE = Path(__file__).parent


def test_jev() -> None:
    probs = load()(Text((HERE / "sample.txt").read_text()))
    assert abs(sum(probs.values()) - 1) < 1e-6
    assert probs.top is Email.PHISHING, probs.json()
