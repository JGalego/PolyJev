"""Lambda entrypoint: {"text": str} -> {"top": label, "probs": {label: p}}."""

from functools import cache

from pydantic import BaseModel

from core.jev import Text
from jev import load

jev = cache(load)


class Request(BaseModel):
    text: str


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    req = Request.model_validate(event)
    return jev()(Text(req.text)).json()
