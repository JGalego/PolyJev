"""A Jev reads a closed-set answer off next-token logits: one forward pass, nothing to parse."""

import ctypes
import os
import subprocess
import tempfile
import urllib.request
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from string import ascii_uppercase

import numpy as np
from llama_cpp import Llama, llama_cpp, mtmd_cpp

FRAMES = 4  # frames sampled per video, one from the middle of each equal slice
WEIGHTS = Path(os.environ.get("JEV_WEIGHTS", Path.home() / ".cache" / "polyjev"))


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Media:
    src: Path | bytes

    def read(self) -> bytes:
        return self.src if isinstance(self.src, bytes) else self.src.read_bytes()


class Image(Media): ...


class Audio(Media): ...


class Video(Media):
    def _ffmpeg(self, *args: str) -> list[bytes]:
        """Run ffmpeg with {src}, {half}, {step}, {out} filled in; return the files it wrote to {out}*."""
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, "src")
            src.write_bytes(self.read())
            probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]
            step = float(subprocess.run(probe, capture_output=True, check=True).stdout) / FRAMES
            subprocess.run(["ffmpeg", "-v", "error", *(a.format(src=src, half=step / 2, step=step, out=f"{d}/out") for a in args)], check=True)
            return [p.read_bytes() for p in sorted(Path(d).glob("out*"))]

    def frames(self) -> list[Image]:
        jpgs = self._ffmpeg("-ss", "{half}", "-i", "{src}", "-vf", "fps=1/{step},scale='min(512,iw)':-2", "-frames:v", str(FRAMES), "{out}%02d.jpg")
        return [Image(jpg) for jpg in jpgs]

    def audio(self) -> Audio:
        return Audio(self._ffmpeg("-i", "{src}", "-vn", "-ac", "1", "-ar", "16000", "{out}.wav")[0])


type Part = str | Image | Audio


@dataclass(frozen=True)
class Probs[C: StrEnum](Mapping[C, float]):
    p: Mapping[C, float]

    def __getitem__(self, c: C) -> float:
        return self.p[c]

    def __iter__(self) -> Iterator[C]:
        return iter(self.p)

    def __len__(self) -> int:
        return len(self.p)

    @property
    def top(self) -> C:
        return max(self.p, key=self.p.__getitem__)

    def json(self) -> dict[str, object]:
        return {"top": self.top.value, "probs": {c.value: round(p, 4) for c, p in self.p.items()}}


def hf(repo: str, file: str) -> str:
    """Local path of a Hugging Face file, downloaded once into WEIGHTS."""
    path = WEIGHTS / file
    if not path.exists():
        WEIGHTS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"https://huggingface.co/{repo}/resolve/main/{file}", f"{path}.part")
        os.replace(f"{path}.part", path)
    return str(path)


@contextmanager
def _quiet() -> Generator[None]:
    """Mute fd 2 while libmtmd logs every tensor and image slice straight to it."""
    saved, null = os.dup(2), os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 2)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(null)


class Jev[*I, C: StrEnum]:
    """Typed closed-set classifier: (*I) -> Probs[C], read off the logits of the option letters."""

    def __init__(self, labels: type[C], prompt: Callable[[str, *I], Sequence[Part]], model: str, mmproj: str | None = None):
        self.labels, self.prompt = list(labels), prompt
        assert 2 <= len(self.labels) <= 26, "need 2..26 options"
        assert len(labels.__members__) == len(self.labels), f"duplicate option values in {labels.__name__}"
        with _quiet():
            self.llm = Llama(model, n_ctx=4096, n_batch=2048, n_threads=os.cpu_count(), verbose=False)
            self.mtmd = None
            if mmproj:
                params = mtmd_cpp.mtmd_context_params_default()
                params.n_threads, params.print_timings, params.warmup = self.llm.n_threads, False, False
                self.mtmd = mtmd_cpp.mtmd_init_from_file(mmproj.encode(), self.llm.model, params)
        assert not mmproj or self.mtmd, f"failed to load {mmproj}"
        letters = ascii_uppercase[: len(self.labels)]
        self.options = "\n".join(f"{k}. {c.value}" for k, c in zip(letters, self.labels))
        # Each option letter must be one token both bare ("A") and after a space (" A"); the two are summed.
        self.tokens = [[self.llm.tokenize(s.encode(), add_bos=False) for s in (k, f" {k}")] for k in letters]
        assert all(len(t) == 1 for ts in self.tokens for t in ts), f"option letters must be single tokens: {self.tokens}"
        assert len({t[0] for ts in self.tokens for t in ts}) == 2 * len(letters), "option tokens must be distinct"

    def __call__(self, *x: *I) -> Probs[C]:
        logits = self._logits(self.prompt(self.options, *x))
        lp = np.array([np.logaddexp.reduce([logits[t[0]] for t in ts]) for ts in self.tokens])
        return Probs(dict(zip(self.labels, np.exp(lp - np.logaddexp.reduce(lp)).tolist())))

    def _logits(self, parts: Sequence[Part]) -> np.ndarray:
        text = "".join(p if isinstance(p, str) else mtmd_cpp.mtmd_default_marker().decode() for p in parts)
        self.llm.reset()
        if self.mtmd is None:
            self.llm.eval(self.llm.tokenize(text.encode(), add_bos=True, special=True))
        else:
            with _quiet():
                self._eval_mtmd(self.mtmd, text, [p.read() for p in parts if not isinstance(p, str)])
        return np.ctypeslib.as_array(llama_cpp.llama_get_logits_ith(self.llm.ctx, -1), shape=(self.llm.n_vocab(),)).astype(np.float64)

    def _eval_mtmd(self, ctx: mtmd_cpp.mtmd_context_p, text: str, media: list[bytes]) -> None:
        memory = llama_cpp.llama_get_memory(self.llm.ctx)
        assert memory is not None
        llama_cpp.llama_memory_clear(memory, True)
        bitmaps = [mtmd_cpp.mtmd_helper_bitmap_init_from_buf(ctx, (ctypes.c_uint8 * len(m)).from_buffer_copy(m), len(m), False) for m in media]
        chunks = mtmd_cpp.mtmd_input_chunks_init()
        try:
            ok = [b for b in bitmaps if b is not None]
            assert chunks is not None and len(ok) == len(media), "could not decode media"
            inp = mtmd_cpp.mtmd_input_text(text.encode(), len(text.encode()), True, True)
            array = (mtmd_cpp.mtmd_bitmap_p_ctypes * len(ok))(*ok)
            assert mtmd_cpp.mtmd_tokenize(ctx, chunks, ctypes.pointer(inp), array, len(ok)) == 0, "mtmd_tokenize failed"
            n_past = llama_cpp.llama_pos(0)
            ret = mtmd_cpp.mtmd_helper_eval_chunks(ctx, self.llm.ctx, chunks, llama_cpp.llama_pos(0), llama_cpp.llama_seq_id(0), self.llm.n_batch, True, ctypes.pointer(n_past))
            assert ret == 0, "mtmd eval failed"
        finally:
            if chunks is not None:
                mtmd_cpp.mtmd_input_chunks_free(chunks)
            for b in bitmaps:
                if b is not None:
                    mtmd_cpp.mtmd_bitmap_free(b)
