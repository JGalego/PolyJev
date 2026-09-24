"""image-audio-video: triage a return from the listing photo and the customer's unboxing clip."""

from enum import StrEnum

from core.jev import Image, Jev, Part, Video, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Return(StrEnum):
    AS_DESCRIBED = "item as described"
    DAMAGED = "item damaged"
    WRONG_ITEM = "wrong item"


def prompt(options: str, listing: Image, unboxing: Video) -> list[Part]:
    return ["<|turn>user\nListing photo:", listing, "Unboxing video frames and audio:", *unboxing.frames(), unboxing.audio(), f"What is the problem with this return?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Image, Video, Return]:
    return Jev(Return, prompt, MODEL, MMPROJ)
