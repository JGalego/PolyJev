"""Lambda entrypoint: {"text": str, "audio": base64} -> {"top": label, "probs": {label: p}}."""

from functools import cache

from pydantic import Base64Bytes, BaseModel

from core.jev import Audio, Text
from jev import load

jev = cache(load)


class Request(BaseModel):
    text: str
    audio: Base64Bytes


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    req = Request.model_validate(event)
    return jev()(Text(req.text), Audio(req.audio)).json()
