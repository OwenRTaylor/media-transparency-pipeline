# Media Transparency Pipeline — stage orchestration
# Each stage = one target. Recipes TBD.

.PHONY: extract stage dedupe validate export run

extract:   ## Layer 1 — run source extractors

stage:     ## Layer 3 — load extractor output into DuckDB

dedupe:    ## Layer 3 — cross-source entity resolution

validate:  ## Layer 3 — post-stage checks

export:    ## Layer 3 — DuckDB -> SQLite

run:       ## full pipeline
