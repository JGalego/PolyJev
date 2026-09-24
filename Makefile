# make deploy|test|destroy JEV=<folder>    make local [JEV=<folder>]    make check
JEVS := $(filter-out core,$(patsubst %/jev.py,%,$(wildcard */jev.py)))
STACK = polyjev-$(JEV)

.PHONY: deploy test local destroy check jev

deploy: jev  ## build the arm64 image, push it to ECR, deploy the stack
	sam build --parameter-overrides Jev=$(JEV)
	sam deploy --stack-name $(STACK) --parameter-overrides Jev=$(JEV) --resolve-image-repos

test: jev  ## invoke the deployed Lambda with sample.* and pretty-print Probs
	@mkdir -p .aws-sam
	@uv run python -m core.payload $(JEV) > .aws-sam/payload.json
	@aws lambda invoke --function-name $(STACK) --payload fileb://.aws-sam/payload.json --cli-read-timeout 900 .aws-sam/response.json > /dev/null
	@uv run python -m json.tool .aws-sam/response.json

local:  ## run the Jev's pytest locally (every Jev when JEV is unset)
	@for j in $(or $(JEV),$(JEVS)); do echo "== $$j"; uv run pytest -q $$j || exit 1; done

destroy: jev  ## delete the stack and its ECR repository
	sam delete --stack-name $(STACK) --no-prompts

check:  ## pyright --strict over the whole repo
	uv run pyright

jev:
	@test -n "$(JEV)" || { echo "set JEV to one of: $(JEVS)"; exit 1; }
