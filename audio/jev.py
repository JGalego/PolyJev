"""audio: route a customer voicemail by the caller's intent."""

from enum import StrEnum

from core.jev import Audio, Jev, Part, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Intent(StrEnum):
    BILLING = "billing question"
    CANCEL = "cancel subscription"
    SUPPORT = "technical support"
    SALES = "sales inquiry"


def prompt(options: str, voicemail: Audio) -> list[Part]:
    return ["<|turn>user\n", voicemail, f"What does this caller want?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Audio, Intent]:
    return Jev(Intent, prompt, MODEL, MMPROJ)
