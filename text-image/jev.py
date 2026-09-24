"""text-image: file a receipt under an expense category, given the employee's note."""

from enum import StrEnum

from core.jev import Image, Jev, Part, Text, hf

MODEL = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "SmolVLM2-500M-Video-Instruct-Q8_0.gguf")
MMPROJ = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf")


class Category(StrEnum):
    MEALS = "meals"
    TRAVEL = "travel"
    LODGING = "lodging"
    OFFICE = "office supplies"


def prompt(options: str, note: Text, receipt: Image) -> list[Part]:
    return ["<|im_start|>User:", receipt, f"{note.text}\nWhich expense category does this receipt belong to?\n{options}\nAnswer with the letter.<end_of_utterance>\nAssistant:"]


def load() -> Jev[Text, Image, Category]:
    return Jev(Category, prompt, MODEL, MMPROJ)
