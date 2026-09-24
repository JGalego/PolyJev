"""image-video: does a reference logo appear anywhere in a clip?"""

from enum import StrEnum

from core.jev import Image, Jev, Part, Video, hf

MODEL = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "SmolVLM2-500M-Video-Instruct-Q8_0.gguf")
MMPROJ = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf")


class Logo(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"


def prompt(options: str, logo: Image, clip: Video) -> list[Part]:
    return ["<|im_start|>User:Logo:", logo, "Video frames:", *clip.frames(), f"Does the logo appear in any of the video frames?\n{options}\nAnswer with the letter.<end_of_utterance>\nAssistant:"]


def load() -> Jev[Image, Video, Logo]:
    return Jev(Logo, prompt, MODEL, MMPROJ)
