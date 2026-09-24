import io
import json
import os
from typing import Any

import pytest
from botocore.exceptions import ClientError

os.environ.update(BUCKET="bucket", TOKEN="secret-token-123456", AWS_DEFAULT_REGION="us-east-1")
import router  # noqa: E402

AUTH = {"x-polyjev-token": "secret-token-123456"}


class Context:
    function_name = "polyjev-gateway"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[Key] = Body

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket: str, Key: str) -> None:
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")


class FakeLambda:
    """Runs the async self-invocation inline; polyjev-text answers, polyjev-image crashes."""

    def invoke(self, FunctionName: str, Payload: bytes, InvocationType: str = "RequestResponse") -> dict[str, Any]:
        if InvocationType == "Event":
            router.handler(json.loads(Payload), Context())
            return {}
        if FunctionName == "polyjev-text":
            assert json.loads(Payload) == {"text": "hi"}
            return {"Payload": io.BytesIO(b'{"top": "spam", "probs": {"spam": 1.0}}')}
        return {"FunctionError": "Unhandled", "Payload": io.BytesIO(b'{"errorMessage": "boom"}')}


@pytest.fixture(autouse=True)
def fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router, "s3", FakeS3())
    monkeypatch.setattr(router, "lam", FakeLambda())


def call(method_path: str, body: str = "", headers: dict[str, str] = AUTH) -> tuple[int, dict[str, Any]]:
    key, value = method_path.split("/")[1:3]
    event = {"headers": headers, "pathParameters": {key.rstrip("s"): value}, "body": body}
    out = router.handler(event, Context())
    assert out is not None
    return out["statusCode"], json.loads(out["body"])


def test_job_round_trip() -> None:
    status, body = call("POST /jevs/text", '{"text": "hi"}')
    assert status == 202
    assert call(f"GET /jobs/{body['job']}") == (200, {"top": "spam", "probs": {"spam": 1.0}})


def test_jev_error_is_reported() -> None:
    _, body = call("POST /jevs/image", "{}")
    assert call(f"GET /jobs/{body['job']}") == (200, {"error": "boom"})


def test_rejects_bad_token_unknown_jev_and_job() -> None:
    assert call("POST /jevs/text", "{}", {"x-polyjev-token": "nope"})[0] == 401
    assert call("POST /jevs/smell", "{}")[0] == 404
    assert call("GET /jobs/123")[0] == 404
