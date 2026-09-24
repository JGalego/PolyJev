"""text: triage an email as legitimate, spam, or phishing."""

from enum import StrEnum

from core.jev import Jev, Part, Text, hf

MODEL = hf("Qwen/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q8_0.gguf")


class Email(StrEnum):
    LEGITIMATE = "legitimate"
    SPAM = "spam"
    PHISHING = "phishing"


def prompt(options: str, email: Text) -> list[Part]:
    return [
        "<|im_start|>system\nYou are an email security filter.<|im_end|>\n"
        f"<|im_start|>user\nClassify this email.\n\n{email.text}\n{options}\nAnswer with the letter.<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    ]


def load() -> Jev[Text, Email]:
    return Jev(Email, prompt, MODEL)
