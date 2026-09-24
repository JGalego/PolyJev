"""audio-video: does the voice-over quote the price shown on screen?"""

from enum import StrEnum

from core.jev import Jev, Part, Video, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Price(StrEnum):
    MATCH = "prices match"
    MISMATCH = "prices differ"


def prompt(options: str, ad: Video) -> list[Part]:
    return ["<|turn>user\n", *ad.frames(), ad.audio(), f"These are frames and the soundtrack of an ad. Does the price spoken in the voice-over match the price shown on screen?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Video, Price]:
    return Jev(Price, prompt, MODEL, MMPROJ)
