"""text-audio: read a customer's spoken reply to an agent's order read-back."""

from enum import StrEnum

from core.jev import Audio, Jev, Part, Text, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Reply(StrEnum):
    CONFIRMED = "confirms the order"
    CHANGES = "wants changes"
    CANCELLED = "cancels the order"


def prompt(options: str, readback: Text, reply: Audio) -> list[Part]:
    return ["<|turn>user\n", f"{readback.text}\nCustomer's reply:", reply, f"What does the customer do?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Text, Audio, Reply]:
    return Jev(Reply, prompt, MODEL, MMPROJ)
