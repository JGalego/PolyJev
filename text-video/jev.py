"""text-video: does a screen recording reproduce the bug in a report?"""

from enum import StrEnum

from core.jev import Jev, Part, Text, Video, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Repro(StrEnum):
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not reproduced"


def prompt(options: str, report: Text, recording: Video) -> list[Part]:
    return ["<|turn>user\n", *recording.frames(), f"These are frames of a screen recording, in order.\n{report.text}\nDoes the recording show this bug?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Text, Video, Repro]:
    return Jev(Repro, prompt, MODEL, MMPROJ)
