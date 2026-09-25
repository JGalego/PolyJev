"""Run the demo examples through the real Jevs on this machine: `uv run python demo/examples/check.py [<jev> ...]`.

Prints each example's top answer against the one it expects, and exits 1 if any disagree. Downloads each Jev's weights
on first use, like the tests.
"""

import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from core.jev import Audio, Image, Text, Video  # noqa: E402

MEDIA = {"image": Image, "audio": Audio, "video": Video}


def check(jev: str, examples: list[dict[str, str]]) -> int:
    sys.path.insert(0, str(ROOT / jev))
    sys.modules.pop("jev", None)
    model = importlib.import_module("jev").load()
    sys.path.pop(0)
    misses = 0
    for ex in examples:
        # Inputs go in the order the Jev takes them: text, image, audio, video.
        inputs = ([Text(ex["text"])] if "text" in ex else []) + [cls(HERE / ex[k]) for k, cls in MEDIA.items() if k in ex]
        probs = model(*inputs)
        ok = probs.top == ex["expect"]
        misses += not ok
        print(f"{'✓' if ok else '✗'} {jev:24} {ex['label']:45} {probs.top} ({probs[probs.top]:.0%})" + ("" if ok else f", expected {ex['expect']}"), flush=True)
    return misses


if __name__ == "__main__":
    examples: dict[str, list[dict[str, str]]] = json.loads((HERE / "examples.json").read_text())
    misses = sum(check(jev, examples[jev]) for jev in (sys.argv[1:] or examples))
    sys.exit(1 if misses else 0)
