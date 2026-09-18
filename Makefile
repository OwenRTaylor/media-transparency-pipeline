# Media Transparency Pipeline — stage orchestration
# Each stage = one target. Recipes TBD.

.PHONY: extract stage dedupe validate export run hooks check-personal

hooks:     ## enable the tracked git hooks (run once after clone)
	git config core.hooksPath scripts/git-hooks
	chmod +x scripts/git-hooks/* scripts/check-no-personal.sh
	@echo "git hooks enabled (core.hooksPath=scripts/git-hooks)"

check-personal: ## scan staged changes for personal / local-only leaks
	bash scripts/check-no-personal.sh

extract:   ## Layer 1 — run source extractors

stage:     ## Layer 3 — load extractor output into DuckDB

dedupe:    ## Layer 3 — cross-source entity resolution

validate:  ## Layer 3 — post-stage checks

export:    ## Layer 3 — DuckDB -> SQLite

run:       ## full pipeline
