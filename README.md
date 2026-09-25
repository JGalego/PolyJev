<div align="center">

# polyjev

**Typed answers from any modality, one forward pass.**

[![Python ≥3.12](https://img.shields.io/badge/python-%E2%89%A53.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![pyright strict](https://img.shields.io/badge/pyright-strict-2C5BB4)](https://microsoft.github.io/pyright/)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

A **Jev** is a closed-set classifier built from a generative model that never generates. It renders the input and a lettered list of options into a prompt, runs a single forward pass, and reads the next-token logits of the option letters (`A`, `B`, `C`, …); a log-softmax over just those logits gives a distribution over the options ([reference gist](https://gist.github.com/JGalego/57883950fe3d5c609f34312fc3d5c3d6)). Generating and then parsing costs many decode steps and can produce answers that are misspelled, hedged, or not among the options. A Jev can only return one of its options, because nothing is parsed, and every option comes with a probability.

polyjev has one Jev for each of the 15 non-empty combinations of text, image, audio, and video, and each one is type-safe from end to end:

```python
class Category(StrEnum):
    MEALS = "meals"
    TRAVEL = "travel"
    LODGING = "lodging"
    OFFICE = "office supplies"

jev: Jev[Text, Image, Category] = load()      # asserts each option letter is one distinct token
probs = jev(Text("Boston client visit"), Image(Path("receipt.png")))  # Probs[Category], sums to 1
probs.top                                     # Category.MEALS
```

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Docker](https://docs.docker.com/get-docker/) with arm64 builds. This works natively on Apple Silicon and Graviton. On x86 Linux, install QEMU first: `docker run --privileged --rm tonistiigi/binfmt --install arm64`
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) (2.32 or later, for `aws login`) and [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- AWS credentials: run `aws login`. It signs you in through the browser with your AWS console credentials, asks for a default region the first time, and stores short-lived credentials instead of long-lived access keys.
- `ffmpeg` on your `PATH` to run the video Jevs locally (the images ship their own)

### Build / install

```bash
uv sync
```

### Deploy

```bash
make deploy JEV=text-image
```

This builds the arm64 image with the weights baked in, pushes it to a SAM-managed ECR repository (`--resolve-image-repos`), and deploys the `polyjev-text-image` stack without prompting. `make destroy JEV=text-image` removes both.

### Test

```bash
make local JEV=text-image   # pytest on this machine: probabilities sum to 1 and the top label is right
make local                  # the same for all 15 Jevs
make test JEV=text-image    # invokes the deployed Lambda with sample.* and pretty-prints Probs
make check                  # pyright --strict, also enforced in CI
```

A local run downloads the weights once into `~/.cache/polyjev` (override with `JEV_WEIGHTS`). The gateway and the demo app are deployed with just; see [Just commands](#just-commands).

## Just commands

The [justfile](justfile) covers everything above, plus the gateway and the demo app. Install just with `uv tool install rust-just`, then run `just` to list the commands. `<jev>` is a folder name such as `text-image`.

| Command | What it does |
| --- | --- |
| `just login` | `aws login`: sign in to AWS with your console credentials |
| `just test [<jev>]` | Run the tests on this machine: one Jev, or every Jev plus the gateway |
| `just check` | Type-check everything with pyright --strict |
| `just run <jev>` | Build a Jev's Lambda image and run it on this machine (`sam local invoke`) with its sample |
| `just deploy <jev>` | Deploy one Jev to AWS |
| `just deploy gateway` | Deploy API Gateway, the router, and the CloudFront-hosted demo app |
| `just deploy all` | Deploy all 15 Jevs, then the gateway |
| `just invoke <jev>` | Send a Jev's sample to its deployed Lambda and print the Probs |
| `just demo` | Print the demo app's link, with the access token in the URL fragment |
| `just destroy <jev>` / `gateway` / `all` | Delete what `deploy` created |

`just run` uses the same arm64 image that Lambda runs. That's native and quick on Apple Silicon or Graviton, but on x86 it runs under QEMU and can take minutes per call.

The demo app has a card per Jev. For each one you can upload your own inputs or load the bundled sample, and it shows the probability of every option. **Run all 15** classifies every sample in parallel.

## Architecture (AWS)

```mermaid
flowchart LR
    dev["Developer<br/>make deploy JEV=…"] -- "sam build (arm64) + push" --> ecr[("Amazon ECR<br/>image with baked-in weights")]
    ecr -- "sam deploy" --> fn["AWS Lambda container<br/>polyjev-JEV (×15)<br/>handler → Jev → Probs"]
    dev -. "make test<br/>aws lambda invoke" .-> fn
    user["Browser / curl"] --> cdn["Amazon CloudFront"]
    cdn -- "/, /JEV/sample.*" --> site[("S3 site bucket<br/>demo app + samples")]
    cdn -- "POST /jevs/JEV<br/>GET /jobs/ID" --> api["Amazon API Gateway<br/>HTTP API"]
    api --> router["Lambda<br/>polyjev-gateway"]
    router -- "request / Probs" --> s3[("S3 job bucket<br/>expires in 1 day")]
    router -- "async self-invoke,<br/>then invoke" --> fn
    fn -- "logs" --> cw["CloudWatch Logs"]
    router -- "logs" --> cw
```

Each Jev stack is one container-image function with no public URL of its own. You can call it directly with `lambda:InvokeFunction`, or through the optional gateway stack in `gateway/`. That stack is serverless too: an Amazon API Gateway HTTP API in front of all 15 functions, and a CloudFront distribution that serves the demo app from a private S3 bucket and forwards `/jevs/*` and `/jobs/*` to the API, so the app and the API share one HTTPS origin. API Gateway's integrations time out after 30 s, but a Jev can take longer, and minutes on a cold start. So `POST /jevs/{jev}` stores the request in S3, returns `202 {"job": id}`, and the router invokes itself asynchronously to call `polyjev-{jev}`, waiting up to 900 s. `GET /jobs/{id}` returns `202` while the job runs, then the Probs or `{"error": …}`. Every API route requires an `x-polyjev-token` header, and the stage is throttled to 5 requests per second. Jevs that aren't deployed return an error when polled rather than a crash. Requests are JSON: `text` is a string, and `image`, `audio`, and `video` are base64. The response is `{"top": label, "probs": {label: p}}`. Video is sampled as `FRAMES = 4` evenly spaced frames. In the combinations that include audio, the audio comes from the clip's own soundtrack. Both are extracted with ffmpeg and fed through the model's image and audio paths.

**Cold starts.** Weights are downloaded while the image is built, so a cold start downloads nothing. The model is loaded on the first invoke rather than in the 10-second init phase: Lambda streams the image from ECR, and the GGUF weights are memory-mapped from it. That is why the timeout is the full 900 s. Warm invocations reuse the loaded model.

**Memory sizing.** Each Jev's `MemorySize` in `template.yaml` is its measured peak RSS plus headroom: about 0.9 GB for SmolVLM2-500M, 2.4 GB for Qwen3-1.7B, and 4.8 GB for Gemma 4 E2B. Lambda allocates vCPUs in proportion to memory (6 vCPUs at 10,240 MB), and a forward pass is CPU-bound, so raising the memory up to 10,240 MB buys lower latency. New AWS accounts may be capped at 3,008 MB until the quota is raised.

Every folder runs on **llama-cpp-python** with GGUF weights, plus a multimodal projector (`mmproj`) fed through libmtmd for image and audio. None needed the `transformers` fallback.

| Folder | Demo task | Options | Model (GGUF) | Backend | Memory |
| --- | --- | --- | --- | --- | --- |
| `text` | Email triage | legitimate · spam · phishing | Qwen3-1.7B Q8_0 | llama-cpp-python | 4096 MB |
| `image` | Chart type | bar · line · pie · scatter | SmolVLM2-500M-Video Q8_0 + mmproj | llama-cpp-python + mtmd | 3008 MB |
| `audio` | Voicemail intent | billing · cancel · support · sales | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `video` | Installer outcome from a screen recording | succeeded · failed · still running | SmolVLM2-500M-Video Q8_0 + mmproj | llama-cpp-python + mtmd | 3008 MB |
| `text-image` | Expense category from note + receipt | meals · travel · lodging · office supplies | SmolVLM2-500M-Video Q8_0 + mmproj | llama-cpp-python + mtmd | 3008 MB |
| `text-audio` | Customer's spoken reply to an order read-back | confirms · wants changes · cancels | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `text-video` | Does a screen recording reproduce a bug report? | reproduced · not reproduced | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `image-audio` | Spoken command → button on screen | Save · Don't Save · Cancel | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `image-video` | Does a reference logo appear in a clip? | present · absent | SmolVLM2-500M-Video Q8_0 + mmproj | llama-cpp-python + mtmd | 3008 MB |
| `audio-video` | Ad compliance: spoken vs on-screen price | match · differ | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `text-image-audio` | Support ticket routing (subject + screenshot + voice note) | billing · account access · bug · feature | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `text-image-video` | Missing-parcel claim (claim + delivery photo + doorbell cam) | never delivered · stolen · still there | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `text-audio-video` | Fact-check a claim against a recorded talk | supported · refuted · not enough info | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `image-audio-video` | Return triage (listing photo + unboxing clip) | as described · damaged · wrong item | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |
| `text-image-audio-video` | Incident severity (alert + dashboard + narrated status page) | SEV1 · SEV2 · SEV3 | Gemma 4 E2B Q4_0 + mmproj | llama-cpp-python + mtmd | 8192 MB |

I picked each model as the smallest one that got its demo right. SmolVLM2-500M handles the single-image and simple video questions. Gemma 4 E2B handles every task with audio, and the vision tasks that need cross-checking evidence, where SmolVLM2 guessed. Ultravox 1B and Qwen2.5-Omni 3B also load through libmtmd. Ultravox was near chance on the voicemail demo. Qwen2.5-Omni was right but about 5× slower than Gemma, because it pads every clip to 30 s of audio. The `sample.*` inputs are synthetic: rendered with Pillow and matplotlib, with speech from Piper's public-domain LJSpeech voice.

## License

[MIT](LICENSE)
