"""Lambda entrypoint: {"text": str, "image": base64, "video": base64} -> {"top": label, "probs": {label: p}}."""

from functools import cache

from pydantic import Base64Bytes, BaseModel

from core.jev import Image, Text, Video
from jev import load

jev = cache(load)


class Request(BaseModel):
    text: str
    image: Base64Bytes
    video: Base64Bytes


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    req = Request.model_validate(event)
    return jev()(Text(req.text), Image(req.image), Video(req.video)).json()
