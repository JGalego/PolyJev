# polyjev. A <jev> is a folder name: text, image, audio, video, text-image, ..., text-image-audio-video.

jevs := `ls */jev.py | sed 's|/jev.py||' | grep -vx core | tr '\n' ' '`

# Show this list
default:
    @just --list --unsorted

# Sign in to AWS with your console credentials (AWS CLI v2)
login:
    aws login

# Run the tests on this machine: one Jev, or all of them
test jev="all":
    for j in {{ if jev == "all" { jevs + "gateway" } else { jev } }}; do uv run pytest -q $j || exit 1; done

# Type-check everything with pyright --strict
check:
    uv run pyright

# Run a Jev's Lambda container on this machine with its sample
run jev: (_sample jev)
    sam build --parameter-overrides Jev={{jev}}
    sam local invoke Function --parameter-overrides Jev={{jev}} --event .aws-sam/{{jev}}.json

# Deploy to AWS: a Jev, the gateway (API + demo app), or all
deploy what:
    @just _deploy-{{ if what == "all" { "all" } else if what == "gateway" { "gateway" } else { "jev " + what } }}

# Send a Jev's sample to its deployed Lambda
invoke jev: (_sample jev)
    @aws lambda invoke --function-name polyjev-{{jev}} --payload fileb://.aws-sam/{{jev}}.json --cli-read-timeout 900 .aws-sam/out.json > /dev/null
    @python3 -m json.tool .aws-sam/out.json

# Print the demo app's link (after `just deploy gateway`)
demo:
    @echo "$(just _out Site)/#token=$(cat .token)"

# Delete from AWS: a Jev, the gateway, or all
destroy what:
    @just _destroy-{{ if what == "all" { "all" } else if what == "gateway" { "gateway" } else { "jev " + what } }}

_sample jev:
    @mkdir -p .aws-sam && uv run python -m core.payload {{jev}} > .aws-sam/{{jev}}.json

_deploy-jev jev:
    sam build --parameter-overrides Jev={{jev}}
    sam deploy --stack-name polyjev-{{jev}} --parameter-overrides Jev={{jev}} --resolve-image-repos

_deploy-gateway:
    @test -s .token || python3 -c 'import secrets; print(secrets.token_urlsafe(24))' > .token
    sam deploy -t gateway/template.yaml --stack-name polyjev-gateway --resolve-s3 --parameter-overrides Token=$(cat .token)
    aws s3 cp demo/index.html s3://$(just _out SiteBucket)/index.html
    aws s3 sync . s3://$(just _out SiteBucket) --exclude '*' --include '*/sample.*' --include '*/jev.py' --exclude 'core/*' --exclude '.*'
    aws cloudfront create-invalidation --distribution-id $(just _out Distribution) --paths '/*' > /dev/null
    @echo "Demo app: $(just _out Site)  (just demo prints a signed-in link)"

_deploy-all:
    for j in {{jevs}}; do just _deploy-jev $j; done
    just _deploy-gateway

_destroy-jev jev:
    sam delete --stack-name polyjev-{{jev}} --no-prompts

_destroy-gateway:
    aws s3 rm s3://$(just _out JobBucket) --recursive
    aws s3 rm s3://$(just _out SiteBucket) --recursive
    sam delete --stack-name polyjev-gateway --no-prompts

_destroy-all:
    -just _destroy-gateway
    for j in {{jevs}}; do just _destroy-jev $j || true; done

_out key:
    @aws cloudformation describe-stacks --stack-name polyjev-gateway --query "Stacks[0].Outputs[?OutputKey=='{{key}}'].OutputValue" --output text
