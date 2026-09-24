"""HTTP API router: POST /jevs/{jev} queues a job, GET /jobs/{job} returns its Probs when ready.

A Jev can outlive API Gateway's 30 s integration timeout (cold starts load GBs of weights), so the
request is parked in S3 and this function re-invokes itself asynchronously to call polyjev-{jev}.
"""

import base64
import hmac
import json
import os
import uuid
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

if TYPE_CHECKING:  # dev-only stubs; the Lambda runtime ships boto3 itself
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_s3 import S3Client

JEVS = {"text", "image", "audio", "video", "text-image", "text-audio", "text-video", "image-audio", "image-video", "audio-video",
        "text-image-audio", "text-image-video", "text-audio-video", "image-audio-video", "text-image-audio-video"}
BUCKET, TOKEN = os.environ["BUCKET"], os.environ["TOKEN"]
s3: "S3Client" = boto3.client("s3")
lam: "LambdaClient" = boto3.client("lambda", config=Config(read_timeout=900, retries={"max_attempts": 0}))


def respond(status: int, body: object) -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any] | None:
    if "job" in event:  # our own async invocation
        return work(event["job"], event["jev"])
    if not hmac.compare_digest(event.get("headers", {}).get("authorization", ""), f"Bearer {TOKEN}"):
        return respond(401, {"error": "missing or wrong bearer token"})
    params: dict[str, str] = event.get("pathParameters") or {}
    if "jev" in params:
        return submit(params["jev"], event.get("body") or "", event.get("isBase64Encoded", False), context.function_name)
    return poll(params.get("job", ""))


def submit(jev: str, body: str, b64: bool, me: str) -> dict[str, Any]:
    if jev not in JEVS:
        return respond(404, {"error": f"unknown jev {jev!r}", "jevs": sorted(JEVS)})
    job = str(uuid.uuid4())
    s3.put_object(Bucket=BUCKET, Key=f"in/{job}.json", Body=base64.b64decode(body) if b64 else body.encode())
    lam.invoke(FunctionName=me, InvocationType="Event", Payload=json.dumps({"job": job, "jev": jev}).encode())
    return respond(202, {"job": job, "jev": jev})


def work(job: str, jev: str) -> None:
    try:
        payload = s3.get_object(Bucket=BUCKET, Key=f"in/{job}.json")["Body"].read()
        out = lam.invoke(FunctionName=f"polyjev-{jev}", Payload=payload)
        result = json.loads(out["Payload"].read())
        if "FunctionError" in out:
            result = {"error": result.get("errorMessage", "the Jev failed")}
    except Exception as e:  # report every failure to the poller instead of leaving the job pending
        result = {"error": str(e)}
    s3.put_object(Bucket=BUCKET, Key=f"out/{job}.json", Body=json.dumps(result).encode())


def poll(job: str) -> dict[str, Any]:
    if not exists(f"in/{job}.json"):
        return respond(404, {"error": f"no such job {job!r}"})
    if not exists(f"out/{job}.json"):
        return respond(202, {"job": job, "status": "running"})
    return respond(200, json.loads(s3.get_object(Bucket=BUCKET, Key=f"out/{job}.json")["Body"].read()))


def exists(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError:
        return False
