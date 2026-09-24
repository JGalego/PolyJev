"""image-audio: map a spoken command to the button it means on screen."""

from enum import StrEnum

from core.jev import Audio, Image, Jev, Part, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Button(StrEnum):
    SAVE = "Save"
    DISCARD = "Don't Save"
    CANCEL = "Cancel"


def prompt(options: str, screen: Image, command: Audio) -> list[Part]:
    return ["<|turn>user\nScreen:", screen, "Spoken command:", command, f"Which button should be clicked?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Image, Audio, Button]:
    return Jev(Button, prompt, MODEL, MMPROJ)
