# polyjev. A <jev> is a folder name: text, image, audio, video, text-image, ..., text-image-audio-video.

jevs := `ls */jev.py | sed 's|/jev.py||' | grep -vx core | tr '\n' ' '`
fun := "scripts/fun.sh"
# Skip Jevs whose MemorySize in template.yaml is above this: `just max_mb=3008 deploy all`, or export POLYJEV_MAX_MB
max_mb := env("POLYJEV_MAX_MB", "10240")

# Show this list
default:
    @just --list --unsorted

# Sign in to AWS with your console credentials (AWS CLI v2)
login:
    @{{fun}} say 🔑 "Signing in to AWS"
    @aws login
    @{{fun}} ok "Signed in as $(aws sts get-caller-identity --query Arn --output text)"

# Run the tests on this machine: one Jev, or all of them
test jev="all":
    #!/usr/bin/env bash
    set -euo pipefail
    todo=({{ if jev == "all" { jevs + "gateway" } else { jev } }}); n=${#todo[@]}; start=$(date +%s)
    for i in "${!todo[@]}"; do
        {{fun}} bar $i $n "🧪 ${todo[i]} ($((i + 1))/$n)" $start
        uv run pytest -q "${todo[i]}" || { {{fun}} fail "${todo[i]} failed"; exit 1; }
    done
    {{fun}} bar $n $n "🎉 all $n green" $start

# Lint the Dockerfiles with hadolint and the shell scripts with shellcheck (same as CI)
lint:
    @{{fun}} say 🐳 "hadolint */Dockerfile"
    @docker run --rm -v "$PWD":/w -w /w hadolint/hadolint:v2.12.0 hadolint */Dockerfile
    @{{fun}} say 🐚 "shellcheck scripts/*.sh"
    @docker run --rm -v "$PWD":/w -w /w koalaman/shellcheck:v0.10.0 scripts/*.sh
    @{{fun}} ok "Lint clean"

# Type-check everything with pyright --strict
check:
    @{{fun}} say 🔍 "pyright --strict"
    @uv run pyright
    @{{fun}} ok "Types check out"

# Run a Jev's Lambda container on this machine with its sample
run jev: (_preflight "uv sam docker") (_sample jev)
    @{{fun}} say 🏗️ "Building {{jev}} (arm64)"
    @sam build --parameter-overrides Jev={{jev}}
    @{{fun}} say 🏃 "Running {{jev}} on its sample"
    @sam local invoke Function --parameter-overrides Jev={{jev}} --event .aws-sam/{{jev}}.json

# Deploy to AWS: a Jev, the gateway (API + demo app), or all
deploy what: (_preflight if what == "gateway" { "python3 sam aws" } else { "python3 sam aws docker" })
    @just max_mb={{max_mb}} _deploy-{{ if what == "all" { "all" } else if what == "gateway" { "gateway" } else { "jev " + what } }}

# Send a Jev's sample to its deployed Lambda
invoke jev: (_preflight "uv python3 aws") (_sample jev)
    @{{fun}} say 🔮 "Asking polyjev-{{jev}}"
    @aws lambda invoke --function-name polyjev-{{jev}} --payload fileb://.aws-sam/{{jev}}.json --cli-read-timeout 900 .aws-sam/out.json > /dev/null
    @python3 -m json.tool .aws-sam/out.json

# Print the demo app's link (after `just deploy gateway`)
demo:
    @echo "🌐 $(just _out Site)/#token=$(cat .token)"

# Delete from AWS: a Jev, the gateway, or all
destroy what: (_preflight "sam aws")
    @just _destroy-{{ if what == "all" { "all" } else if what == "gateway" { "gateway" } else { "jev " + what } }}

# Stop early when a tool is missing, Docker is down or can't build arm64, or AWS isn't set up
_preflight tools:
    #!/usr/bin/env bash
    set -euo pipefail
    fail() { {{fun}} fail "preflight: $*"; exit 1; }
    for t in {{tools}}; do command -v $t > /dev/null || fail "$t is not installed"; done
    if [[ " {{tools}} " == *" sam "* ]]; then
        [[ "$(sam build --help)" == *--use-buildkit* ]] || fail "$(sam --version) can't build with BuildKit (samconfig.toml sets use_buildkit); upgrade SAM CLI"
    fi
    if [[ " {{tools}} " == *" docker "* ]]; then
        docker info > /dev/null 2>&1 || fail "Docker is not running"
        docker buildx ls 2>/dev/null | grep -q linux/arm64 || fail "Docker can't build linux/arm64 images; install QEMU: docker run --privileged --rm tonistiigi/binfmt --install arm64"
    fi
    if [[ " {{tools}} " == *" aws "* ]]; then
        [[ -n "${AWS_REGION:-${AWS_DEFAULT_REGION:-}}" ]] || aws configure get region > /dev/null || fail "no AWS region set (aws configure set region <region>, or export AWS_REGION)"
        aws sts get-caller-identity > /dev/null 2>&1 || fail "not signed in to AWS (just login)"
    fi
    {{fun}} say ✈️ "Preflight OK: {{tools}}"

_sample jev:
    @mkdir -p .aws-sam && uv run python -m core.payload {{jev}} > .aws-sam/{{jev}}.json

_deploy-jev jev:
    @mb=$(just _mb {{jev}}); [ "$mb" -le {{max_mb}} ] || { {{fun}} fail "{{jev}} needs $mb MB, over max_mb={{max_mb}}"; exit 1; }
    @{{fun}} say 🏗️ "Building {{jev}} (arm64, weights baked in)"
    @sam build --parameter-overrides Jev={{jev}}
    @{{fun}} say 🚀 "Deploying polyjev-{{jev}}"
    @sam deploy --stack-name polyjev-{{jev}} --parameter-overrides Jev={{jev}} --resolve-image-repos
    @{{fun}} ok "polyjev-{{jev}} is live"

_deploy-gateway:
    @test -s .token || python3 -c 'import secrets; print(secrets.token_urlsafe(24))' > .token
    @{{fun}} say 🚪 "Deploying polyjev-gateway (API Gateway, router, CloudFront)"
    @# samconfig.toml is read from the template's folder, so the gateway gets its settings here
    @sam deploy -t gateway/template.yaml --stack-name polyjev-gateway --resolve-s3 --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset --parameter-overrides Token=$(cat .token)
    @{{fun}} say 📦 "Uploading the demo app and samples"
    @aws s3 cp demo/index.html s3://$(just _out SiteBucket)/index.html
    @aws s3 sync . s3://$(just _out SiteBucket) --exclude '*' --include '*/sample.*' --include '*/jev.py' --include 'demo/examples/*' --exclude 'demo/examples/*.py' --exclude 'core/*' --exclude '.*'
    @{{fun}} say 🧽 "Invalidating the CloudFront cache"
    @aws cloudfront create-invalidation --distribution-id $(just _out Distribution) --paths '/*' > /dev/null
    @{{fun}} ok "Demo app: $(just _out Site)  (just demo prints a signed-in link)"

_deploy-all:
    #!/usr/bin/env bash
    set -euo pipefail
    todo=()
    for j in {{jevs}}; do
        mb=$(just _mb $j)
        if [ "$mb" -le {{max_mb}} ]; then todo+=($j); else {{fun}} say ⏭️ "Skipping $j ($mb MB > max_mb={{max_mb}})"; fi
    done
    n=${#todo[@]}; start=$(date +%s)
    for i in "${!todo[@]}"; do
        {{fun}} bar $i $((n + 1)) "🚀 ${todo[i]} ($((i + 1))/$n)" $start
        just max_mb={{max_mb}} _deploy-jev "${todo[i]}" || { {{fun}} fail "${todo[i]} failed; fix it and rerun: stacks already up to date are no-ops"; exit 1; }
    done
    {{fun}} bar $n $((n + 1)) "🚪 gateway" $start
    just _deploy-gateway
    {{fun}} bar 1 1 "🎉 $n Jevs and the gateway are live" $start

_destroy-jev jev:
    @{{fun}} say 🧹 "Deleting polyjev-{{jev}}"
    @sam delete --stack-name polyjev-{{jev}} --no-prompts

_destroy-gateway:
    @{{fun}} say 🪣 "Emptying the gateway's buckets"
    @aws s3 rm s3://$(just _out JobBucket) --recursive
    @aws s3 rm s3://$(just _out SiteBucket) --recursive
    @{{fun}} say 🧹 "Deleting polyjev-gateway"
    @sam delete --stack-name polyjev-gateway --no-prompts

_destroy-all:
    #!/usr/bin/env bash
    set -uo pipefail
    todo=({{jevs}}); n=${#todo[@]}; start=$(date +%s)
    {{fun}} bar 0 $((n + 1)) "🚪 gateway" $start
    just _destroy-gateway || {{fun}} fail "gateway: skipped (not deployed?)"
    for i in "${!todo[@]}"; do
        {{fun}} bar $((i + 1)) $((n + 1)) "🧹 ${todo[i]} ($((i + 1))/$n)" $start
        just _destroy-jev "${todo[i]}" || {{fun}} fail "${todo[i]}: skipped"
    done
    {{fun}} bar 1 1 "🌱 All cleaned up" $start

# A Jev's MemorySize (MB), from the Memory mapping in template.yaml
_mb jev:
    @awk -F'[ :{}]+' '$2 == "{{jev}}" && $3 == "MB" { print $4 }' template.yaml

_out key:
    @aws cloudformation describe-stacks --stack-name polyjev-gateway --query "Stacks[0].Outputs[?OutputKey=='{{key}}'].OutputValue" --output text
