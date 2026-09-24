# polyjev recipes. A jev is a folder name: text, image, ..., text-image-audio-video.

jevs := `ls */jev.py | sed 's|/jev.py||' | grep -vx core | tr '\n' ' '`
token := "${POLYJEV_TOKEN:-$(cat .token)}"

# List the recipes
default:
    @just --list --unsorted

# Build the arm64 image, push it to ECR, and deploy stack polyjev-<jev>
deploy jev:
    sam build --parameter-overrides Jev={{jev}}
    sam deploy --stack-name polyjev-{{jev}} --parameter-overrides Jev={{jev}} --resolve-image-repos

# Deploy all 15 Jevs, then the gateway
deploy-all:
    for j in {{jevs}}; do just deploy $j; done
    just gateway

# Invoke the deployed polyjev-<jev> with its sample.* and pretty-print Probs
test jev:
    @mkdir -p .aws-sam
    @uv run python -m core.payload {{jev}} > .aws-sam/payload.json
    @aws lambda invoke --function-name polyjev-{{jev}} --payload fileb://.aws-sam/payload.json --cli-read-timeout 900 .aws-sam/response.json > /dev/null
    @uv run python -m json.tool .aws-sam/response.json

# Run the Lambda image locally on its sample with `sam local invoke` (native on arm64 hosts, emulated and slow on x86)
invoke jev:
    sam build --parameter-overrides Jev={{jev}}
    @uv run python -m core.payload {{jev}} > .aws-sam/payload.json
    sam local invoke Function --parameter-overrides Jev={{jev}} --event .aws-sam/payload.json

# Run pytest on this machine: one Jev, or every Jev plus the gateway
local jev="":
    for j in {{ if jev == "" { jevs + "gateway" } else { jev } }}; do echo "== $j"; uv run pytest -q $j || exit 1; done

# Delete stack polyjev-<jev> and its ECR repository
destroy jev:
    sam delete --stack-name polyjev-{{jev}} --no-prompts

# Type-check everything with pyright --strict
check:
    uv run pyright

# Deploy the HTTP API gateway; the bearer token is $POLYJEV_TOKEN, else .token, else a new one saved to .token
gateway:
    @test -n "${POLYJEV_TOKEN:-}" -o -s .token || python3 -c 'import secrets; print(secrets.token_urlsafe(24))' > .token
    sam deploy -t gateway/template.yaml --stack-name polyjev-gateway --resolve-s3 --parameter-overrides Token={{token}}
    @echo "API: $(just url)"

# Print the gateway's URL
url:
    @aws cloudformation describe-stacks --stack-name polyjev-gateway --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text

# Empty the job bucket and delete the gateway stack
destroy-gateway:
    aws s3 rm "s3://$(aws cloudformation describe-stacks --stack-name polyjev-gateway --query "Stacks[0].Outputs[?OutputKey=='Bucket'].OutputValue" --output text)" --recursive
    sam delete --stack-name polyjev-gateway --no-prompts

# Classify a Jev's sample through the gateway with curl
call jev:
    #!/usr/bin/env bash
    set -euo pipefail
    api=$(just url); auth="authorization: Bearer {{token}}"
    job=$(uv run python -m core.payload {{jev}} | curl -sf -H "$auth" -H 'content-type: application/json' --data-binary @- "$api/jevs/{{jev}}" | python3 -c 'import json, sys; print(json.load(sys.stdin)["job"])')
    while out=$(curl -s -w '\n%{http_code}' -H "$auth" "$api/jobs/$job") && [ "${out##*$'\n'}" = 202 ]; do sleep 2; done
    echo "${out%$'\n'*}" | python3 -m json.tool

# Serve the demo app for the deployed gateway on http://localhost:<port>
demo port="8000":
    @echo "open http://localhost:{{port}}/demo/?api=$(just url)#token={{token}}"
    python3 -m http.server {{port}} --bind 127.0.0.1
