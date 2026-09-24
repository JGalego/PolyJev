"""video: tell from a screen recording how a software install ended."""

from enum import StrEnum

from core.jev import Jev, Part, Video, hf

MODEL = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "SmolVLM2-500M-Video-Instruct-Q8_0.gguf")
MMPROJ = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf")


class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RUNNING = "still running"


def prompt(options: str, recording: Video) -> list[Part]:
    return ["<|im_start|>User:", *recording.frames(), f"These are frames of a screen recording, in order. How did the installation end?\n{options}\nAnswer with the letter.<end_of_utterance>\nAssistant:"]


def load() -> Jev[Video, Outcome]:
    return Jev(Outcome, prompt, MODEL, MMPROJ)
