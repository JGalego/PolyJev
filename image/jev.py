"""image: name the type of chart in a picture."""

from enum import StrEnum

from core.jev import Image, Jev, Part, hf

MODEL = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "SmolVLM2-500M-Video-Instruct-Q8_0.gguf")
MMPROJ = hf("ggml-org/SmolVLM2-500M-Video-Instruct-GGUF", "mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf")


class Chart(StrEnum):
    BAR = "bar chart"
    LINE = "line chart"
    PIE = "pie chart"
    SCATTER = "scatter plot"


def prompt(options: str, chart: Image) -> list[Part]:
    return ["<|im_start|>User:", chart, f"What type of chart is this?\n{options}\nAnswer with the letter.<end_of_utterance>\nAssistant:"]


def load() -> Jev[Image, Chart]:
    return Jev(Chart, prompt, MODEL, MMPROJ)
