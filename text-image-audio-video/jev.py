"""text-image-audio-video: set incident severity from the alert, dashboard, on-call voice note, and status page."""

from enum import StrEnum

from core.jev import Image, Jev, Part, Text, Video, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Severity(StrEnum):
    SEV1 = "SEV1: outage, customers blocked"
    SEV2 = "SEV2: degraded, customers affected"
    SEV3 = "SEV3: minor, no customer impact"


def prompt(options: str, alert: Text, dashboard: Image, status: Video) -> list[Part]:
    return ["<|turn>user\n", f"Alert: {alert.text}\nDashboard:", dashboard, "Status page recording and on-call voice note:", *status.frames(), status.audio(), f"How severe is this incident?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Text, Image, Video, Severity]:
    return Jev(Severity, prompt, MODEL, MMPROJ)
