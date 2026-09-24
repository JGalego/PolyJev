"""text-image-video: settle a missing-parcel claim with the delivery photo and doorbell footage."""

from enum import StrEnum

from core.jev import Image, Jev, Part, Text, Video, hf

MODEL = hf("ggml-org/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q4_0.gguf")
MMPROJ = hf("ggml-org/gemma-4-E2B-it-GGUF", "mmproj-gemma-4-E2B-it-Q8_0.gguf")


class Parcel(StrEnum):
    NEVER_DELIVERED = "never delivered"
    STOLEN = "stolen after delivery"
    STILL_THERE = "still at the door"


def prompt(options: str, claim: Text, photo: Image, doorbell: Video) -> list[Part]:
    return ["<|turn>user\nDelivery photo:", photo, "Doorbell camera frames, in order:", *doorbell.frames(), f"{claim.text}\nWhat happened to the parcel?\n{options}\nAnswer with the letter.<turn|>\n<|turn>model\n"]


def load() -> Jev[Text, Image, Video, Parcel]:
    return Jev(Parcel, prompt, MODEL, MMPROJ)
