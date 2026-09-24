"""Lambda entrypoint: {"image": base64} -> {"top": label, "probs": {label: p}}."""

from functools import cache

from pydantic import Base64Bytes, BaseModel

from core.jev import Image
from jev import load

jev = cache(load)


class Request(BaseModel):
    image: Base64Bytes


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    req = Request.model_validate(event)
    return jev()(Image(req.image)).json()
