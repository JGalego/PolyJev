"""Print the Lambda request for a Jev folder's sample.* inputs: python -m core.payload <jev>."""

import base64
import json
import sys
from pathlib import Path

FIELDS = {".txt": "text", ".png": "image", ".wav": "audio", ".mp4": "video"}


def payload(folder: Path) -> dict[str, str]:
    return {FIELDS[p.suffix]: p.read_text() if p.suffix == ".txt" else base64.b64encode(p.read_bytes()).decode() for p in folder.glob("sample.*")}


if __name__ == "__main__":
    print(json.dumps(payload(Path(sys.argv[1]))))
