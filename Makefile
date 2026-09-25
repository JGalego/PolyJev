# make deploy|test|destroy JEV=<folder>    make local [JEV=<folder>]    make check
JEVS := $(filter-out core,$(patsubst %/jev.py,%,$(wildcard */jev.py)))
STACK = polyjev-$(JEV)
FUN := scripts/fun.sh

.PHONY: deploy test local destroy check jev

deploy: jev  ## build the arm64 image, push it to ECR, deploy the stack
	@$(FUN) say 🏗️ "Building $(JEV) (arm64, weights baked in)"
	@sam build --parameter-overrides Jev=$(JEV)
	@$(FUN) say 🚀 "Deploying $(STACK)"
	@sam deploy --stack-name $(STACK) --parameter-overrides Jev=$(JEV) --resolve-image-repos
	@$(FUN) ok "$(STACK) is live"

test: jev  ## invoke the deployed Lambda with sample.* and pretty-print Probs
	@$(FUN) say 🔮 "Asking $(STACK)"
	@mkdir -p .aws-sam
	@uv run python -m core.payload $(JEV) > .aws-sam/payload.json
	@aws lambda invoke --function-name $(STACK) --payload fileb://.aws-sam/payload.json --cli-read-timeout 900 .aws-sam/response.json > /dev/null
	@uv run python -m json.tool .aws-sam/response.json

local:  ## run the Jev's pytest locally (every Jev when JEV is unset)
	@set -- $(or $(JEV),$(JEVS)); n=$$#; i=0; start=$$(date +%s); \
	for j; do $(FUN) bar $$i $$n "🧪 $$j ($$((i + 1))/$$n)" $$start; uv run pytest -q $$j || { $(FUN) fail "$$j failed"; exit 1; }; i=$$((i + 1)); done; \
	$(FUN) bar $$n $$n "🎉 all $$n green" $$start

destroy: jev  ## delete the stack and its ECR repository
	@$(FUN) say 🧹 "Deleting $(STACK)"
	@sam delete --stack-name $(STACK) --no-prompts

check:  ## pyright --strict over the whole repo
	@$(FUN) say 🔍 "pyright --strict"
	@uv run pyright
	@$(FUN) ok "Types check out"

jev:
	@test -n "$(JEV)" || { $(FUN) fail "set JEV to one of: $(JEVS)"; exit 1; }
