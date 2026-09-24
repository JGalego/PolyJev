"""text-audio-video: fact-check a claim against a recorded presentation."""

from enum import StrEnum

from core.jev import Jev, Part, Text, Video, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Verdict(StrEnum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    UNVERIFIABLE = "not enough information"


def prompt(options: str, claim: Text, talk: Video) -> list[Part]:
    return ["<|turn>user\n", *talk.frames(), talk.audio(), f"These are frames and the audio of a presentation.\n{claim.text}\nDoes the presentation support the claim?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Text, Video, Verdict]:
    return Jev(Verdict, prompt, MODEL, MMPROJ)
