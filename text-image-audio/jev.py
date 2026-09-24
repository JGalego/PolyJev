"""text-image-audio: route a support ticket from its subject, screenshot, and voice note."""

from enum import StrEnum

from core.jev import Audio, Image, Jev, Part, Text, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Queue(StrEnum):
    BILLING = "billing"
    ACCESS = "account access"
    BUG = "bug report"
    FEATURE = "feature request"


def prompt(options: str, subject: Text, screenshot: Image, voice: Audio) -> list[Part]:
    return ["<|turn>user\n", f"Support ticket: {subject.text}\nScreenshot:", screenshot, "Voice note:", voice, f"Which team should handle this ticket?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Text, Image, Audio, Queue]:
    return Jev(Queue, prompt, MODEL, MMPROJ)
